import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import traceback
from pathlib import Path

from bfcl_eval.constants.category_mapping import (
    MULTI_TURN_FUNC_DOC_FILE_MAPPING,
    TEST_FILE_MAPPING,
)
from bfcl_eval.constants.eval_config import (
    MULTI_TURN_FUNC_DOC_PATH,
    PROJECT_ROOT,
    PROMPT_PATH,
    RESULT_PATH,
    TEST_IDS_TO_GENERATE_PATH,
)
from bfcl_eval.eval_checker.eval_runner_helper import load_file
from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING
from bfcl_eval.model_handler.model_style import ModelStyle
from bfcl_eval.utils import is_multi_turn, parse_test_category_argument, sort_key
from bfcl_eval.model_handler.utils import get_rate_limit_count
from tqdm import tqdm

RETRY_LIMIT = 3
# 60s for the timer to complete. But often we find that even with 60 there is a conflict. So 65 is a safe no.
RETRY_DELAY = 65  # Delay in seconds


def get_args():
    parser = argparse.ArgumentParser()
    # Refer to model_choice for supported models.
    parser.add_argument("--model", type=str, default="gorilla-openfunctions-v2", nargs="+")
    # Refer to test_categories for supported categories.
    parser.add_argument("--test-category", type=str, default="all", nargs="+")

    # Parameters for the model that you want to test.
    parser.add_argument("--temperature", type=float, default=0.001)
    parser.add_argument("--include-input-log", action="store_true", default=False)
    parser.add_argument("--exclude-state-log", action="store_true", default=False)
    parser.add_argument("--num-threads", default=1, type=int)
    parser.add_argument("--num-gpus", default=1, type=int)
    parser.add_argument("--backend", default="vllm", type=str, choices=["vllm", "sglang"])
    parser.add_argument("--gpu-memory-utilization", default=0.9, type=float)
    parser.add_argument("--result-dir", default=None, type=str)
    parser.add_argument("--stochastic-result-dir", default=None, type=str, help="Use this exact directory for results (no PROJECT_ROOT prepending)")
    parser.add_argument("--run-ids", action="store_true", default=False)
    parser.add_argument("--allow-overwrite", "-o", action="store_true", default=False)
    parser.add_argument("--prompt-file", type=str, default=None, help="Path to custom prompt file to use instead of default")
    # Add the new skip_vllm argument
    parser.add_argument(
        "--skip-server-setup",
        action="store_true",
        default=False,
        help="Skip vLLM/SGLang server setup and use existing endpoint specified by the VLLM_ENDPOINT and VLLM_PORT environment variables."
    )
    # Optional local model path
    parser.add_argument(
        "--local-model-path",
        type=str,
        default=None,
        help="Specify the path to a local directory containing the model's config/tokenizer/weights for fully offline inference. Use this only if the model weights are stored in a location other than the default HF_HOME directory.",
    )
    args = parser.parse_args()

    return args


def build_handler(model_name, temperature):
    config = MODEL_CONFIG_MAPPING[model_name]
    handler = config.model_handler(model_name, temperature)
    # Propagate config flags to the handler instance
    handler.is_fc_model = config.is_fc_model
    return handler


def get_involved_test_entries(test_category_args, run_ids):
    all_test_file_paths, all_test_categories, all_test_entries_involved = [], [], []
    if run_ids:
        with open(TEST_IDS_TO_GENERATE_PATH) as f:
            test_ids_to_generate = json.load(f)
        for category, test_ids in test_ids_to_generate.items():
            if len(test_ids) == 0:
                continue
            test_file_path = TEST_FILE_MAPPING[category]
            all_test_entries_involved.extend(
                [
                    entry
                    for entry in load_file(PROMPT_PATH / test_file_path)
                    if entry["id"] in test_ids
                ]
            )
            all_test_categories.append(category)
            all_test_file_paths.append(test_file_path)

    else:
        all_test_file_paths, all_test_categories = parse_test_category_argument(test_category_args)
        # Make a copy here since we are removing list elemenets inside the for loop
        for test_category, file_to_open in zip(
            all_test_categories[:], all_test_file_paths[:]
        ):
            all_test_entries_involved.extend(load_file(PROMPT_PATH / file_to_open))

    return (
        all_test_file_paths,
        all_test_categories,
        all_test_entries_involved,
    )


