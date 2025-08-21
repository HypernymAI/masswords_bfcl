#!/usr/bin/env python3
"""
BFCL Stochastic Results to SQLite Database Converter
Imports fan approach stochastic test results (50 runs per config)
Only imports configurations with all 50 runs complete
"""

import json
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
import argparse
import sys
import numpy as np
from typing import Dict, List, Any, Optional

class BFCLStochasticDatabase:
    def __init__(self, db_path: str = "bfcl_stochastic_results.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Enable foreign keys and JSON functions
        self.cursor.execute("PRAGMA foreign_keys = ON")
        
        self._create_schema()
    
    def _create_schema(self):
        """Create the database schema for stochastic BFCL results"""
        
        # Configurations table - tracks different prompt configurations
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS configurations (
            config_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            suffix TEXT NOT NULL,
            description TEXT,
            prompt_file TEXT,
            prompt_hash TEXT,
            target_categories TEXT,  -- JSON array
            expected_improvement TEXT,
            num_runs INTEGER,
            temperature REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Runs table - individual runs for each configuration
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            run_number INTEGER NOT NULL,
            model_name TEXT NOT NULL,
            timestamp DATETIME,
            categories_tested TEXT,  -- JSON array
            FOREIGN KEY (config_id) REFERENCES configurations(config_id),
            UNIQUE(config_id, run_number)
        )
        """)
        
        # Prompts table - stores different prompt versions
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            prompt_id INTEGER PRIMARY KEY AUTOINCREMENT,
            prompt_hash TEXT UNIQUE NOT NULL,
            content TEXT NOT NULL,
            type TEXT CHECK(type IN ('system', 'user', 'combined')),
            version TEXT,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Test cases table - the actual BFCL test definitions
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_cases (
            test_id TEXT PRIMARY KEY,  -- e.g., 'simple_0'
            category TEXT NOT NULL,
            question JSON NOT NULL,  -- Full question structure
            functions JSON NOT NULL,  -- Function definitions
            expected_result JSON,  -- From possible_answers if available
            metadata JSON
        )
        """)
        
        # Results table - model outputs for each test
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            result_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            test_id TEXT NOT NULL,
            category TEXT NOT NULL,
            model_output TEXT NOT NULL,  -- Raw model response
            output_type TEXT,  -- 'string', 'list', 'dict', etc.
            is_correct BOOLEAN,
            is_blacklisted BOOLEAN DEFAULT 0,
            error_type TEXT,
            error_message TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            FOREIGN KEY (test_id) REFERENCES test_cases(test_id)
        )
        """)
        
        # Run accuracies table - accuracy per run/category
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_accuracies (
            accuracy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            total_tests INTEGER,
            correct_tests INTEGER,
            accuracy REAL,
            blacklisted_count INTEGER,
            FOREIGN KEY (run_id) REFERENCES runs(run_id),
            UNIQUE(run_id, category)
        )
        """)
        
        # Aggregate statistics table - summary stats per configuration
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS aggregate_stats (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            total_tests INTEGER,
            mean_accuracy REAL,
            std_accuracy REAL,
            min_accuracy REAL,
            max_accuracy REAL,
            ci_95_lower REAL,
            ci_95_upper REAL,
            num_runs INTEGER,
            FOREIGN KEY (config_id) REFERENCES configurations(config_id),
            UNIQUE(config_id, category)
        )
        """)
        
        # Create indexes for better query performance
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_run ON results(run_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_test ON results(test_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_correct ON results(is_correct)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_results_category ON results(category)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_runs_config ON runs(config_id)")
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_aggregate_config ON aggregate_stats(config_id)")
        
        self.conn.commit()
    
    def import_stochastic_config(self, 
                                config_name: str,
                                base_dir: Path = Path("fan_stochastic_results"),
                                blacklist_db: Path = Path("content_filter_blacklist.db"),
                                required_runs: int = 50) -> bool:
        """Import a stochastic configuration only if it has all required runs complete"""
        
        config_dir = base_dir / config_name
        if not config_dir.exists():
            print(f"Configuration directory not found: {config_dir}")
            return False
        
        # Check if we have all required runs
        completed_runs = []
        for run_num in range(1, required_runs + 1):
            run_dir = config_dir / f"run_{run_num:03d}"
            results_file = run_dir / "results.json"
            if results_file.exists():
                completed_runs.append(run_num)
        
        if len(completed_runs) < required_runs:
            print(f"Configuration '{config_name}' only has {len(completed_runs)}/{required_runs} runs complete. Skipping.")
            return False
        
        print(f"Configuration '{config_name}' has all {required_runs} runs complete. Importing...")
        
        # Load blacklist
        blacklist = set()
        if blacklist_db.exists():
            conn = sqlite3.connect(blacklist_db)
            cursor = conn.cursor()
            cursor.execute("SELECT test_id FROM content_filter_blacklist WHERE is_deterministic = 1")
            blacklist = {row[0] for row in cursor.fetchall()}
            conn.close()
            print(f"Loaded {len(blacklist)} blacklisted test IDs")
        
        # Get configuration info from a sample run
        sample_results = config_dir / "run_001" / "results.json"
        with open(sample_results) as f:
            sample_data = json.load(f)
        
        # Create configuration record
        from fan_approach_stochastic_test import PROMPT_CONFIGS
        config_info = PROMPT_CONFIGS.get(config_name, {})
        
        prompt_hash = None
        if config_info.get("prompt_file"):
            prompt_file = Path(config_info["prompt_file"])
            if prompt_file.exists():
                with open(prompt_file) as f:
                    prompt_content = f.read()
                    prompt_hash = hashlib.sha256(prompt_content.encode()).hexdigest()[:16]
                    
                    self.cursor.execute("""
                    INSERT OR IGNORE INTO prompts (prompt_hash, content, type, version)
                    VALUES (?, ?, 'system', ?)
                    """, (prompt_hash, prompt_content, config_name))
        
        self.cursor.execute("""
        INSERT OR REPLACE INTO configurations 
        (name, suffix, description, prompt_file, prompt_hash, target_categories, 
         expected_improvement, num_runs, temperature)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (config_name, config_info.get("suffix", ""), config_info.get("description", ""),
              str(config_info.get("prompt_file", "")), prompt_hash,
              json.dumps(config_info.get("target_categories", [])),
              config_info.get("expected_improvement", ""), required_runs,
              sample_data.get("temperature", 0.3)))
        
        config_id = self.cursor.lastrowid
        
        # Import each run
        categories_set = set()
        for run_num in completed_runs:
            run_dir = config_dir / f"run_{run_num:03d}"
            results_file = run_dir / "results.json"
            
            with open(results_file) as f:
                run_data = json.load(f)
            
            # Create run record
            self.cursor.execute("""
            INSERT INTO runs (config_id, run_number, model_name, timestamp, categories_tested)
            VALUES (?, ?, ?, ?, ?)
            """, (config_id, run_num, run_data["model"], run_data["timestamp"],
                  json.dumps(list(run_data["results"].keys()))))
            
            run_id = self.cursor.lastrowid
            
            # Import results for this run
            for category, cat_results in run_data["results"].items():
                categories_set.add(category)
                total = cat_results["total"]
                correct = cat_results["correct"]
                accuracy = cat_results["accuracy"]
                blacklisted_count = cat_results.get("blacklisted_count", 0)
                
                # Store run accuracy data
                self.cursor.execute("""
                INSERT OR REPLACE INTO run_accuracies 
                (run_id, category, total_tests, correct_tests, accuracy, blacklisted_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (run_id, category, total, correct, accuracy, blacklisted_count))
        
        # Calculate and store aggregate statistics
        # If categories_set is empty (e.g., for baseline with empty results.json), 
        # use the expected categories from config
        if not categories_set:
            from fan_approach_stochastic_test import PROMPT_CONFIGS
            if config_name in PROMPT_CONFIGS:
                categories_set = set(PROMPT_CONFIGS[config_name].get("target_categories", []))
            if not categories_set:  # If still empty, use all categories
                categories_set = {"simple", "irrelevance", "live_irrelevance", "live_simple", "live_relevance"}
        
        self._calculate_aggregate_stats(config_id, config_name, categories_set)
        
        self.conn.commit()
        print(f"Successfully imported configuration '{config_name}'")
        return True
    
    def _calculate_aggregate_stats(self, config_id: int, config_name: str, categories: set):
        """Calculate aggregate statistics across all runs for a configuration"""
        
        config_dir = Path("fan_stochastic_results") / config_name
        
        # Get model name from config
        from fan_approach_stochastic_test import PROMPT_CONFIGS, BASE_MODEL
        suffix = PROMPT_CONFIGS[config_name]["suffix"]
        
        for category in categories:
            accuracies = []
            total_tests = None
            
            # Collect accuracy from score files directly
            for run_num in range(1, 51):  # Assuming 50 runs
                # Determine the correct score directory
                if config_name == "baseline":
                    model_dir = BASE_MODEL.replace("/", "_")
                else:
                    model_dir = (BASE_MODEL + suffix).replace("/", "_")
                
                score_file = config_dir / f"run_{run_num:03d}" / "score" / model_dir / f"BFCL_v3_{category}_score.json"
                if score_file.exists():
                    with open(score_file) as f:
                        first_line = f.readline()
                        if first_line:
                            summary = json.loads(first_line)
                            accuracy = summary.get("accuracy", 0) * 100  # Convert to percentage
                            accuracies.append(accuracy)
                            if total_tests is None:
                                total_tests = summary.get("total_count", 0)
                            
                            # Also update the run_accuracies table with correct score data
                            self.cursor.execute("""
                            UPDATE run_accuracies 
                            SET accuracy = ?, total_tests = ?, correct_tests = ?
                            WHERE run_id = (
                                SELECT run_id FROM runs 
                                WHERE config_id = ? AND run_number = ?
                            ) AND category = ?
                            """, (summary.get("accuracy", 0), 
                                  summary.get("total_count", 0),
                                  summary.get("correct_count", 0),
                                  config_id, run_num, category))
            
            if accuracies:
                # Calculate statistics
                mean_acc = np.mean(accuracies)
                std_acc = np.std(accuracies)
                min_acc = np.min(accuracies)
                max_acc = np.max(accuracies)
                ci_lower = np.percentile(accuracies, 2.5)
                ci_upper = np.percentile(accuracies, 97.5)
                
                self.cursor.execute("""
                INSERT OR REPLACE INTO aggregate_stats 
                (config_id, category, total_tests, mean_accuracy, std_accuracy, 
                 min_accuracy, max_accuracy, ci_95_lower, ci_95_upper, num_runs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (config_id, category, total_tests, mean_acc, std_acc,
                      min_acc, max_acc, ci_lower, ci_upper, len(accuracies)))
                
                print(f"  {category}: {mean_acc:.1f}% ± {std_acc:.1f}% ({len(accuracies)} runs)")
    
    def close(self):
        """Close the database connection"""
        self.conn.close()

def main():
    parser = argparse.ArgumentParser(description="Import BFCL stochastic results into SQLite for introspection")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import stochastic test results")
    import_parser.add_argument("--config", help="Specific configuration to import (default: all with 50 runs)")
    import_parser.add_argument("--db", default="bfcl_stochastic_results.db", help="Database file")
    import_parser.add_argument("--required-runs", type=int, default=50, help="Required number of runs (default: 50)")
    
    # Query examples command
    examples_parser = subparsers.add_parser("examples", help="Show example SQL queries")
    
    args = parser.parse_args()
    
    if args.command == "import":
        db = BFCLStochasticDatabase(args.db)
        
        # Import specific config or all available
        if args.config:
            configs = [args.config]
        else:
            # Check all available configurations
            configs = ["baseline", "anti_verbosity", "format_strict", "param_precision", "zero_output", "kitchen_sink"]
        
        imported = 0
        for config in configs:
            if db.import_stochastic_config(config, required_runs=args.required_runs):
                imported += 1
        
        db.close()
        
        print(f"\nImported {imported} configurations")
        print(f"Database saved to: {args.db}")
        print(f"Open with: sqlite3 {args.db}")
    
    elif args.command == "examples":
        print("""
BFCL Stochastic Results - Example Queries
=========================================

1. View aggregate statistics for all configurations:
   SELECT c.name, s.category, 
          s.mean_accuracy, s.std_accuracy,
          s.ci_95_lower, s.ci_95_upper,
          s.num_runs
   FROM configurations c
   JOIN aggregate_stats s ON c.config_id = s.config_id
   ORDER BY c.name, s.category;

2. Compare baseline vs other configs:
   SELECT 
       b.category,
       b.mean_accuracy as baseline_mean,
       t.name as test_config,
       t.mean_accuracy as test_mean,
       ROUND(t.mean_accuracy - b.mean_accuracy, 2) as improvement,
       CASE WHEN t.ci_95_lower > b.ci_95_upper THEN '***' 
            WHEN t.ci_95_upper < b.ci_95_lower THEN '!!!' 
            ELSE '' END as significant
   FROM 
       (SELECT s.* FROM aggregate_stats s 
        JOIN configurations c ON s.config_id = c.config_id 
        WHERE c.name = 'baseline') b
   JOIN
       (SELECT c.name, s.* FROM aggregate_stats s 
        JOIN configurations c ON s.config_id = c.config_id 
        WHERE c.name != 'baseline') t
   ON b.category = t.category
   ORDER BY b.category, improvement DESC;

3. Find best config for each category:
   SELECT category, name as best_config, mean_accuracy, std_accuracy
   FROM (
       SELECT s.category, c.name, s.mean_accuracy, s.std_accuracy,
              ROW_NUMBER() OVER (PARTITION BY s.category ORDER BY s.mean_accuracy DESC) as rn
       FROM aggregate_stats s
       JOIN configurations c ON s.config_id = c.config_id
   )
   WHERE rn = 1;

4. Check statistical significance:
   SELECT c1.name as config1, c2.name as config2, s1.category,
          s1.mean_accuracy as mean1, s2.mean_accuracy as mean2,
          ROUND(s2.mean_accuracy - s1.mean_accuracy, 2) as diff,
          CASE 
              WHEN s2.ci_95_lower > s1.ci_95_upper THEN 'Significant improvement'
              WHEN s2.ci_95_upper < s1.ci_95_lower THEN 'Significant degradation'
              ELSE 'Not significant'
          END as significance
   FROM aggregate_stats s1
   JOIN aggregate_stats s2 ON s1.category = s2.category
   JOIN configurations c1 ON s1.config_id = c1.config_id
   JOIN configurations c2 ON s2.config_id = c2.config_id
   WHERE c1.name = 'baseline' AND c2.name != 'baseline';

5. View run-level data:
   SELECT r.run_number, r.timestamp, r.categories_tested
   FROM runs r
   JOIN configurations c ON r.config_id = c.config_id
   WHERE c.name = 'baseline'
   ORDER BY r.run_number;

6. Export results for further analysis:
   .mode csv
   .output stochastic_results.csv
   SELECT * FROM aggregate_stats;
   .output stdout
   .mode list
""")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()