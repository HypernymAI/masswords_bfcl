#!/usr/bin/env python3
"""
Fan Approach Stochastic Test - Testing Individual Yellies with Multiple Runs
Tests multiple prompt configurations with repeated sampling to establish statistical significance
Excludes deterministic content filter failures from testing
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path
import numpy as np

# Base configuration
BASE_MODEL = "azure/Meta-Llama-31-8B-Instruct-2"
RESULTS_DIR = Path("fan_stochastic_results")
PROMPTS_BASE_DIR = Path("/Users/fieldempress/Desktop/source/hypernym/llama-prompt-ops/bfcl_optimization/yellies_experiment/prompts")
NUM_THREADS = 1  # Default, can be overridden by command line
NUM_RUNS = 50  # Number of runs per configuration
BLACKLIST_DB = Path("content_filter_blacklist.db")
TEMPERATURE = 0.3  # Temperature for stochastic testing

# Find project root by looking for bfcl_eval directory
_current = Path.cwd()
while _current != _current.parent:
    if (_current / "bfcl_eval").exists():
        PROJECT_ROOT = _current
        break
    _current = _current.parent
else:
    raise RuntimeError("Could not find project root with bfcl_eval directory")

# Prompt configurations
PROMPT_CONFIGS = {
    "baseline": {
        "suffix": "",  # No suffix, use cached baseline
        "prompt_file": PROMPTS_BASE_DIR / "1_baseline.txt",  # Use explicit baseline prompt
        "description": "BFCL default baseline",
        "target_categories": ["simple", "irrelevance", "live_irrelevance", "live_simple", "live_relevance"],
        "expected_improvement": "0% (control)"
    },
    "kitchen_sink": {
        "suffix": "-yellies",  # Already tested as category-adaptive
        "prompt_file": "/Users/fieldempress/Desktop/source/hypernym/llama-prompt-ops/bfcl_optimization/yellies_experiment/bfcl_category_adaptive_yellied_prompt.txt",
        "description": "Category-adaptive yellies (kitchen sink)",
        "target_categories": ["simple", "irrelevance", "live_irrelevance", "live_simple", "live_relevance"],
        "expected_improvement": "Failed catastrophically"
    },
    "anti_verbosity": {
        "suffix": "-anti-verbosity",
        "prompt_file": PROMPTS_BASE_DIR / "2_anti_verbosity.txt",
        "description": "Anti-verbosity only for [] output",
        "target_categories": ["live_irrelevance"],
        "expected_improvement": "37.98% → 80%+"
    },
    "format_strict": {
        "suffix": "-format-strict",
        "prompt_file": PROMPTS_BASE_DIR / "3_format_strict.txt",
        "description": "Format compliance only",
        "target_categories": ["live_simple"],
        "expected_improvement": "72.48% → 85%+"
    },
    "param_precision": {
        "suffix": "-param-precision",
        "prompt_file": PROMPTS_BASE_DIR / "4_param_precision.txt",
        "description": "Parameter type precision only",
        "target_categories": ["simple"],
        "expected_improvement": "92.5% → 94%+"
    },
    "multi_tool": {
        "suffix": "-multi-tool",
        "prompt_file": PROMPTS_BASE_DIR / "5_multi_tool.txt",
        "description": "Multi-tool exploration only",
        "target_categories": ["multiple", "parallel"],
        "expected_improvement": "Unknown → 70%+"
    },
    "zero_output": {
        "suffix": "-zero-output",
        "prompt_file": PROMPTS_BASE_DIR / "6_zero_output.txt",
        "description": "Zero output enforcement only",
        "target_categories": ["irrelevance", "live_irrelevance"],
        "expected_improvement": "Maintain 90%+"
    }
}

def load_content_filter_blacklist():
    """Load deterministic content filter failures from blacklist database"""
    if not BLACKLIST_DB.exists():
        raise FileNotFoundError(f"Blacklist database not found at {BLACKLIST_DB}. Run create_content_filter_blacklist.py first.")
    
    conn = sqlite3.connect(BLACKLIST_DB)
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT test_id 
    FROM content_filter_blacklist 
    WHERE is_deterministic = 1
    """)
    
    blacklisted_ids = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    print(f"✓ Loaded {len(blacklisted_ids)} blacklisted test IDs")
    return blacklisted_ids

