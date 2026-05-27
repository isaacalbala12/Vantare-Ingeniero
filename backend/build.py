"""
Build script para empaquetar backend FastAPI como vantare-engine.exe.
Uso: cd backend && pyinstaller build.py
"""
import sys
from pathlib import Path

import PyInstaller.__main__

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "src"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

args = [
    "--onedir",
    "--noconsole",
    "--name=vantare-engine",
    "--add-data", f"{SHARED_TELEMETRY}{Path.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{Path.pathsep}shared_strategy",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--distpath=./dist",
    "--workpath=./build",
]

PYLMU_DIR = SHARED_TELEMETRY / "shared_telemetry" / "pyLMUSharedMemory"
for pyd_file in PYLMU_DIR.glob("*.pyd"):
    args.extend(["--add-binary", f"{str(pyd_file)}{Path.pathsep}shared_telemetry/pyLMUSharedMemory"])

args.append("src/main.py")

PyInstaller.__main__.run(args)
