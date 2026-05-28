import os
import sys
import shutil
import subprocess
import argparse

def build():
    # Skip if no arguments (called during import)
    if len(sys.argv) < 2:
        return
    
    parser = argparse.ArgumentParser(description="Compila el backend con PyInstaller")
    parser.add_argument("--clean", action="store_true", help="Forzar limpieza de cache de PyInstaller (lento)")
    args = parser.parse_args()

    print("=== Iniciando compilación de Vantare Ingeniero IA Backend ===")
    
    # Directorio base del backend
    base_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base_dir)
    
    # Definir rutas
    src_main = os.path.join(base_dir, "src", "main.py")
    dist_dir = os.path.join(base_dir, "dist")
    
    # Paquetes locales a incluir en el path de PyInstaller
    shared_telemetry_path = os.path.abspath(os.path.join(base_dir, "..", "shared-telemetry"))
    shared_strategy_path = os.path.abspath(os.path.join(base_dir, "..", "shared-strategy"))
    
    print(f"Incluyendo path local de shared-telemetry: {shared_telemetry_path}")
    print(f"Incluyendo path local de shared-strategy: {shared_strategy_path}")
    
    # Construir comando PyInstaller
    cmd = [
        "pyinstaller",
        "--onedir",
        "--name=backend",
        "--noconsole",
        "-y",
    ]
    
    # --clean SOLO si se pasa explicitamente (evita re-analisis completo en builds iterativos)
    if args.clean:
        cmd.append("--clean")
        print("[i] Modo --clean activado: se purgará la cache de PyInstaller")
    else:
        print("[i] Usando cache de PyInstaller existente (pasa --clean para purgar)")
    
    # Excluir paquetes del entorno global que NO son dependencias del proyecto
    # PyTorch, scipy, PySide6, etc. son instalados globalmente pero no se usan
    EXCLUDED_MODULES = [
        "torch", "torchvision", "torchaudio",
        "scipy",
        "PySide6", "PySide6.Essentials", "PySide6.Addons", "shiboken6",
        "streamlit",
        "av",
        "flask",
        "transformers",
        "optimum", "optimum.onnx",
        "matplotlib", "pandas",
        "plotly", "altair", "pydeck",
        "PIL",
        "sympy", "networkx",
        "aider_chat", "litellm",
        "sqlfluff", "ruff", "pytest",
        "sounddevice", "soundfile",
        "faster_whisper",
        "pyqtgraph",
        "ralph_workflow",
        "mixpanel", "posthog",
        "notebook", "jupyter",
        "tensorflow", "keras", "sklearn",
        "django", "celery", "redis",
    ]
    for mod in EXCLUDED_MODULES:
        cmd.append(f"--exclude-module={mod}")
    print(f"[i] Excluyendo {len(EXCLUDED_MODULES)} módulos no necesarios del bundle")

    # Incluir paths para paquetes locales
    cmd.append(f"--paths={shared_telemetry_path}")
    cmd.append(f"--paths={shared_strategy_path}")
    
    # Hidden imports clave para FastAPI, Uvicorn, Websockets y dependencias locales
    HIDDEN_IMPORTS = [
        "src.config",
        "src.services.lmu_api",
        "src.services.strategy_service",
        "src.routers.health",
        "src.routers.websocket",
        "src.routers.llm",
        "src.intelligence.spotter",
        "src.intelligence.engine",
        "shared_telemetry",
        "shared_strategy",
        "uvicorn",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "websockets",
        "watchfiles",
        "msgpack",
        "yaml",
        "httpx",
        "aiohttp",
        "wave",
        "onnxruntime",
        "espeakng_loader",
        "edge_tts",
        "openai",
    ]
    for imp in HIDDEN_IMPORTS:
        cmd.append(f"--hidden-import={imp}")
    
    cmd.append(src_main)
    
    print(f"Ejecutando comando: {' '.join(cmd)}")
    result = subprocess.run(cmd, shell=True)
    
    if result.returncode != 0:
        print("[-] Error durante la compilación con PyInstaller.")
        sys.exit(1)
        
    print("[+] Compilación de PyInstaller completada con éxito.")

    # =========================================================================
    # FASE 2: Copiar modulos locales al bundle
    # PyInstaller --onedir no incluye codigo fuente local, solo dependencies
    # Por tanto copiamos src/, shared-telemetry/, shared-strategy/ a _internal/
    # =========================================================================
    
    compiled_dir = os.path.join(dist_dir, "backend")
    internal_dir = os.path.join(compiled_dir, "_internal")
    
    # Rutas de los módulos locales a copiar
    backend_dir = os.path.abspath(base_dir)
    src_dir = os.path.join(backend_dir, "src")
    shared_telemetry_dir = os.path.join(backend_dir, "..", "shared-telemetry", "shared_telemetry")
    shared_strategy_dir = os.path.join(backend_dir, "..", "shared-strategy", "src", "shared_strategy")
    
    # Normalizar rutas (resolve ..)
    shared_telemetry_dir = os.path.abspath(shared_telemetry_dir)
    shared_strategy_dir = os.path.abspath(shared_strategy_dir)
    
    print(f"Preparando para copiar módulos locales a _internal/")
    print(f"  src: {src_dir}")
    print(f"  shared_telemetry: {shared_telemetry_dir}")
    print(f"  shared_strategy: {shared_strategy_dir}")
    
    # Copiar src/ -> _internal/src/
    if os.path.exists(src_dir):
        dest_src = os.path.join(internal_dir, "src")
        if os.path.exists(dest_src):
            shutil.rmtree(dest_src)
        shutil.copytree(src_dir, dest_src)
        print("[+] Copiado src/ -> _internal/src/")
    else:
        print("[-] ADVERTENCIA: src/ no encontrado")
    
    # Copiar shared_telemetry/ -> _internal/shared_telemetry/
    if os.path.exists(shared_telemetry_dir):
        dest_telemetry = os.path.join(internal_dir, "shared_telemetry")
        if os.path.exists(dest_telemetry):
            shutil.rmtree(dest_telemetry)
        shutil.copytree(shared_telemetry_dir, dest_telemetry)
        print("[+] Copiado shared_telemetry/ -> _internal/shared_telemetry/")
    else:
        print("[-] ADVERTENCIA: shared_telemetry/ no encontrado")
    
    # Copiar shared_strategy/ -> _internal/shared_strategy/
    if os.path.exists(shared_strategy_dir):
        dest_strategy = os.path.join(internal_dir, "shared_strategy")
        if os.path.exists(dest_strategy):
            shutil.rmtree(dest_strategy)
        shutil.copytree(shared_strategy_dir, dest_strategy)
        print("[+] Copiado shared_strategy/ -> _internal/shared_strategy/")
    else:
        print("[-] ADVERTENCIA: shared_strategy/ no encontrado")

    # Copiar tts_models/ (voz Piper) -> _internal/src/services/tts_models/
    tts_models_dir = os.path.join(backend_dir, "src", "services", "tts_models")
    if os.path.exists(tts_models_dir):
        dest_tts = os.path.join(internal_dir, "src", "services", "tts_models")
        if os.path.exists(dest_tts):
            shutil.rmtree(dest_tts)
        os.makedirs(os.path.dirname(dest_tts), exist_ok=True)
        shutil.copytree(tts_models_dir, dest_tts)
        print("[+] Copiado tts_models/ -> _internal/src/services/tts_models/")
    else:
        print("[-] ADVERTENCIA: tts_models/ no encontrado")

    # Copiar .env a _internal/ (para config.py que usa sys._MEIPASS) y al raíz (para CWD fallback)
    env_src = os.path.join(base_dir, ".env")
    if os.path.exists(env_src):
        shutil.copy2(env_src, os.path.join(internal_dir, ".env"))
        shutil.copy2(env_src, os.path.join(compiled_dir, ".env"))
        print("[+] Copiado .env -> _internal/ y raíz del bundle")
    else:
        print("[-] ADVERTENCIA: .env no encontrado en source")

    # Destino en src-tauri
    target_binaries_dir = os.path.abspath(os.path.join(base_dir, "..", "frontend", "src-tauri", "binaries", "backend"))
    
    print(f"Limpiando directorio destino anterior si existe: {target_binaries_dir}")
    if os.path.exists(target_binaries_dir):
        shutil.rmtree(target_binaries_dir)
        
    os.makedirs(target_binaries_dir, exist_ok=True)
    
    compiled_dir = os.path.join(dist_dir, "backend")
    print(f"Copiando compilado desde {compiled_dir} a {target_binaries_dir}...")
    
    # Copiar contenido de la carpeta compilada
    for item in os.listdir(compiled_dir):
        s = os.path.join(compiled_dir, item)
        d = os.path.join(target_binaries_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
            
    # Tauri busca el ejecutable sidecar con el target triple en Windows (x86_64-pc-windows-msvc)
    # Por tanto, renombramos backend.exe a backend-x86_64-pc-windows-msvc.exe en la raíz de binaries/backend
    exe_source = os.path.join(target_binaries_dir, "backend.exe")
    exe_target = os.path.join(target_binaries_dir, "backend-x86_64-pc-windows-msvc.exe")
    
    if os.path.exists(exe_source):
        print(f"Renombrando {exe_source} a {exe_target} para Tauri sidecar...")
        shutil.move(exe_source, exe_target)
    else:
        print("[-] ADVERTENCIA: No se encontró backend.exe en la carpeta de binaries.")
        
    print("[+] Proceso de la Fase 2 completado exitosamente.")

if __name__ == "__main__":
    build()