def collect_test_cases(
    args, model_name, all_test_categories, all_test_file_paths, all_test_entries_involved
):
    model_name_dir = model_name.replace("/", "_")
    model_result_dir = args.result_dir / model_name_dir
    print(f"DEBUG: args.result_dir = {args.result_dir}")
    print(f"DEBUG: model_result_dir = {model_result_dir}")
    print(f"DEBUG: model_result_dir.absolute() = {model_result_dir.absolute()}")

    # Always check what already exists - this enables automatic resume
    existing_result = []
    existing_ids_by_category = {}
    
    for test_category, file_to_open in zip(all_test_categories, all_test_file_paths):
        result_file_path = model_result_dir / file_to_open.replace(".json", "_result.json")
        if result_file_path.exists():
            category_results = load_file(result_file_path)
            existing_result.extend(category_results)
            # Track which IDs exist per category for logging
            existing_ids_by_category[test_category] = {entry["id"] for entry in category_results}
            
    existing_ids = [entry["id"] for entry in existing_result]
    
    # Log what we found
    if existing_ids:
        print(f"Found {len(existing_ids)} existing results:")
        for cat, ids in existing_ids_by_category.items():
            total_for_cat = len([t for t in all_test_entries_involved if t["id"].startswith(cat)])
            print(f"  {cat}: {len(ids)}/{total_for_cat} complete")

    # Only generate tests that don't already have results
    test_cases_to_generate = [
        test_case
        for test_case in all_test_entries_involved
        if test_case["id"] not in existing_ids
    ]
    
    if not test_cases_to_generate:
        print("All tests already have results!")
    else:
        print(f"Will generate {len(test_cases_to_generate)} missing tests")
    
    test_cases_to_generate = process_multi_turn_test_case(test_cases_to_generate)

    return sorted(test_cases_to_generate, key=sort_key)


def process_multi_turn_test_case(test_cases):
    """
    Multi-turn test cases don't have the function doc in the prompt. We need to add them here.
    """
    for entry in test_cases:
        if not is_multi_turn(entry["id"]):
            continue
        involved_classes = entry["involved_classes"]
        entry["function"] = []
        for func_collection in involved_classes:
            # func_doc is a list of dict
            func_doc = load_file(
                MULTI_TURN_FUNC_DOC_PATH / MULTI_TURN_FUNC_DOC_FILE_MAPPING[func_collection]
            )
            entry["function"].extend(func_doc)

        # Handle Miss Func category; we need to remove the holdout function doc
        if "missed_function" in entry:
            for turn_index, missed_func_names in entry["missed_function"].items():
                entry["missed_function"][turn_index] = []
                for missed_func_name in missed_func_names:
                    for i, func_doc in enumerate(entry["function"]):
                        if func_doc["name"] == missed_func_name:
                            # Add the missed function doc to the missed_function list
                            entry["missed_function"][turn_index].append(func_doc)
                            # Remove it from the function list
                            entry["function"].pop(i)
                            break

    return test_cases