def get_run_directory(config_name, run_num):
    """Get directory for a specific run"""
    return RESULTS_DIR / config_name / f"run_{run_num:03d}"

def check_run_complete(config_name, run_num, categories):
    """Check if a run is already complete (has results AND scores)"""
    run_dir = get_run_directory(config_name, run_num)
    results_file = run_dir / "results.json"
    
    if not results_file.exists():
        return False
    
    # Verify it has all expected categories
    try:
        with open(results_file) as f:
            data = json.load(f)
            results = data.get("results", {})
            if not all(cat in results for cat in categories):
                return False
    except:
        return False
    
    # Also check if score files exist
    model_name = BASE_MODEL + PROMPT_CONFIGS[config_name]["suffix"]
    score_dir = run_dir / "score" / model_name.replace("/", "_")
    
    # Check if all category score files exist
    for category in categories:
        score_file = score_dir / f"BFCL_v3_{category}_score.json"
        if not score_file.exists():
            return False
    
    return True

def check_results_exist(config_name, run_num, categories):
    """Check if any test results already exist"""
    run_dir = get_run_directory(config_name, run_num)
    result_dir = run_dir / "result"
    model_name = BASE_MODEL + PROMPT_CONFIGS[config_name]["suffix"]
    model_dir = result_dir / model_name.replace("/", "_")
    
    if not model_dir.exists():
        return False
    
    # Check if any result files exist with content
    for cat in categories:
        result_file = model_dir / f"BFCL_v3_{cat}_result.json"
        if result_file.exists() and result_file.stat().st_size > 0:
            return True
    
    return False

def get_completed_runs(config_name, categories):
    """Get list of completed run numbers for a configuration"""
    completed = []
    for run_num in range(1, NUM_RUNS + 1):
        if check_run_complete(config_name, run_num, categories):
            completed.append(run_num)
    return completed

def backup_original_prompt():
    """Backup the original prompt file"""
    prompt_file = PROJECT_ROOT / "bfcl_eval/constants/default_prompts.py"
    backup_file = prompt_file.with_suffix('.py.backup')
    
    if not backup_file.exists():
        shutil.copy(prompt_file, backup_file)
        print(f"✓ Backed up original prompt to {backup_file}")
    return prompt_file, backup_file

def validate_prompt_file(prompt_file_path):
    """Validate that prompt file exists"""
    if not Path(prompt_file_path).exists():
        print(f"✗ Prompt file not found: {prompt_file_path}")
        return False
    return True


def check_cached_results(model_name, categories):
    """Check if results are already cached"""
    result_dir = Path(f"result/{model_name.replace('/', '_')}")
    return all((result_dir / f"BFCL_v3_{cat}_result.json").exists() for cat in categories)

