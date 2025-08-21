#!/usr/bin/env python3
"""
Create a blacklist database of test IDs that fail due to content filtering.
Scans all result files for content filter errors and stores them in a SQLite database.
"""
import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime

def find_project_root():
    """Find the BFCL project root by looking for key markers."""
    current = Path.cwd()
    
    # Look for BFCL markers
    markers = ['bfcl_eval', 'README.md', 'setup.py']
    
    while current != current.parent:
        if all((current / marker).exists() for marker in markers[:2]):  # At least bfcl_eval and README
            return current
        current = current.parent
    
    # Fallback to current directory
    return Path.cwd()

def create_blacklist_db(db_path):
    """Create the blacklist database schema."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS content_filter_blacklist (
        test_id TEXT PRIMARY KEY,
        category TEXT NOT NULL,
        experiment_count INTEGER NOT NULL,
        total_experiments INTEGER NOT NULL,
        is_deterministic INTEGER NOT NULL,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_category ON content_filter_blacklist(category)
    """)
    
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_deterministic ON content_filter_blacklist(is_deterministic)
    """)
    
    conn.commit()
    return conn

def scan_bfcl_results_db(root_dir):
    """Scan bfcl_results.db for content filter errors and verify they're deterministic."""
    db_path = root_dir / "bfcl_results.db"
    
    if not db_path.exists():
        print(f"No bfcl_results.db found at {db_path}")
        print("Please run BFCL tests first to generate results.")
        return {}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # First, get all experiments
    cursor.execute("SELECT experiment_id, name FROM experiments")
    experiments = cursor.fetchall()
    total_experiments = len(experiments)
    
    print(f"Found {total_experiments} experiments in bfcl_results.db")
    
    # Get all content filter errors grouped by test_id
    cursor.execute("""
    SELECT 
        r.test_id,
        tc.category,
        COUNT(DISTINCT r.experiment_id) as experiment_count,
        GROUP_CONCAT(DISTINCT e.name) as experiment_names
    FROM results r
    JOIN test_cases tc ON r.test_id = tc.test_id
    JOIN experiments e ON r.experiment_id = e.experiment_id
    WHERE r.model_output LIKE '%content_filter%' 
       OR r.model_output LIKE '%content management policy%'
    GROUP BY r.test_id, tc.category
    """)
    
    blacklisted_tests = {}
    
    for row in cursor.fetchall():
        test_id, category, experiment_count, experiment_names = row
        
        # Only include if it fails in ALL experiments (deterministic)
        is_deterministic = (experiment_count == total_experiments)
        
        blacklisted_tests[test_id] = {
            "category": category,
            "experiment_count": experiment_count,
            "total_experiments": total_experiments,
            "is_deterministic": is_deterministic,
            "experiment_names": experiment_names
        }
    
    conn.close()
    return blacklisted_tests

def main():
    """Main function to create content filter blacklist."""
    # Find project root
    root_dir = find_project_root()
    print(f"Project root: {root_dir}")
    
    # Create database
    db_path = root_dir / "content_filter_blacklist.db"
    conn = create_blacklist_db(db_path)
    cursor = conn.cursor()
    
    # Scan bfcl_results.db for blacklisted tests
    blacklisted_tests = scan_bfcl_results_db(root_dir)
    
    if not blacklisted_tests:
        print("No content filter errors found in bfcl_results.db")
        return
    
    # Insert into database
    deterministic_count = 0
    for test_id, info in blacklisted_tests.items():
        cursor.execute("""
        INSERT OR REPLACE INTO content_filter_blacklist 
        (test_id, category, experiment_count, total_experiments, is_deterministic)
        VALUES (?, ?, ?, ?, ?)
        """, (
            test_id,
            info["category"],
            info["experiment_count"],
            info["total_experiments"],
            info["is_deterministic"]
        ))
        
        if info["is_deterministic"]:
            deterministic_count += 1
    
    conn.commit()
    
    # Print summary
    cursor.execute("SELECT COUNT(*) FROM content_filter_blacklist")
    total_count = cursor.fetchone()[0]
    
    print(f"\nBlacklist created at: {db_path}")
    print(f"Total content filter errors found: {total_count}")
    print(f"Deterministic failures (fail in ALL experiments): {deterministic_count}")
    
    # Show deterministic failures by category
    print("\nDeterministic content filter failures by category:")
    cursor.execute("""
    SELECT category, COUNT(*) as count 
    FROM content_filter_blacklist 
    WHERE is_deterministic = 1
    GROUP BY category 
    ORDER BY count DESC
    """)
    
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    # List all deterministic failures
    print("\nDeterministic test IDs to exclude from stochastic testing:")
    cursor.execute("""
    SELECT test_id, category 
    FROM content_filter_blacklist 
    WHERE is_deterministic = 1
    ORDER BY category, test_id
    """)
    
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]})")
    
    # Show non-deterministic ones if any
    cursor.execute("SELECT COUNT(*) FROM content_filter_blacklist WHERE is_deterministic = 0")
    non_deterministic_count = cursor.fetchone()[0]
    
    if non_deterministic_count > 0:
        print(f"\nNon-deterministic failures (only fail in some experiments): {non_deterministic_count}")
        print("These may be worth investigating further.")
    
    conn.close()

if __name__ == "__main__":
    main()