def multi_threaded_inference(handler, test_case, include_input_log, exclude_state_log):
    # Record when this thread actually starts processing
    test_case["_processing_start_time"] = time.time()
    test_case["_rate_limit_count"] = 0  # Track RL count for status display
    
    assert type(test_case["function"]) is list

    retry_count = 0
    rate_limit_count = 0
    
    # Function to check remaining active tests
    def get_active_test_count():
        if "_get_active_count" in test_case:
            return test_case["_get_active_count"]()
        return 999  # Default if not available

    while True:
        try:
            # Remove non-serializable fields before deepcopy
            stall_event = test_case.pop("_stall_event", None)
            increment_rate_limit = test_case.pop("_increment_rate_limit", None)
            get_active_count = test_case.pop("_get_active_count", None)
            
            # Now safe to deepcopy
            test_case_copy = deepcopy(test_case)
            
            # Restore the fields
            if stall_event:
                test_case["_stall_event"] = stall_event
            if increment_rate_limit:
                test_case["_increment_rate_limit"] = increment_rate_limit
            if get_active_count:
                test_case["_get_active_count"] = get_active_count
            
            result, metadata = handler.inference(
                test_case_copy, include_input_log, exclude_state_log
            )
            break  # Success, exit the loop
        except Exception as e:
            # TODO: It might be better to handle the exception in the handler itself rather than a universal catch block here, as each handler use different ways to call the endpoint.
            # OpenAI has openai.RateLimitError while Anthropic has anthropic.RateLimitError. It would be more robust in the long run.
            error_str = str(e).lower()
            if (
                "rate limit reached" in error_str
                or (hasattr(e, "status_code") and (e.status_code in {429, 503, 500}))
                or "timeout" in error_str
                or "timed out" in error_str
                or "read timed out" in error_str
                or "负载已饱和" in str(e)  # Chinese overload error
                or "relay error" in error_str
            ):
                retry_count += 1
                rate_limit_count += 1
                test_case["_rate_limit_count"] = rate_limit_count  # Update for display
                test_case["_last_retry_time"] = time.time()  # Track when we last retried
                # Update RL counter immediately
                if "_increment_rate_limit" in test_case:
                    test_case["_increment_rate_limit"]()
                
                # Check if it's a timeout - retry immediately
                if "timeout" in error_str or "timed out" in error_str:
                    # Timeout detected - retry immediately without delay
                    print(f"\n⚡ Timeout detected for {test_case['id']} - retrying immediately")
                    continue  # Skip the delay
                
                # Dynamic retry delay for rate limits
                active_count = get_active_test_count()
                if active_count <= 6:
                    # Scale delay based on how few tests remain
                    if active_count == 1:
                        dynamic_delay = 5  # Just 5 seconds for last test
                    elif active_count == 2:
                        dynamic_delay = 10
                    elif active_count == 3:
                        dynamic_delay = 15
                    elif active_count == 4:
                        dynamic_delay = 20
                    elif active_count == 5:
                        dynamic_delay = 35
                    else:  # 6 tests
                        dynamic_delay = 45
                else:
                    dynamic_delay = RETRY_DELAY
                
                # Sleep with stall event checking
                stall_event = test_case.get("_stall_event")
                if stall_event:
                    # Check for stall event every 0.5 seconds
                    elapsed = 0
                    while elapsed < dynamic_delay:
                        if stall_event.is_set():
                            # Stall detected - break out immediately
                            test_case["_last_poke_time"] = time.time()
                            break
                        time.sleep(min(0.5, dynamic_delay - elapsed))
                        elapsed += 0.5
                else:
                    # Fallback if no stall event
                    time.sleep(dynamic_delay)
            else:
                # Check if it's a content filter error
                error_str = str(e)
                error_type = None
                if "content_filter" in error_str or "content management policy" in error_str:
                    # Silently continue for content filter errors
                    error_type = "content_filter"
                else:
                    # This is usually the case when the model getting stuck on one particular test case.
                    # For example, timeout error or FC model returning invalid JSON response.
                    # Since temperature is already set to 0.001, retrying the same test case will not help.
                    # So we continue the generation process and record the error message as the model response
                    print("-" * 100)
                    print(
                        "❗️❗️ Error occurred during inference. Maximum retries reached for rate limit or other error. Continuing to next test case."
                    )
                    print(f"❗️❗️ Test case ID: {test_case['id']}, Error: {str(e)}")
                    traceback.print_exc(limit=10)
                    print("-" * 100)

                return {
                    "id": test_case["id"],
                    "result": f"Error during inference: {str(e)}",
                    "traceback": traceback.format_exc(),
                    "_error_type": error_type  # Internal field for tracking
                }

    result_to_write = {
        "id": test_case["id"],
        "result": result,
    }

    result_to_write.update(metadata)
    
    # Add rate limit count if any occurred
    if rate_limit_count > 0:
        result_to_write["_rate_limit_count"] = rate_limit_count

    return result_to_write


