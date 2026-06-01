#!/usr/bin/env python3
"""Run benchmark V2 with MiniMax"""
import subprocess, sys, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

api_key = "sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0"

cmd = [
    sys.executable, "benchmark_llm_v2.py",
    "--model", "MiniMax-M2.7",
    "--base-url", "https://api.minimaxi.chat/v1",
    "--api-key", api_key,
    "--output-dir", "./benchmark_reports"
]

print(f"Running: {' '.join(cmd)}")
result = subprocess.run(cmd, capture_output=False, text=True)
sys.exit(result.returncode)