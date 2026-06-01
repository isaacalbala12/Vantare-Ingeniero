#!/usr/bin/env python3
"""Benchmark para MiniMax API (OpenAI-compatible)."""
import subprocess, sys, os, time, json, argparse
from datetime import datetime

# System prompt idéntico al benchmark local
SYSTEM_PROMPT_TICKER = """Eres un ingeniero de carrera. Recibes datos en formato ticker compacto.

DICCIONARIO RAPIDO (terminos de automobilismo):
- L = vuelta (lap), no letra L suelta
- P = posicion (place/standing)
- F = combustible (fuel) en litros
- TYR = neumaticos (tyres/wheels)
- BRK = frenos (brakes)
- GAP = diferencia de tiempo con rivales
- SES = sesion (carrera/qualify/practica)
- WTH = clima (weather)
- RIV = rivales
- SC = Safety Car
- FL = delantera izquierda, FR = delantera derecha
- RL = trasera izquierda, RR = trasera derecha

FORMATO TICKER:
### DRV — Datos del piloto
DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{wFL}/{wFR}/{wRL}/{wRR}·{tFL}/{tFR}/{tRL}/{tRR}
### GAP — Diferencias
GAP>{ahead_name}:+{ahead_sec}.{ahead_best}|<{behind_name}:{behind_sec}.{behind_best}.d{delta}

Maximo 2-3 frases. Estilo radio. Tecnico y conciso."""

# Tickers base del benchmark
TICKER_A = """DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63.92/94/98/96
BRK:38/35/22/20
GAP>VST:+2.1.1:48.2|<ALO:-1.2.1:47.9.d-0.3
SES:HY|RACE|38L|45:22
WTH:MED|22|30%+15m|SC:N"""

# Prompts de ejemplo (muestra representativa del benchmark completo)
PROMPTS = [
    ("L1", TICKER_A, "Cual es la posicion actual?", ["P3", "3"]),
    ("L1", TICKER_A, "Cuanto combustible queda en el tanque?", ["42.3"]),
    ("L1", TICKER_A, "Quien va delante y a que distancia?", ["VST", "2.1"]),
    ("L2", TICKER_A, "El piloto esta liderando o no? Explica tu razonamiento.", ["lider", "VST", "liderando"]),
    ("L2", TICKER_A, "Cuanto falta para que termine la carrera?", ["45", "22", "minutos"]),
    ("L3", TICKER_A, "Combustible 42.3L con consumo 3.2L/vuelta. Cuantas vueltas restantes?", ["13", "13L"]),
    ("L4", TICKER_A, "El piloto esta en P3 con VST a +2.1s y ALO a -1.2s. Describe la batalla.", ["3", "VST", "ALO"]),
    ("L5", """DRV:P1|L25|F:28.5L/3.3(7L)|TYR:55/52/50/48.88/90/91/89
GAP>---|<HAM:-5.3.1:47.5.d+0.8
SES:HY|RACE|38L|20:15
WTH:LOW|18|80%+3m|SC:N""", "Hay lluvia aproximandose? Cuanto tiempo?", ["80", "3", "lluvia", "minutos"]),
    ("L6", """DRV:P8|L8|F:89.7L/3.1(27L)|TYR:98/97/96/96.85/87/88/86
GAP>BOT:+0.8.1:49.5|<SAI:-0.4.1:49.1.d-0.7
SES:HY|RACE|38L|52:00
WTH:GRN|26|10%+0m|SC:S""", "Safety Car activo con neumaticos muy desgastados (98/97/96/96). Que recomiendas?", ["boxes", "cambiar", "neum"]),
    ("L7", """DRV:P5|L2|F:96.8L/3.2(28L)
GAP>VER:+3.5.1:47.8|<NOR:-2.1.1:48.5.d-0.7
SES:HY|RACE|38L|55:30
WTH:GRN|20|5%+0m|SC:N""", "Por que no hay datos de neumaticos?", ["vuelta", "2", "3", "representativo"]),
    ("L8", """Tick 1: DRV:P3|L10|F:42.3L TYR:72/68/65/63
Tick 2: DRV:P3|L12|F:36.1L TYR:78/74/71/68
Tick 3: DRV:P3|L14|F:29.8L TYR:85/81/78/75""", "Cual es la tendencia del desgaste de neumaticos?", ["aumenta", "degradacion", "mas rapido"]),
]

