"""
Build script para empaquetar backend FastAPI como vantare-engine.
Uso: cd backend && python build.py
"""
from pathlib import Path
import os

import PyInstaller.__main__

REPO_ROOT = Path(__file__).resolve().parent.parent

# Las librerías están en shared-telemetry/shared_telemetry/ y shared-strategy/src/
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "shared_telemetry"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

args = [
    "--onedir",
    "--noconsole",
    "--name=vantare-engine",
    "--add-data", f"{SHARED_TELEMETRY}{os.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{os.pathsep}shared_strategy",
    "--paths", str(REPO_ROOT / "shared-telemetry"),
    "--paths", str(REPO_ROOT / "shared-strategy" / "src"),
    "--distpath=./dist",
    "--workpath=./build",
    # Hidden imports clave para que PyInstaller detecte los módulos
    "--hidden-import=src.config",
    "--hidden-import=src.services.lmu_api",
    "--hidden-import=src.services.strategy_service",
    "--hidden-import=src.routers.health",
    "--hidden-import=src.routers.websocket",
    "--hidden-import=src.routers.llm",
    "--hidden-import=src.intelligence.spotter",
    "--hidden-import=src.intelligence.engine",
    "--hidden-import=shared_telemetry",
    "--hidden-import=shared_strategy",
    "--hidden-import=uvicorn",
    "--hidden-import=fastapi",
    "--hidden-import=pydantic",
    "--hidden-import=pydantic_settings",
    "--hidden-import=websockets",
    "--hidden-import=watchfiles",
    "--hidden-import=msgpack",
    "--hidden-import=yaml",
    "--hidden-import=httpx",
    "--hidden-import=aiohttp",
    "--hidden-import=wave",
    "--hidden-import=onnxruntime",
    "--hidden-import=espeakng_loader",
    "--hidden-import=edge_tts",
    "--hidden-import=openai",
    "--hidden-import=sentence_transformers",
    "--hidden-import=chromadb",
]

args.append("src/main.py")

PyInstaller.__main__.run(args)