def generate_results(args, model_name, test_cases_total):
    update_mode = args.allow_overwrite
    handler = build_handler(model_name, args.temperature)

    if handler.model_style == ModelStyle.OSSMODEL:
        # batch_inference will handle the writing of results
        handler.batch_inference(
            test_entries=test_cases_total,
            num_gpus=args.num_gpus,
            gpu_memory_utilization=args.gpu_memory_utilization,
            backend=args.backend,
            skip_server_setup=args.skip_server_setup,
            local_model_path=args.local_model_path,
            include_input_log=args.include_input_log,
            exclude_state_log=args.exclude_state_log,
            result_dir=args.result_dir,
            update_mode=update_mode,
        )

    else:
        futures = []
        # Add counters for tracking errors
        error_counts = {"rate_limit": 0, "content_filter": 0}
        
        with ThreadPoolExecutor(max_workers=args.num_threads) as executor:
            with tqdm(
                total=len(test_cases_total), desc=f"Generating results for {model_name}"
            ) as pbar:

                import time
                start_times = {}  # Track when each test starts
                test_id_map = {}  # Map futures to test IDs
                test_case_map = {}  # Map futures to test cases
                
                # Make error_counts accessible to threads
                import threading
                error_lock = threading.Lock()
                
                # Global stall detection
                last_completion_time = [time.time()]  # Track when last task completed
                stall_event = threading.Event()  # Event to signal stall detected
                completed_count = [0]  # Track completed tasks
                
                def increment_rate_limit():
                    with error_lock:
                        error_counts["rate_limit"] += 1
                        # Force progress bar update
                        pbar.set_postfix({
                            "CF": error_counts["content_filter"],
                            "RL": error_counts["rate_limit"]
                        })
                        pbar.refresh()
                
                # Function to count active tests
                def get_active_count():
                    return sum(1 for f in futures if not f.done())
                
                # Watchdog thread for stall detection
                def stall_watchdog():
                    while True:
                        time.sleep(1)  # Check every second
                        active_count = get_active_count()
                        
                        # Only care about last 1-8 tasks
                        if 1 <= active_count <= 8:
                            time_since_last_completion = time.time() - last_completion_time[0]
                            
                            # If no progress in 10 seconds, poke every 10 seconds
                            if time_since_last_completion > 10:
                                # Poke every 10 seconds (when time is 10, 20, 30, etc)
                                if int(time_since_last_completion) % 10 == 0:
                                    # Track if we already poked at this second
                                    current_poke_time = int(time_since_last_completion)
                                    if not hasattr(stall_watchdog, 'last_poke_time') or stall_watchdog.last_poke_time != current_poke_time:
                                        stall_watchdog.last_poke_time = current_poke_time
                                        stall_watchdog.poke_count = getattr(stall_watchdog, 'poke_count', 0) + 1
                                        
                                        # Set event for a short pulse
                                        stall_event.set()
                                        # Store poke time in a shared location
                                        stall_watchdog.last_poke_timestamp = time.time()
                                        
                                        # Wait a bit then clear
                                        time.sleep(0.5)
                                        stall_event.clear()
                        
                        # Exit when all done
                        if active_count == 0:
                            break
                
                # Display update thread
                def display_updater():
                    while True:
                        time.sleep(1)  # Update every second
                        update_status_display()
                        
                        # Update main progress bar with stall info
                        active_count = get_active_count()
                        postfix_dict = {
                            "CF": error_counts["content_filter"],
                            "RL": get_rate_limit_count()
                        }
                        
                        # Add stall timer if we're in the danger zone
                        if 1 <= active_count <= 8:
                            time_since_last = time.time() - last_completion_time[0]
                            if time_since_last > 5:  # Show after 5 seconds
                                postfix_dict["⚡STL"] = f"{time_since_last:.0f}s"
                        
                        pbar.set_postfix(postfix_dict)
                        
                        # Exit when all done
                        if active_count == 0:
                            break
                
                # Start the watchdog thread
                watchdog = threading.Thread(target=stall_watchdog, daemon=True)
                watchdog.start()
                
                # Start display updater thread
                display_thread = threading.Thread(target=display_updater, daemon=True)
                display_thread.start()
                
                for test_case in test_cases_total:
                    test_case["_increment_rate_limit"] = increment_rate_limit
                    test_case["_get_active_count"] = get_active_count
                    test_case["_stall_event"] = stall_event  # Pass stall event to each test
                    future = executor.submit(
                        multi_threaded_inference,
                        handler,
                        test_case,
                        args.include_input_log,
                        args.exclude_state_log,
                    )
                    futures.append(future)
                    test_id_map[future] = test_case["id"]
                    test_case_map[future] = test_case
                    start_times[test_case["id"]] = time.time()

                # Process results as they complete for better parallelism
                from concurrent.futures import as_completed
                last_update = time.time()
                
                # Create 5 status lines below progress bar
                from tqdm import trange
                status_bars = []
                for i in range(5):
                    bar = tqdm(total=0, desc="", bar_format="{desc}", position=i+1, leave=True)
                    status_bars.append(bar)
                
                # Helper to update status display
                def update_status_display():
                    current_time = time.time()
                    running = []
                    for f in futures:
                        if not f.done() and f in test_id_map:
                            test_id = test_id_map[f]
                            test_case = test_case_map[f]
                            elapsed = current_time - start_times[test_id]
                            rl_count = test_case.get("_rate_limit_count", 0)
                            last_retry = test_case.get("_last_retry_time", 0)
                            time_since_retry = current_time - last_retry if last_retry > 0 else 0
                            last_poke = test_case.get("_last_poke_time", 0)
                            time_since_poke = current_time - last_poke if last_poke > 0 else 0
                            running.append((elapsed, test_id, rl_count, time_since_retry, time_since_poke))
                    
                    running.sort(reverse=True)
                    top_5 = running[:5]
                    
                    # Update each status bar
                    for i in range(5):
                        if i < len(top_5):
                            elapsed, tid, rl_count, time_since_retry, time_since_poke = top_5[i]
                            
                            # Change marker based on poke status
                            if time_since_poke > 0 and time_since_poke < 10:
                                marker = "🔔"  # Recently poked
                            elif elapsed > 120:
                                marker = "⏰"
                            elif elapsed > 60:
                                marker = "⏳"
                            else:
                                marker = "⏱️"
                            
                            # Add RL count and last retry time if any
                            rl_str = f" [RL:{rl_count}]" if rl_count > 0 else ""
                            retry_str = f" [LR:{time_since_retry:.0f}s]" if time_since_retry > 0 else ""
                            poke_str = f" [LP:{time_since_poke:.0f}s]" if time_since_poke > 0 else ""
                            desc = f"{marker} {tid}: {elapsed:.0f}s{rl_str}{retry_str}{poke_str}"
                        else:
                            desc = ""
                        status_bars[i].set_description_str(desc)
                
                for future in as_completed(futures):
                    try:
                        # Update display periodically
                        current_time = time.time()
                        if current_time - last_update > 1:  # Update every second
                            update_status_display()
                            # Also update the RL counter in progress bar
                            pbar.set_postfix({
                                "CF": error_counts["content_filter"],
                                "RL": get_rate_limit_count()
                            })
                            last_update = current_time
                        
                        result = future.result()  # This should always return a dict from multi_threaded_inference
                        
                        # Update last completion time
                        last_completion_time[0] = time.time()
                        completed_count[0] += 1
                        
                        # Clear stall event if set since we made progress
                        if stall_event.is_set():
                            stall_event.clear()
                        
                        # Check for error types and update counters
                        if "_error_type" in result:
                            if result["_error_type"] == "content_filter":
                                error_counts["content_filter"] += 1
                            # Remove internal field before writing
                            del result["_error_type"]
                        
                        # Remove internal tracking fields if present
                        for field in ["_rate_limit_count", "_increment_rate_limit", "_get_active_count", 
                                     "_stall_event", "_processing_start_time"]:
                            if field in result:
                                del result[field]
                        
                        handler.write(
                            result, result_dir=args.result_dir, update_mode=args.run_ids
                        )
                        
                        # Remove from tracking
                        test_id = test_id_map.pop(future, None)
                        if test_id and test_id in start_times:
                            del start_times[test_id]
                        
                        # Update progress bar
                        pbar.update()
                        # Always refresh postfix to show current counts
                        pbar.set_postfix({
                            "CF": error_counts["content_filter"],
                            "RL": get_rate_limit_count()
                        })
                        
                        # Update display after completion
                        update_status_display()
                    except Exception as e:
                        print(f"\n\n❌ CRITICAL ERROR: Failed to process/write result: {str(e)}")
                        print("Aborting entire program - result writing failed!")
                        import traceback
                        traceback.print_exc()
                        import sys
                        sys.exit(1)
                
                # Clean up status bars
                for bar in status_bars:
                    bar.close()