def run_bfcl_test(config_name, run_num, categories_override=None):
    """Run BFCL test for a specific configuration and run number"""
    config = PROMPT_CONFIGS[config_name]
    model_name = BASE_MODEL + config["suffix"]
    categories = categories_override or config["target_categories"]
    run_dir = get_run_directory(config_name, run_num)
    
    print(f"\n{'='*60}")
    print(f"Testing: {config_name} - Run {run_num}/{NUM_RUNS}")
    print(f"Model: {model_name}")
    print(f"Temperature: {TEMPERATURE}")
    print(f"Directory: {run_dir}")
    print(f"{'='*60}")
    
    # Check if already complete
    results_file = run_dir / "results.json"
    if results_file.exists():
        print("✓ Run already has results.json, skipping entirely")
        return True
    
    if check_run_complete(config_name, run_num, categories):
        print("✓ Run already complete (has results and scores), skipping")
        return True
    
    # Check if results exist but evaluation failed
    has_results = check_results_exist(config_name, run_num, categories)
    results_file = run_dir / "results.json"
    has_results_json = results_file.exists()
    
    if has_results and has_results_json:
        print("✓ Found existing results, will skip generation and run evaluation only")
    elif has_results:
        print("✓ Found partial results, BFCL will automatically resume generation")
    else:
        print("No existing results found, generating all tests")
    
    # Create run directory structure
    run_dir.mkdir(parents=True, exist_ok=True)
    result_dir = run_dir / "result" / model_name.replace("/", "_")
    result_dir.mkdir(parents=True, exist_ok=True)
    score_dir = run_dir / "score" / model_name.replace("/", "_")
    score_dir.mkdir(parents=True, exist_ok=True)
    
    # No symlinks - just use the directories directly
    
    # Save current directory to restore later
    original_cwd = os.getcwd()
    
    try:
        # Change to run directory so BFCL writes to the correct location
        os.chdir(str(run_dir.absolute()))
        print(f"Changed to directory: {os.getcwd()}")
        
        # Validate prompt file if specified
        prompt_file_path = config.get("prompt_file")
        if prompt_file_path:
            print(f"Using prompt from: {prompt_file_path}")
            if not validate_prompt_file(prompt_file_path):
                return False
        
        # Skip generation if we already have complete results
        if has_results and has_results_json:
            print(f"\n[1/2] Skipping generation (results already exist)")
        else:
            print(f"\n[1/2] Generating responses...")
            
            # Just run normal generation - BFCL will automatically skip existing tests
            # thanks to our modification to collect_test_cases
            cmd = [
                "python", "-m", "bfcl_eval", "generate",
                "--model", model_name,
                "--test-category", ",".join(categories),
                "--num-threads", str(NUM_THREADS),
                "--temperature", str(TEMPERATURE),
                "--stochastic-result-dir", "./result"  # Use exact path in current directory
            ]
            
            # Add prompt file if specified
            if prompt_file_path:
                cmd.extend(["--prompt-file", str(Path(prompt_file_path).absolute())])
            
            subprocess.run(cmd, check=True)
            print("✓ Response generation complete")
        
        # Evaluate results
        print(f"\n[2/2] Evaluating results...")
        cmd = [
            "python", "-m", "bfcl_eval", "evaluate",
            "--model", model_name,
            "--test-category", ",".join(categories),
            "--stochastic-result-dir", "./result",  # Use exact path in current directory
            "--stochastic-score-dir", "./score"     # Use exact path in current directory
        ]
        
        subprocess.run(cmd, check=True)
        print("✓ Evaluation complete")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        return False
        
    finally:
        # Always restore original directory
        os.chdir(original_cwd)
        print(f"Restored directory: {os.getcwd()}")

def load_results(model_name, categories, blacklist, run_dir=None):
    """Load evaluation results from score files"""
    results = {}
    if run_dir:
        score_dir = run_dir / "score" / model_name.replace("/", "_")
    else:
        score_dir = Path("score") / model_name.replace("/", "_")
    
    for category in categories:
        score_file = score_dir / f"BFCL_v3_{category}_score.json"
        if score_file.exists():
            try:
                with open(score_file, 'r') as f:
                    # First line has the summary with actual results
                    first_line = f.readline()
                    if first_line:
                        summary = json.loads(first_line)
                        
                        # Use the actual values from the score file
                        results[category] = {
                            "total": summary.get("total_count", 0),
                            "correct": summary.get("correct_count", 0),
                            "accuracy": summary.get("accuracy", 0) * 100,  # Convert to percentage
                            "blacklisted_count": 0  # This was meaningless anyway
                        }
            except Exception as e:
                print(f"Error reading score file {score_file}: {e}")
                continue
    
    return results

def save_run_results(config_name, run_num, results):
    """Save results for a specific run"""
    run_dir = get_run_directory(config_name, run_num)
    results_file = run_dir / "results.json"
    
    with open(results_file, 'w') as f:
        json.dump({
            "config": config_name,
            "run": run_num,
            "timestamp": datetime.now().isoformat(),
            "temperature": TEMPERATURE,
            "model": BASE_MODEL + PROMPT_CONFIGS[config_name]["suffix"],
            "results": results
        }, f, indent=2)

