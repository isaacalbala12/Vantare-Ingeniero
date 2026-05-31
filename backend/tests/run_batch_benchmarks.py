"""Lanzador batch de benchmarks para múltiples modelos.
Carga cada modelo via API, ejecuta el benchmark, guarda resultados, y pasa al siguiente."""
import subprocess
import sys
import time
import os
import httpx

BASE_URL = "http://192.168.1.41:1234"
API_URL = f"{BASE_URL}/api/v1"
BENCHMARK_CMD = [sys.executable, "-m", "tests.benchmark_llm"]
OUTPUT_DIR = "./benchmark_reports"

# Orden exacto solicitado por el usuario
MODELS = [
    "granite-4.1-8b",
    "qwen3.5-4b-safety-thinking",
    "nvidia/nemotron-3-nano-4b",
    "meta-llama-3.1-8b-instruct",
    "liquid/lfm2.5-1.2b",
    "qwopus3.5-9b-v3",
    "qwopus3.5-9b-coder-mtp",
    "google/gemma-4-e2b",
    "deepseek/deepseek-r1-0528-qwen3-8b",
    "mistralai/ministral-3-3b",
    "qwen/qwen3.5-9b",
    "google/gemma-4-e4b",
    "lfm2.5-8b-a1b",
]

BENCHMARK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BENCHMARK_DIR)  # backend/
os.makedirs(os.path.join(PROJECT_DIR, OUTPUT_DIR), exist_ok=True)

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

current_instance_id = None

def unload_current_model():
    """Descarga el modelo actual para liberar VRAM."""
    global current_instance_id
    if not current_instance_id:
        log("  No hay modelo cargado para descargar")
        return True
    log(f"Descargando modelo (instance_id={current_instance_id})...")
    try:
        r = httpx.post(f"{API_URL}/models/unload",
            json={"instance_id": current_instance_id}, timeout=30)
        if r.status_code == 200:
            log(f"  Modelo descargado: {r.json().get('status', 'ok')}")
            current_instance_id = None
            return True
        else:
            log(f"  Error descargando: HTTP {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        log(f"  Error descargando: {e}")
        return False

def load_model(model_key):
    """Carga un modelo via API LM Studio. Retorna True si éxito."""
    global current_instance_id
    log(f"Cargando modelo: {model_key}...")
    try:
        r = httpx.post(
            f"{API_URL}/models/load",
            json={"model": model_key},
            timeout=120,
        )
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "unknown")
            load_time = data.get("load_time_seconds", "?")
            current_instance_id = data.get("instance_id")
            log(f"  Modelo {model_key}: {status} (cargado en {load_time}s, id={current_instance_id})")
            return status == "loaded"
        else:
            log(f"  Error cargando {model_key}: HTTP {r.status_code} - {r.text[:200]}")
            return False
    except Exception as e:
        log(f"  Error cargando {model_key}: {e}")
        return False

def run_benchmark(model_key):
    """Ejecuta el benchmark para un modelo y retorna éxito."""
    log(f"Iniciando benchmark para: {model_key}")
    start = time.time()
    
    cmd = BENCHMARK_CMD + [
        "--model", model_key,
        "--base-url", BASE_URL,
        "--output-dir", OUTPUT_DIR,
    ]
    
    try:
        result = subprocess.run(
            cmd,
            cwd=PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=14400,  # 4h por modelo (15000 tokens/razonamiento puede ser lento)
        )
        elapsed = time.time() - start
        
        # Log output relevante
        log(f"  Benchmark completado en {elapsed:.0f}s")
        for line in result.stderr.split("\n"):
            if "Nivel" in line or "Benchmark" in line or "Error" in line or "WARNING" in line:
                log(f"  {line.strip()}")
        
        return True
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT: Benchmark excedió 2h para {model_key}")
        return False
    except Exception as e:
        log(f"  Error en benchmark {model_key}: {e}")
        return False

def main():
    log("=" * 60)
    log("LANZADOR BATCH DE BENCHMARKS")
    log(f"Endpoint: {BASE_URL}")
    log(f"Modelos a probar: {len(MODELS)}")
    log("Orden: " + ", ".join(MODELS))
    log("=" * 60)
    
    results = {}
    total_start = time.time()
    
    for i, model in enumerate(MODELS, 1):
        log("")
        log(f"[{i}/{len(MODELS)}] {'='*40}")
        log(f"[{i}/{len(MODELS)}] Modelo: {model}")
        log(f"[{i}/{len(MODELS)}] {'='*40}")
        
        # 0. Descargar modelo anterior (libera VRAM)
        if i > 1:  # No descargar antes del primer modelo
            unload_current_model()
            time.sleep(2)  # Pausa para que LM Studio estabilice

        # 1. Cargar modelo
        model_start = time.time()
        loaded = load_model(model)
        if not loaded:
            log(f"  [!] No se pudo cargar {model} - saltando")
            results[model] = "FAILED_LOAD"
            continue
        
        # Pequeña pausa para estabilización
        time.sleep(3)
        
        # 2. Ejecutar benchmark
        success = run_benchmark(model)
        results[model] = "OK" if success else "FAILED_BENCH"
        
        model_elapsed = time.time() - model_start
        remaining_models = len(MODELS) - i
        avg_time = model_elapsed if success else 0
        eta = avg_time * remaining_models if avg_time > 0 else 0
        
        log(f"  Tiempo del modelo: {model_elapsed:.0f}s")
        if remaining_models > 0:
            log(f"  Modelos restantes: {remaining_models}")
            log(f"  ETA estimado: {eta/60:.0f} min ({eta/3600:.1f}h)")
        
        log("")
    
    # Descargar ultimo modelo
    unload_current_model()

    # Resumen final
    total_elapsed = time.time() - total_start
    log("=" * 60)
    log("RESUMEN FINAL")
    log(f"Tiempo total: {total_elapsed/60:.0f} min ({total_elapsed/3600:.1f}h)")
    log("")
    for model, status in results.items():
        log(f"  {model}: {status}")
    log("=" * 60)

if __name__ == "__main__":
    main()