def main(args):
    # Load custom prompt if provided
    if args.prompt_file:
        from bfcl_eval.model_handler.utils import load_custom_prompt_from_file
        load_custom_prompt_from_file(args.prompt_file)
        print(f"✓ Loaded custom prompt from: {args.prompt_file}")

    if type(args.model) is not list:
        args.model = [args.model]
    if type(args.test_category) is not list:
        args.test_category = [args.test_category]

    (
        all_test_file_paths,
        all_test_categories,
        all_test_entries_involved,
    ) = get_involved_test_entries(args.test_category, args.run_ids)

    for model_name in args.model:
        if model_name not in MODEL_CONFIG_MAPPING:
            raise ValueError(
                        f"Unknown model_name '{model_name}'.\n"
                        "• For officially supported models, please refer to `SUPPORTED_MODELS.md`.\n"
                        "• For running new models, please refer to `README.md` and `CONTRIBUTING.md`."
                    )
    print(f"Generating results for {args.model}")
    if args.run_ids:
        print("Running specific test cases. Ignoring `--test-category` argument.")
    else:
        print(f"Running full test cases for categories: {all_test_categories}.")

    if args.stochastic_result_dir is not None:
        # Use the exact path provided for stochastic testing
        args.result_dir = Path(args.stochastic_result_dir)
    elif args.result_dir is not None:
        args.result_dir = PROJECT_ROOT / args.result_dir
    else:
        args.result_dir = RESULT_PATH

    for model_name in args.model:
        test_cases_total = collect_test_cases(
            args,
            model_name,
            all_test_categories,
            all_test_file_paths,
            all_test_entries_involved,
        )

        if len(test_cases_total) == 0:
            print(
                f"All selected test cases have been previously generated for {model_name}. No new test cases to generate."
            )
        else:
            generate_results(args, model_name, test_cases_total)