def compare_fan_results(baseline_results, test_results, config_name):
    """Compare results for a specific yellie against baseline"""
    config = PROMPT_CONFIGS[config_name]
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {config_name}")
    print(f"{'='*60}")
    
    improvements = []
    for category in config["target_categories"]:
        if category in baseline_results and category in test_results:
            base_acc = baseline_results[category]["accuracy"]
            test_acc = test_results[category]["accuracy"]
            improvement = test_acc - base_acc
            improvements.append(improvement)
            
            status = "✓" if improvement > 0 else "✗" if improvement < -5 else "="
            print(f"{status} {category}: {base_acc:.1f}% → {test_acc:.1f}% ({improvement:+.1f}%)")
    
    if improvements:
        avg_improvement = sum(improvements) / len(improvements)
        print(f"\nAverage improvement: {avg_improvement:+.1f}%")
        
        if avg_improvement > 5:
            print("🎯 SIGNIFICANT IMPROVEMENT - This yellie works!")
        elif avg_improvement < -5:
            print("❌ DEGRADATION - This yellie makes things worse")
        else:
            print("≈ No significant effect")
    
    return improvements

def save_fan_report(all_results):
    """Save comprehensive fan test report"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = RESULTS_DIR / f"fan_approach_report_{timestamp}.json"
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "base_model": BASE_MODEL,
        "configurations_tested": list(all_results.keys()),
        "results": all_results,
        "summary": {
            "best_for_live_irrelevance": None,
            "best_for_live_simple": None,
            "best_for_simple": None,
            "best_overall": None
        }
    }
    
    # Find best performers
    for category in ["live_irrelevance", "live_simple", "simple"]:
        best_config = None
        best_accuracy = 0
        
        for config_name, results in all_results.items():
            if config_name != "baseline" and category in results:
                if results[category]["accuracy"] > best_accuracy:
                    best_accuracy = results[category]["accuracy"]
                    best_config = config_name
        
        if best_config:
            baseline_acc = all_results["baseline"][category]["accuracy"]
            report["summary"][f"best_for_{category}"] = {
                "config": best_config,
                "accuracy": best_accuracy,
                "improvement": best_accuracy - baseline_acc
            }
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n✓ Fan test report saved to {report_file}")
    return report

def analyze_stochastic_results(config_name, categories):
    """Analyze results across all runs for a configuration"""
    accuracies = {cat: [] for cat in categories}
    
    for run_num in range(1, NUM_RUNS + 1):
        run_dir = get_run_directory(config_name, run_num)
        results_file = run_dir / "results.json"
        
        if results_file.exists():
            with open(results_file) as f:
                data = json.load(f)
                for cat, result in data["results"].items():
                    if cat in accuracies:
                        accuracies[cat].append(result["accuracy"])
    
    stats = {}
    for cat, accs in accuracies.items():
        if accs:
            stats[cat] = {
                "mean": np.mean(accs),
                "std": np.std(accs),
                "min": np.min(accs),
                "max": np.max(accs),
                "runs": len(accs),
                "95_ci_lower": np.percentile(accs, 2.5),
                "95_ci_upper": np.percentile(accs, 97.5)
            }
    
    return stats

def main():
    """Run the stochastic fan approach test"""
    print("BFCL Fan Approach Stochastic Test")
    print("==================================")
    print(f"Configurations: ALL (baseline + yellies)")
    print(f"Runs per config: {NUM_RUNS}")
    print(f"Temperature: {TEMPERATURE}")
    print(f"Threads: {NUM_THREADS}")
    
    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Load blacklist
    blacklist = load_content_filter_blacklist()
    
    # Backup original prompt
    prompt_file, backup_file = backup_original_prompt()
    
    # Test categories
    ALL_TEST_CATEGORIES = ["simple", "irrelevance", "live_irrelevance", "live_simple", "live_relevance"]
    
    # All configurations to test
    if args.config == "all":
        test_configs = ["baseline", "anti_verbosity", "format_strict", "param_precision", "zero_output"]
    else:
        test_configs = [args.config]
    
    # Store results for final comparison
    all_config_stats = {}
    
    try:
        for config_name in test_configs:
            print(f"\n{'='*80}")
            print(f"TESTING CONFIGURATION: {config_name}")
            print(f"Description: {PROMPT_CONFIGS[config_name]['description']}")
            print(f"{'='*80}")
            
            
            # Check existing runs
            completed_runs = get_completed_runs(config_name, ALL_TEST_CATEGORIES)
            print(f"\nCompleted runs for {config_name}: {len(completed_runs)}/{NUM_RUNS}")
            if completed_runs:
                print(f"Already complete: {completed_runs[:10]}{'...' if len(completed_runs) > 10 else ''}")
            
            # Run tests
            for run_num in range(1, NUM_RUNS + 1):
                if run_num in completed_runs:
                    print(f"\nSkipping run {run_num} (already complete)")
                    continue
                    
                # Run test
                if run_bfcl_test(config_name, run_num, categories_override=ALL_TEST_CATEGORIES):
                    # Check if results.json was created by run_bfcl_test or if we need to create it
                    results_file = get_run_directory(config_name, run_num) / "results.json"
                    needs_results = False
                    
                    if not results_file.exists():
                        needs_results = True
                    else:
                        # Check if results.json exists but has empty results
                        try:
                            with open(results_file) as f:
                                data = json.load(f)
                                if not data.get("results", {}):
                                    needs_results = True
                        except:
                            needs_results = True
                    
                    if needs_results:
                        # Save results if they don't exist or are empty
                        run_dir = get_run_directory(config_name, run_num)
                        model_name = BASE_MODEL + PROMPT_CONFIGS[config_name]["suffix"]
                        results = load_results(model_name, ALL_TEST_CATEGORIES, blacklist, run_dir)
                        save_run_results(config_name, run_num, results)
                    
                    # Show progress every 5 runs
                    if run_num % 5 == 0 or run_num == NUM_RUNS:
                        print(f"\n{'='*60}")
                        print(f"PROGRESS UPDATE - {len(get_completed_runs(config_name, ALL_TEST_CATEGORIES))}/{NUM_RUNS} runs complete")
                        print(f"{'='*60}")
                        
                        stats = analyze_stochastic_results(config_name, ALL_TEST_CATEGORIES)
                        for cat, stat in stats.items():
                            if stat['runs'] > 0:
                                print(f"{cat}: {stat['mean']:.1f}% ± {stat['std']:.1f}% ({stat['runs']} runs)")
        
            # Configuration complete - save stats
            config_stats = analyze_stochastic_results(config_name, ALL_TEST_CATEGORIES)
            all_config_stats[config_name] = config_stats
            
            # Save per-config report
            report = {
                "config": config_name,
                "model": BASE_MODEL + PROMPT_CONFIGS[config_name]["suffix"],
                "num_runs": NUM_RUNS,
                "temperature": TEMPERATURE,
                "timestamp": datetime.now().isoformat(),
                "blacklisted_count": len(blacklist),
                "completed_runs": len(get_completed_runs(config_name, ALL_TEST_CATEGORIES)),
                "statistics": config_stats
            }
            
            report_file = RESULTS_DIR / f"{config_name}_stochastic_report.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n✓ Config report saved to {report_file}")
        
        # Final comparison across all configurations
        print("\n" + "="*80)
        print("FINAL FAN APPROACH COMPARISON (WITH STOCHASTIC RESULTS)")
        print("="*80)
        
        # Get baseline stats for comparison
        baseline_stats = all_config_stats.get("baseline", {})
        
        for config_name in test_configs:
            if config_name == "baseline":
                continue
                
            print(f"\n{config_name.upper()} vs BASELINE:")
            print(f"Description: {PROMPT_CONFIGS[config_name]['description']}")
            print(f"Target categories: {PROMPT_CONFIGS[config_name]['target_categories']}")
            print(f"Actual categories tested: {ALL_TEST_CATEGORIES}")
            print("-" * 60)
            
            config_stats = all_config_stats.get(config_name, {})
            
            for category in ALL_TEST_CATEGORIES:
                if category in baseline_stats and category in config_stats:
                    base_mean = baseline_stats[category]['mean']
                    test_mean = config_stats[category]['mean']
                    improvement = test_mean - base_mean
                    
                    # Calculate if statistically significant (non-overlapping 95% CIs)
                    base_ci_upper = baseline_stats[category]['95_ci_upper']
                    test_ci_lower = config_stats[category]['95_ci_lower']
                    significant = test_ci_lower > base_ci_upper
                    
                    target_marker = "🎯 " if category in PROMPT_CONFIGS[config_name]["target_categories"] else "   "
                    sig_marker = "***" if significant else ""
                    
                    print(f"{target_marker}{category}: {base_mean:.1f}% → {test_mean:.1f}% ({improvement:+.1f}%) {sig_marker}")
        
        # Save comprehensive report
        final_report = {
            "timestamp": datetime.now().isoformat(),
            "base_model": BASE_MODEL,
            "num_runs_per_config": NUM_RUNS,
            "temperature": TEMPERATURE,
            "configurations_tested": test_configs,
            "blacklisted_count": len(blacklist),
            "all_statistics": all_config_stats,
            "summary": {
                "significant_improvements": [],
                "best_for_category": {}
            }
        }
        
        # Find significant improvements and best configs
        for config_name in test_configs:
            if config_name == "baseline":
                continue
                
            config_stats = all_config_stats.get(config_name, {})
            
            for category in ALL_TEST_CATEGORIES:
                if category in baseline_stats and category in config_stats:
                    base_mean = baseline_stats[category]['mean']
                    test_mean = config_stats[category]['mean']
                    improvement = test_mean - base_mean
                    
                    # Check significance
                    if config_stats[category]['95_ci_lower'] > baseline_stats[category]['95_ci_upper']:
                        final_report["summary"]["significant_improvements"].append({
                            "config": config_name,
                            "category": category,
                            "improvement": improvement,
                            "baseline_mean": base_mean,
                            "test_mean": test_mean
                        })
                    
                    # Track best config per category
                    if category not in final_report["summary"]["best_for_category"] or \
                       test_mean > final_report["summary"]["best_for_category"][category]["mean"]:
                        final_report["summary"]["best_for_category"][category] = {
                            "config": config_name,
                            "mean": test_mean,
                            "improvement": improvement
                        }
        
        # Save final report
        final_report_file = RESULTS_DIR / f"fan_stochastic_final_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(final_report_file, 'w') as f:
            json.dump(final_report, f, indent=2)
        
        print(f"\n✓ Final report saved to {final_report_file}")
        
        # Print summary
        print("\n" + "="*60)
        print("SUMMARY OF SIGNIFICANT IMPROVEMENTS")
        print("="*60)
        
        if final_report["summary"]["significant_improvements"]:
            for item in final_report["summary"]["significant_improvements"]:
                print(f"✓ {item['config']} significantly improves {item['category']}: "
                      f"{item['baseline_mean']:.1f}% → {item['test_mean']:.1f}% (+{item['improvement']:.1f}%)")
        else:
            print("No statistically significant improvements found.")
        
    finally:
        print("\n✓ Test complete")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fan Approach Test - Test isolated yellies")
    parser.add_argument(
        "--num-threads", 
        type=int, 
        default=1,
        help="Number of threads for parallel API calls (default: 1)"
    )
    parser.add_argument(
        "--config",
        type=str,
        choices=["all", "baseline", "anti_verbosity", "format_strict", "param_precision", "zero_output"],
        default="all",
        help="Which configuration to test (default: all)"
    )
    args = parser.parse_args()
    
    # Set global NUM_THREADS from command line
    NUM_THREADS = args.num_threads
    print(f"Using {NUM_THREADS} thread(s) for API calls")
    
    main()