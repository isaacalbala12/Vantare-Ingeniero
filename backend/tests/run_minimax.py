#!/usr/bin/env python3
"""Run MiniMax benchmark with provided API key."""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
py_path = os.path.join(os.path.dirname(sys.executable), "python.exe")

api_key = "sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0"

cmd = [py_path, "-m", "tests.benchmark_minimax",
       "--api-key", api_key,
       "--model", "MiniMax/M2.7"]

print(f"Launching: python -m tests.benchmark_minimax")
result = subprocess.run(cmd, cwd=os.getcwd())
sys.exit(result.returncode)