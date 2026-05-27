"""
Build script para empaquetar el sidecar de estrategia como strategy-sidecar.
Uso: cd sidecar && python build.py
"""
from pathlib import Path
import os

import PyInstaller.__main__

REPO_ROOT = Path(__file__).resolve().parent.parent

# Las librerías están en shared-telemetry/shared_telemetry/ y shared-strategy/src/
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "shared_telemetry"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

# Verificar que existen antes de continuar
if not SHARED_TELEMETRY.exists():
    print(f"ADVERTENCIA: {SHARED_TELEMETRY} no existe")
if not SHARED_STRATEGY.exists():
    print(f"ADVERTENCIA: {SHARED_STRATEGY} no existe")

args = [
    "--onedir",
    "--noconsole",
    "--name=strategy-sidecar",
    "--add-data", f"{SHARED_TELEMETRY}{os.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{os.pathsep}shared_strategy",
    "--distpath=./dist",
    "--workpath=./build",
]

args.append("src/sidecar/main.py")

PyInstaller.__main__.run(args)