"""Test lfm2.5-8b-a1b con system prompt + diccionario racing."""
import httpx, json, time, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = "http://192.168.1.41:1234"
API = f"{BASE}/api/v1"
MODEL = "lfm2.5-8b-a1b"

SYSTEM = """Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio. Tecnico y conciso.

DICCIONARIO RAPIDO (terminos de automovilismo):
- L = vuelta (lap), no letra L suelta
- P = posicion (place/standing)
- F = combustible (fuel) en litros
- TYR = neumaticos (tyres/wheels): FL/FR/RL/RR = delantera izq/der, trasera izq/der
- BRK = frenos (brakes)
- GAP = diferencia de tiempo con rivales
- SES = sesion (carrera/qualify/practica)
- WTH = clima (weather)
- RIV = rivales
- SC = Safety Car
- undercut = entrar a boxes antes que el rival para ganar posicion
- stint = stint/periodo entre paradas
- pits = boxes/pit lane"""

PROMPTS = [
    "Cual es la posicion actual? Datos: DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63.92/94/98/96",
    "Combustible critico: F:8.7L/3.2(2L). Recomienda accion.",
    "Hay lluvia en 15 minutos (30%) y neumaticos slicks (72% desgaste). Que recomiendas?",
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)

def load_model(key):
    log(f"Cargando {key}...")
    r = httpx.post(f"{API}/models/load", json={"model": key}, timeout=120)
    d = r.json()
    log(f"  {d.get('status')} ({d.get('load_time_seconds','?')}s)")
    return d.get("status") == "loaded"

def send_prompt(text):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text}
        ],
        "temperature": 0.1,
        "max_tokens": 15000,
        "stream": True,
    }

    log(f"Enviando: {text[:60]}...")
    start = time.time()
    content = ""
    reasoning = ""
    first_content_time = None
    content_tokens = 0

    try:
        with httpx.stream("POST", f"{BASE}/v1/chat/completions",
                         json=payload, timeout=300) as response:

            for line in response.iter_lines():
                line = line.strip()
                if not line or line == "[DONE]":
                    continue
                if line.startswith("data: "):
                    line = line[6:]

                try:
                    data = json.loads(line)
                    delta = data.get("choices", [{}])[0].get("delta", {})

                    c = delta.get("content", "")
                    if c:
                        if first_content_time is None:
                            first_content_time = time.time()
                        content += c
                        content_tokens += 1
                        continue

                    r = delta.get("reasoning_content", "")
                    if r:
                        reasoning += r

                except json.JSONDecodeError:
                    pass

    except Exception as e:
        log(f"  ERROR: {e}")
        return

    elapsed = time.time() - start
    ttft = ((first_content_time - start) * 1000) if first_content_time else None
    tps = content_tokens / (elapsed - ttft/1000) if (content_tokens and ttft and ttft > 0 and elapsed > ttft/1000) else 0

    log(f"  Tiempo: {elapsed:.1f}s | TTFT: {ttft:.0f}ms | Tok/s: {tps:.1f}")
    log(f"  Reasoning: {len(reasoning)} chars | Content: {len(content)} chars ({content_tokens} toks)")

    print("\n" + "="*70)
    print("CONTENT (respuesta final):")
    print(content[:400] if content else "(VACIO)")
    print("="*70 + "\n")

def main():
    if not load_model(MODEL):
        return

    time.sleep(2)

    for i, prompt in enumerate(PROMPTS, 1):
        log(f"\n--- Prompt {i}/{len(PROMPTS)} ---")
        send_prompt(prompt)

    log("Descargando...")
    httpx.post(f"{API}/models/unload", json={"instance_id": MODEL}, timeout=30)
    log("Listo.")

if __name__ == "__main__":
    main()
