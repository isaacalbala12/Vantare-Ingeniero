#!/usr/bin/env python3
"""Wrapper para ejecutar benchmark_minimax_full.py"""
import subprocess, sys, os

# La API key debe estar en la variable de entorno MINIMAX_API_KEY
api_key = os.environ.get("MINIMAX_API_KEY")
if not api_key:
    # Si no hay env, crear un script temporal sin la key expuesta
    print("ERROR: MINIMAX_API_KEY no está configurada")
    print("Ejecuta: set MINIMAX_API_KEY=tu-key && python run_minimax_full.py")
    sys.exit(1)

script_dir = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.join(script_dir, "benchmark_minimax_full.py")

result = subprocess.run(
    [sys.executable, script_path, "--api-key", api_key],
    cwd=script_dir
)
sys.exit(result.returncode)