"""
Build script para empaquetar el sidecar de estrategia como strategy-sidecar.
Uso: cd sidecar && python build.py
"""
from pathlib import Path
import os

import shutil

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

# =========================================================================
# FASE 2: Copiar a frontend/src-tauri/binaries/sidecar/ + renombrar exe
# =========================================================================
sidecar_dir = Path(__file__).resolve().parent
compiled_dir = sidecar_dir / "dist" / "strategy-sidecar"
target_binaries_dir = REPO_ROOT / "frontend" / "src-tauri" / "binaries" / "sidecar"

print(f"Limpiando directorio destino anterior si existe: {target_binaries_dir}")
if target_binaries_dir.exists():
    shutil.rmtree(target_binaries_dir)
target_binaries_dir.mkdir(parents=True, exist_ok=True)

print(f"Copiando compilado desde {compiled_dir} a {target_binaries_dir}...")
for item in compiled_dir.iterdir():
    d = target_binaries_dir / item.name
    if item.is_dir():
        shutil.copytree(item, d)
    else:
        shutil.copy2(item, d)

# Tauri busca el ejecutable con el target triple en Windows (x86_64-pc-windows-msvc)
exe_source = target_binaries_dir / "strategy-sidecar.exe"
exe_target = target_binaries_dir / "strategy-sidecar-x86_64-pc-windows-msvc.exe"

if exe_source.exists():
    print(f"Renombrando {exe_source} a {exe_target} para Tauri sidecar...")
    shutil.move(str(exe_source), str(exe_target))
else:
    print("[-] ADVERTENCIA: No se encontró strategy-sidecar.exe en la carpeta de binaries.")

print("[+] Proceso de la Fase 2 completado exitosamente.")