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
PROMPTS_BASE_DIR = Path("jupiter_bfcl/yellies_prompts")
NUM_THREADS = 1  # Default, can be overridden by command line
NUM_RUNS = 50  # Number of runs per configuration
BLACKLIST_DB = Path("content_filter_blacklist.db")
TEMPERATURE = 0.3  # Temperature for stochastic testing

# Prompt configurations
PROMPT_CONFIGS = {
    "baseline": {
        "suffix": "",  # No suffix, use cached baseline
        "prompt_file": None,  # Use default BFCL prompt
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
    """Check if a run is already complete"""
    run_dir = get_run_directory(config_name, run_num)
    results_file = run_dir / "results.json"
    
    if not results_file.exists():
        return False
    
    # Verify it has all expected categories
    try:
        with open(results_file) as f:
            data = json.load(f)
            results = data.get("results", {})
            return all(cat in results for cat in categories)
    except:
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
    prompt_file = Path("bfcl_eval/constants/default_prompts.py")
    backup_file = prompt_file.with_suffix('.py.backup')
    
    if not backup_file.exists():
        shutil.copy(prompt_file, backup_file)
        print(f"✓ Backed up original prompt to {backup_file}")
    return prompt_file, backup_file

def set_prompt_from_file(prompt_file_path):
    """Replace the default prompt with content from file"""
    if not Path(prompt_file_path).exists():
        print(f"✗ Prompt file not found: {prompt_file_path}")
        return False
        
    with open(prompt_file_path, 'r') as f:
        # Remove {functions} line if present
        lines = f.readlines()
        if lines and lines[-1].strip() == "{functions}":
            lines = lines[:-1]
        prompt_text = "".join(lines).strip()
    
    prompt_file = Path("bfcl_eval/constants/default_prompts.py")
    
    with open(prompt_file, 'r') as f:
        content = f.read()
    
    # Replace the DEFAULT_SYSTEM_PROMPT_WITHOUT_FUNC_DOC
    import re
    pattern = r'DEFAULT_SYSTEM_PROMPT_WITHOUT_FUNC_DOC = """.*?"""'
    replacement = f'DEFAULT_SYSTEM_PROMPT_WITHOUT_FUNC_DOC = """{prompt_text}"""'
    
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    with open(prompt_file, 'w') as f:
        f.write(new_content)
    
    return True

def restore_original_prompt(backup_file):
    """Restore the original prompt from backup"""
    prompt_file = Path("bfcl_eval/constants/default_prompts.py")
    shutil.copy(backup_file, prompt_file)

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
    if check_run_complete(config_name, run_num, categories):
        print("✓ Run already complete, skipping")
        return True
    
    # Create run directory structure
    run_dir.mkdir(parents=True, exist_ok=True)
    result_dir = run_dir / "result" / model_name.replace("/", "_")
    result_dir.mkdir(parents=True, exist_ok=True)
    score_dir = run_dir / "score" / model_name.replace("/", "_")
    score_dir.mkdir(parents=True, exist_ok=True)
    
    # Save original directories
    original_result_dir = Path("result")
    original_score_dir = Path("score")
    
    # Backup existing dirs if they exist
    if original_result_dir.exists():
        shutil.move(str(original_result_dir), "result_backup")
    if original_score_dir.exists():
        shutil.move(str(original_score_dir), "score_backup")
    
    # Create symlinks to our run directory
    os.symlink(str(run_dir / "result"), "result")
    os.symlink(str(run_dir / "score"), "score")
    
    try:
        # Set appropriate prompt
        if config["prompt_file"]:
            print(f"Setting prompt from: {config['prompt_file']}")
            if not set_prompt_from_file(config["prompt_file"]):
                return False
        
        # Generate responses
        print(f"\n[1/2] Generating responses...")
        cmd = [
            "python", "-m", "bfcl_eval", "generate",
            "--model", model_name,
            "--test-category", ",".join(categories),
            "--num-threads", str(NUM_THREADS),
            "--temperature", str(TEMPERATURE)
        ]
        
        subprocess.run(cmd, check=True)
        print("✓ Response generation complete")
        
        # Evaluate results
        print(f"\n[2/2] Evaluating results...")
        cmd = [
            "python", "-m", "bfcl_eval", "evaluate",
            "--model", model_name,
            "--test-category", ",".join(categories)
        ]
        
        subprocess.run(cmd, check=True)
        print("✓ Evaluation complete")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error: {e}")
        return False
        
    finally:
        # Restore original directories
        os.unlink("result")
        os.unlink("score")
        
        if Path("result_backup").exists():
            shutil.move("result_backup", "result")
        if Path("score_backup").exists():
            shutil.move("score_backup", "score")

def load_results(model_name, categories, blacklist, run_dir=None):
    """Load evaluation results excluding blacklisted tests"""
    results = {}
    if run_dir:
        score_dir = run_dir / "score" / model_name.replace("/", "_")
    else:
        score_dir = Path("score") / model_name.replace("/", "_")
    
    for category in categories:
        score_file = score_dir / f"BFCL_v3_{category}_score.json"
        if score_file.exists():
            with open(score_file, 'r') as f:
                lines = f.readlines()
                if not lines:
                    continue
                    
                # First line has summary
                summary = json.loads(lines[0])
                
                # Count non-blacklisted results
                total_clean = 0
                correct_clean = 0
                
                # Process individual test results
                for line in lines[1:]:
                    if line.strip():
                        result = json.loads(line)
                        test_id = result.get("id", "")
                        
                        # Skip blacklisted tests
                        if test_id in blacklist:
                            continue
                            
                        total_clean += 1
                        if result.get("valid", False):
                            correct_clean += 1
                
                # Calculate clean accuracy
                if total_clean > 0:
                    accuracy_clean = (correct_clean / total_clean) * 100
                else:
                    accuracy_clean = 0
                    
                results[category] = {
                    "total": total_clean,
                    "correct": correct_clean,
                    "accuracy": accuracy_clean,
                    "blacklisted_count": summary["total_count"] - total_clean
                }
    
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
    print(f"Configurations: baseline")
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
    
    try:
        # Run baseline configuration only
        config_name = "baseline"
        
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
                # Load and save results
                run_dir = get_run_directory(config_name, run_num)
                results = load_results(BASE_MODEL, ALL_TEST_CATEGORIES, blacklist, run_dir)
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
        
        # Final analysis
        print("\n" + "="*60)
        print("FINAL BASELINE STATISTICS")
        print("="*60)
        
        final_stats = analyze_stochastic_results(config_name, ALL_TEST_CATEGORIES)
        
        # Save final report
        report = {
            "config": config_name,
            "model": BASE_MODEL,
            "num_runs": NUM_RUNS,
            "temperature": TEMPERATURE,
            "timestamp": datetime.now().isoformat(),
            "blacklisted_count": len(blacklist),
            "completed_runs": len(get_completed_runs(config_name, ALL_TEST_CATEGORIES)),
            "statistics": final_stats
        }
        
        report_file = RESULTS_DIR / f"{config_name}_stochastic_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        # Print summary
        for category, stat in final_stats.items():
            if 'runs' in stat and stat['runs'] > 0:
                print(f"\n{category}:")
                print(f"  Mean: {stat['mean']:.2f}%")
                print(f"  Std Dev: {stat['std']:.2f}%")
                print(f"  95% CI: [{stat['95_ci_lower']:.2f}%, {stat['95_ci_upper']:.2f}%]")
                print(f"  Range: [{stat['min']:.2f}%, {stat['max']:.2f}%]")
                print(f"  Runs: {stat['runs']}")
        
        print(f"\n✓ Report saved to {report_file}")
                        test_acc = test_results[category]["accuracy"]
                        improvement = test_acc - base_acc
                        
                        # Highlight if this was a target category
                        target_marker = "🎯 " if category in PROMPT_CONFIGS[config_name]["target_categories"] else "   "
                        status = "✓" if improvement > 0 else "✗" if improvement < -5 else "="
                        
                        print(f"{target_marker}{status} {category}: {base_acc:.1f}% → {test_acc:.1f}% ({improvement:+.1f}%)")
        
        # Phase 4: Generate comprehensive report
        report = save_fan_report(all_runs_data)
        
        # Phase 5: Summary
        print("\n" + "="*60)
        print("FAN APPROACH SUMMARY")
        print("="*60)
        
        winners = []
        for key, value in report["summary"].items():
            if value and value["improvement"] > 5:
                winners.append(f"{key}: {value['config']} (+{value['improvement']:.1f}%)")
        
        if winners:
            print("🎯 WINNING YELLIES:")
            for winner in winners:
                print(f"  - {winner}")
        else:
            print("❌ No significant improvements found")
        
        print("\nKey Learning: Individual yellies can be tested without catastrophic failure")
        
    finally:
        # Always restore original prompt
        restore_original_prompt(backup_file)
        print("\n✓ Test complete, original prompt restored")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fan Approach Test - Test isolated yellies")
    parser.add_argument(
        "--num-threads", 
        type=int, 
        default=1,
        help="Number of threads for parallel API calls (default: 1)"
    )
    args = parser.parse_args()
    
    # Set global NUM_THREADS from command line
    NUM_THREADS = args.num_threads
    print(f"Using {NUM_THREADS} thread(s) for API calls")
    
    main()