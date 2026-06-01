#!/usr/bin/env python3
"""Wrapper para benchmark qwen3.5-4b."""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
py_path = os.path.join(os.path.dirname(sys.executable), "python.exe")

model = "qwen3.5-4b"
base_url = "http://192.168.1.41:1234"

cmd = [py_path, "-m", "tests.benchmark_llm", 
       "--model", model,
       "--base-url", base_url,
       "--output-dir", "./benchmark_reports"]

print(f"Launching: {' '.join(cmd)}")
result = subprocess.run(cmd, cwd=os.getcwd())
sys.exit(result.returncode)