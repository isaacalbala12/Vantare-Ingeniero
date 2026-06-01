#!/usr/bin/env python3
"""
Run all 3 benchmarks in parallel with infinite tokens
"""

import subprocess, time, os, sys

# Change to tests directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

models = [
    "MiniMax-M2.7",
    "MiniMax-M3", 
    "StepFun-3.7",
]

print("="*60)
print("LAUNCHING ALL 3 BENCHMARKS IN PARALLEL")
print("="*60)

processes = []
for model in models:
    print(f"\nLaunching: {model}")
    p = subprocess.Popen([
        sys.executable, 
        "benchmark_v2_runner.py", 
        model
    ])
    processes.append((model, p))
    time.sleep(1)  # Stagger slightly

print(f"\n{len(processes)} processes launched. Waiting for completion...")
print("Monitor benchmark_results folder for outputs.")

# Wait for all
for model, p in processes:
    retcode = p.wait()
    print(f"  {model} finished with code {retcode}")

print("\n" + "="*60)
print("ALL BENCHMARKS COMPLETE")
print("="*60)