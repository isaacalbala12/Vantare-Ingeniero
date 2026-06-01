#!/usr/bin/env python3
"""Wrapper para benchmark nvidia_nvidia-nemotron-nano-9b-v2."""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
py_path = os.path.join(os.path.dirname(sys.executable), "python.exe")

model = "nvidia_nvidia-nemotron-nano-9b-v2"
base_url = "http://192.168.1.41:1234"

cmd = [py_path, "-m", "tests.benchmark_llm", 
       "--model", model,
       "--base-url", base_url,
       "--output-dir", "./benchmark_reports"]

print(f"Launching: {' '.join(cmd)}")
result = subprocess.run(cmd, cwd=os.getcwd())
sys.exit(result.returncode)