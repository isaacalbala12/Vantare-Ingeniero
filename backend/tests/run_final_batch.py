<<<<<<< Updated upstream
"""Batch runner: última tanda — 5 modelos nuevos (sin phi-4)."""
=======
"""Batch runner: ultima tanda - 5 modelos nuevos."""
>>>>>>> Stashed changes
import subprocess, sys, time, os, httpx

BASE = "http://192.168.1.41:1234"
API = f"{BASE}/api/v1"
CMD = [sys.executable, "-m", "tests.benchmark_llm"]
OUT = "./benchmark_reports"
PROJ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODELS = [
    "unsloth/granite-4.1-3b",
    "ministral-3-8b-instruct-2512",
    "smollm3-3b-128k",
    "nvidia_nvidia-nemotron-nano-9b-v2",
    "qwen3.5-4b",
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def unload():
    try:
        r = httpx.get(f"{API}/models", timeout=5)
        for m in r.json().get("models", []):
            for inst in m.get("loaded_instances", []):
                iid = inst.get("id") if isinstance(inst, dict) else inst
                httpx.post(f"{API}/models/unload", json={"instance_id": iid}, timeout=30)
    except Exception as e:
        log(f"  Error al descargar: {e}")

def load_model(key):
    log(f"Cargando {key}...")
    r = httpx.post(f"{API}/models/load", json={"model": key}, timeout=120)
    d = r.json()
    log(f"  {d.get('status')} ({d.get('load_time_seconds','?')}s)")
    return d.get("status") == "loaded"

def run_model(key):
    log(f"Benchmark: {key}")
    start = time.time()
    p = subprocess.run(
        CMD + ["--model", key, "--base-url", BASE, "--output-dir", OUT],
        cwd=PROJ, capture_output=True, text=True, timeout=14400
    )
    elapsed = time.time() - start
    log(f"  Completado en {elapsed/60:.1f}min")
    for line in p.stderr.split("\n"):
        if any(x in line for x in ["Nivel", "Benchmark", "Error", "WARNING", "PASA", "NO PASA"]):
            log(f"  {line.strip()}")
    if p.returncode != 0:
        log(f"  WARNING: return code {p.returncode}")
    return p.returncode == 0

def main():
    log("=" * 60)
<<<<<<< Updated upstream
    log(f"ULTIMA TANDA - {len(MODELS)} modelos nuevos (sin phi-4)")
=======
    log(f"ULTIMA TANDA - {len(MODELS)} modelos nuevos")
>>>>>>> Stashed changes
    log("=" * 60)

    unload()
    time.sleep(2)

    results = {}
    total_start = time.time()

    for i, model in enumerate(MODELS, 1):
        log(f"\n{'='*60}")
        log(f"[{i}/{len(MODELS)}] {model}")
        log(f"{'='*60}")

        if i > 1:
            unload()
            time.sleep(3)

        ok = load_model(model)
        if not ok:
            log(f"  FALLO carga - saltando")
            results[model] = "FAIL"
            continue

        time.sleep(3)
        success = run_model(model)
        results[model] = "OK" if success else "FAIL"

        remaining = len(MODELS) - i
        if remaining > 0:
            avg = (time.time() - total_start) / i
            eta = avg * remaining / 60
            log(f"  ETA restante: ~{eta:.0f}min")

    unload()
    log("\n" + "=" * 60)
    log("RESUMEN FINAL")
    log("=" * 60)
    for m, s in results.items():
        log(f"  {m}: {s}")
    log(f"Tiempo total: {(time.time()-total_start)/60:.0f}min")
    log("=" * 60)

if __name__ == "__main__":
    main()
