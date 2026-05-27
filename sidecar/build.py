"""
Build script para empaquetar el sidecar de estrategia como strategy-sidecar.exe.
Uso: cd sidecar && pyinstaller build.py
"""
from pathlib import Path

import PyInstaller.__main__

SIDECAR_SRC = Path(__file__).resolve().parent / "src"
REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "src"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

import os

args = [
    "--onedir",
    "--noconsole",
    "--name=strategy-sidecar",
    "--add-data", f"{SHARED_TELEMETRY}{os.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{os.pathsep}shared_strategy",
    "--distpath=./dist",
    "--workpath=./build",
]

PYLMU_DIR = SHARED_TELEMETRY / "shared_telemetry" / "pyLMUSharedMemory"
for pyd_file in PYLMU_DIR.glob("*.pyd"):
    args.extend(["--add-binary", f"{str(pyd_file)}{os.pathsep}shared_telemetry/pyLMUSharedMemory"])

args.append("src/sidecar/main.py")

PyInstaller.__main__.run(args)