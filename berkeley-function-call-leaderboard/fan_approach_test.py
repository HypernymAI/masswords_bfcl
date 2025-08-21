#!/usr/bin/env python3
"""
Fan Approach Test - Testing Individual Yellies vs Baseline vs Kitchen Sink
Tests multiple prompt configurations to identify which specific interventions help
"""

import os
import sys
import json
import shutil
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

# Base configuration
BASE_MODEL = "azure/Meta-Llama-31-8B-Instruct-2"
RESULTS_DIR = Path("fan_test_results")
PROMPTS_BASE_DIR = Path("/Users/fieldempress/Desktop/source/hypernym/llama-prompt-ops/bfcl_optimization/yellies_experiment/prompts")
NUM_THREADS = 1  # Default, can be overridden by command line

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

def run_bfcl_test(config_name, categories_override=None):
    """Run BFCL evaluation for a specific configuration"""
    config = PROMPT_CONFIGS[config_name]
    model_name = BASE_MODEL + config["suffix"]
    categories = categories_override or config["target_categories"]
    
    print(f"\n{'='*60}")
    print(f"Testing: {config_name}")
    print(f"Model: {model_name}")
    print(f"Description: {config['description']}")
    print(f"Target categories: {', '.join(categories)}")
    print(f"Expected: {config['expected_improvement']}")
    print(f"{'='*60}")
    
    # Check if already cached
    if check_cached_results(model_name, categories):
        print("✓ Using cached results")
        # Still run evaluate to ensure score files exist
        cmd = [
            "python", "-m", "bfcl_eval", "evaluate",
            "--model", model_name,
            "--test-category", ",".join(categories)
        ]
        try:
            subprocess.run(cmd, check=True)
        except:
            pass  # Ignore errors for categories that don't exist
        return True
    
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
        "--num-threads", str(NUM_THREADS)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✓ Response generation complete")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error generating responses: {e}")
        return False
    
    # Evaluate results
    print(f"\n[2/2] Evaluating results...")
    cmd = [
        "python", "-m", "bfcl_eval", "evaluate",
        "--model", model_name,
        "--test-category", ",".join(categories)
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✓ Evaluation complete")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error evaluating results: {e}")
        # Continue anyway - some categories might not exist
    
    return True

def load_results(model_name, categories):
    """Load evaluation results"""
    results = {}
    score_dir = Path("score") / model_name.replace("/", "_")
    
    for category in categories:
        score_file = score_dir / f"BFCL_v3_{category}_score.json"
        if score_file.exists():
            with open(score_file, 'r') as f:
                first_line = f.readline()
                if first_line:
                    data = json.loads(first_line)
                    total = data["total_count"]
                    correct = data["correct_count"]
                    accuracy = data["accuracy"] * 100
                    results[category] = {
                        "total": total,
                        "correct": correct,
                        "accuracy": accuracy
                    }
    
    return results

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

def main():
    """Run the fan approach test"""
    print("BFCL Fan Approach Test")
    print("======================")
    print("Testing individual yellies to identify specific improvements")
    
    # Create results directory
    RESULTS_DIR.mkdir(exist_ok=True)
    
    # Backup original prompt
    prompt_file, backup_file = backup_original_prompt()
    
    # Results storage
    all_results = {}
    
    try:
        # Phase 1: Test baseline (should be cached)
        if run_bfcl_test("baseline"):
            baseline_results = load_results(BASE_MODEL, PROMPT_CONFIGS["baseline"]["target_categories"])
            all_results["baseline"] = baseline_results
            
            print("\n" + "="*60)
            print("BASELINE RESULTS")
            print("="*60)
            for cat, res in baseline_results.items():
                print(f"{cat}: {res['accuracy']:.1f}%")
        
        # Phase 2: Show kitchen sink results (should be cached)
        print("\n" + "="*60)
        print("KITCHEN SINK REFERENCE (Already tested)")
        print("="*60)
        if check_cached_results(BASE_MODEL + "-yellies", PROMPT_CONFIGS["kitchen_sink"]["target_categories"]):
            kitchen_results = load_results(BASE_MODEL + "-yellies", PROMPT_CONFIGS["kitchen_sink"]["target_categories"])
            all_results["kitchen_sink"] = kitchen_results
            compare_fan_results(baseline_results, kitchen_results, "kitchen_sink")
        
        # Phase 3: Test each isolated yellie
        print("\n" + "="*60)
        print("ISOLATED YELLIE TESTING")
        print("="*60)
        
        isolated_configs = ["anti_verbosity", "format_strict", "param_precision", "zero_output"]
        
        # ALL categories to test - same for every yellie to see side effects!
        ALL_TEST_CATEGORIES = ["simple", "irrelevance", "live_irrelevance", "live_simple", "live_relevance"]
        
        for config_name in isolated_configs:
            # Restore baseline prompt first
            restore_original_prompt(backup_file)
            
            # Test on ALL categories, not just target!
            if run_bfcl_test(config_name, categories_override=ALL_TEST_CATEGORIES):
                test_results = load_results(
                    BASE_MODEL + PROMPT_CONFIGS[config_name]["suffix"],
                    ALL_TEST_CATEGORIES
                )
                all_results[config_name] = test_results
                
                # Show results for ALL categories
                print(f"\n{'='*60}")
                print(f"FULL RESULTS: {config_name}")
                print(f"Target was: {PROMPT_CONFIGS[config_name]['target_categories']}")
                print(f"{'='*60}")
                
                for category in ALL_TEST_CATEGORIES:
                    if category in baseline_results and category in test_results:
                        base_acc = baseline_results[category]["accuracy"]
                        test_acc = test_results[category]["accuracy"]
                        improvement = test_acc - base_acc
                        
                        # Highlight if this was a target category
                        target_marker = "🎯 " if category in PROMPT_CONFIGS[config_name]["target_categories"] else "   "
                        status = "✓" if improvement > 0 else "✗" if improvement < -5 else "="
                        
                        print(f"{target_marker}{status} {category}: {base_acc:.1f}% → {test_acc:.1f}% ({improvement:+.1f}%)")
        
        # Phase 4: Generate comprehensive report
        report = save_fan_report(all_results)
        
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