def keyword_score(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for kw in keywords if kw.lower() in text_lower)
    return matches / len(keywords)

def run_benchmark_minimax(api_key: str, model: str = "MiniMax/M2.7", base_url: str = "https://api.minimaxi.chat/v1"):
    """Ejecuta benchmark en MiniMax API."""
    import httpx
    
    print(f"=== Benchmark MiniMax: {model} ===")
    print(f"Endpoint: {base_url}")
    print(f"API Key: {api_key[:8]}...")
    
    client = httpx.Client(timeout=120.0)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    results = []
    total_start = time.time()
    
    for i, (level, ticker, question, expected) in enumerate(PROMPTS, 1):
        print(f"\n[{i}/{len(PROMPTS)}] {level}: {question[:50]}...")
        
        # Construir contenido
        user_content = f"""### TELEMETRIA ###
{ticker}

### PREGUNTA ###
{question}"""
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_TICKER},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "max_tokens": 15000,
            "stream": False,
        }
        
        start = time.time()
        try:
            response = client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            
            elapsed = time.time() - start
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            score = keyword_score(content, expected)
            
            print(f"  Score: {score*100:.0f}% | TTFT: {elapsed*1000:.0f}ms | Response: {content[:80]}...")
            
            results.append({
                "level": level,
                "question": question[:60],
                "response": content,
                "score": score,
                "passed": score >= 0.5,
                "ttft_ms": elapsed * 1000,
            })
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({
                "level": level,
                "question": question[:60],
                "response": str(e),
                "score": 0.0,
                "passed": False,
                "ttft_ms": 0,
            })
    
    total_elapsed = time.time() - total_start
    
    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN MINIMAX")
    print("=" * 60)
    
    levels = {}
    for r in results:
        l = r["level"]
        if l not in levels:
            levels[l] = {"passed": 0, "total": 0, "score": 0}
        levels[l]["total"] += 1
        if r["passed"]:
            levels[l]["passed"] += 1
        levels[l]["score"] += r["score"]
    
    for l in sorted(levels.keys()):
        data = levels[l]
        avg_score = data["score"] / data["total"] if data["total"] > 0 else 0
        print(f"  {l}: {data['passed']}/{data['total']} ({avg_score*100:.0f}%)")
    
    total_passed = sum(1 for r in results if r["passed"])
    print(f"\nTotal: {total_passed}/{len(results)} ({total_passed/len(results)*100:.0f}%)")
    print(f"Tiempo: {total_elapsed:.0f}s")
    print("=" * 60)
    
    # Guardar resultados
    output_dir = "./benchmark_reports"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_").replace(" ", "_")
    
    report_path = os.path.join(output_dir, f"{timestamp}_minimax_{safe_model}_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"# Benchmark MiniMax: {model}\n\n")
        f.write(f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        f.write(f"- **Total prompts**: {len(results)}\n")
        f.write(f"- **Aciertos**: {total_passed}/{len(results)}\n\n")
        for r in results:
            f.write(f"## {r['level']}: {r['question']}\n")
            f.write(f"- Score: {r['score']*100:.0f}%\n")
            f.write(f"- TTFT: {r['ttft_ms']:.0f}ms\n")
            f.write(f"- Response: {r['response'][:200]}...\n\n")
    
    print(f"Reporte guardado: {report_path}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description="Benchmark MiniMax API")
    parser.add_argument("--api-key", default=os.environ.get("MINIMAX_API_KEY", ""),
                        help="MiniMax API Key (o MINIMAX_API_KEY env)")
    parser.add_argument("--model", default="MiniMax/M2.7",
                        help="Nombre del modelo")
    parser.add_argument("--base-url", default="https://api.minimaxi.chat/v1",
                        help="URL base de la API")
    args = parser.parse_args()
    
    if not args.api_key:
        print("ERROR: Se necesita --api-key o MINIMAX_API_KEY")
        print("Consigue tu API key en: https://platform.minimaxi.com/")
        sys.exit(1)
    
    run_benchmark_minimax(args.api_key, args.model, args.base_url)

if __name__ == "__main__":
    main()