#!/usr/bin/env python3
"""Wrapper para benchmark_llm.py con base-url correcto."""
import subprocess, sys, os

# Change to backend directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Get sys.executable path
py_path = os.path.join(os.path.dirname(sys.executable), "python.exe")

# Correct LM Studio endpoint (no /api/v1)
model = "smollm3-3b-128k"
base_url = "http://192.168.1.41:1234"  # NOT http://192.168.1.41:1234/api/v1
output_dir = "./benchmark_reports"

cmd = [py_path, "-m", "tests.benchmark_llm", 
       "--model", model,
       "--base-url", base_url,
       "--output-dir", output_dir]

print(f"Launching: {' '.join(cmd)}")
result = subprocess.run(cmd, cwd=os.getcwd())
sys.exit(result.returncode)