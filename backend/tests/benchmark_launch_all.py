#!/usr/bin/env python3
"""
Run LOCAL LM Studio benchmarks SEQUENTIALLY (to avoid model reload issues)
"""

import subprocess, time, os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

models = [
    "smollm3-3b-128k",
    "unsloth-granite-4.1-3b",
    "ministral-3-3b",
    "granite-4.1-8b",
    "lfm2.5-8b-a1b",
    "greg-0-mini",
    "gemma-4-e4b-it-coder",
]

print("="*60)
print("LAUNCHING BENCHMARKS SEQUENTIALLY")
print("="*60)

for i, model in enumerate(models, 1):
    print(f"\n[{i}/{len(models)}] Running: {model}")
    print("-"*40)
    
    result = subprocess.run([
        sys.executable, 
        "benchmark_v2_runner.py", 
        model
    ], capture_output=False)
    
    print(f"  Finished with code {result.returncode}")
    print(f"  Next model in 5s...")
    time.sleep(5)

print("\n" + "="*60)
print("ALL BENCHMARKS COMPLETE")
print("="*60)