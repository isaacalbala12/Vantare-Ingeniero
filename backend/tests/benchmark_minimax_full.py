#!/usr/bin/env python3
"""Benchmark completo para MiniMax API usando prompts del benchmark local."""
import subprocess, sys, os, time, json, argparse, httpx
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

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
DRV:P{pos}|L{vuelta}|F:{fuel}L/{consumo}({laps_rest})|TYR:{wFL}/{wFR}/{wRL}/{wRR}·{tFL}/{tFR}/{tRL}/{tRR}
GAP>{ahead}:+{gap}.{best}|<{behind}:-{gap}.{best}.d{delta}
SES:{clase}|{tipo}|{total}L|{tiempo_restante}
WTH:{grip}|{temp}|{rain}%+{min}|SC:{S/N}

Maximo 2-3 frases. Estilo radio. Tecnico y conciso."""

# Tickers base
TICKERS = {
    "A": """DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63.92/94/98/96
BRK:38/35/22/20
GAP>VST:+2.1.1:48.2|<ALO:-1.2.1:47.9.d-0.3
SES:HY|RACE|38L|45:22
WTH:MED|22|30%+15m|SC:N
RIV:20 cars
CLS1(3):VST|HY|+2.1|V10.ALO|HY|-1.2|V10.LEC|GT3|+4.8|V10""",
    "B": """DRV:P1|L25|F:28.5L/3.3(7L)|TYR:55/52/50/48.88/90/91/89
GAP>---|<HAM:-5.3.1:47.5.d+0.8
SES:HY|RACE|38L|20:15
WTH:LOW|18|80%+3m|SC:N
RIV:20 cars
CLS1(2):HAM|HY|-5.3|V24.VER|HY|-8.1|V24""",
    "C": """DRV:P8|L8|F:89.7L/3.1(27L)|TYR:98/97/96/96.85/87/88/86
GAP>BOT:+0.8.1:49.5|<SAI:-0.4.1:49.1.d-0.7
SES:HY|RACE|38L|52:00
WTH:GRN|26|10%+0m|SC:S
RIV:20 cars
CLS1(4):BOT|HY|+0.8|V7.SAI|HY|-0.4|V8.ALB|GT3|+1.2|V8.OCO|GT3|-2.1|V7""",
    "D": """DRV:P5|L2|F:96.8L/3.2(28L)
GAP>VER:+3.5.1:47.8|<NOR:-2.1.1:48.5.d-0.7
SES:HY|RACE|38L|55:30
WTH:GRN|20|5%+0m|SC:N
RIV:20 cars
CLS1(3):VER|HY|+3.5|V1.NOR|GT3|-2.1|V2.ALO|HY|+4.2|V2""",
}

# 20 prompts principales (simplificado del benchmark completo)
PROMPTS = [
    # L1 - Extracción
    ("A", "Cual es la posicion actual?", ["P3", "3"], 1),
    ("A", "Cuanto combustible queda en el tanque?", ["42.3"], 1),
    ("A", "Cual es el consumo promedio por vuelta?", ["3.2"], 1),
    ("A", "Cuantas vueltas restantes de combustible estimadas?", ["13", "13L"], 1),
    ("A", "Cual es el desgaste del neumatico delantero izquierdo?", ["72", "72%"], 1),
    ("B", "Esta activo el Safety Car?", ["No", "N", "no"], 1),
    ("B", "Cual es la probabilidad de lluvia?", ["80", "80%"], 1),
    ("B", "En que vuelta estamos?", ["25", "L25"], 1),
    ("C", "Esta activo el Safety Car?", ["Si", "S", "si"], 1),
    ("D", "Cual es la posicion?", ["5", "P5"], 1),
    # L2 - Interpretación
    ("A", "El piloto esta liderando o no? Explica.", ["liderando", "lider", "no lider"], 2),
    ("A", "Cuanto falta para que termine la carrera? Expresa en minutos.", ["45", "45:"], 2),
    ("B", "El piloto lidera con cuanta ventaja?", ["5", "lidera", "5.3"], 2),
    ("C", "Hay SC en pista? Explica el impacto.", ["SC", "activo", "S"], 2),
    ("D", "Por que no hay datos de neumaticos?", ["vuelta", "2", "3", "representativo"], 2),
    # L3 - Triggers
    ("A", "Combustible 42.3L con consumo 3.2L/vuelta. Cuantas vueltas quedan? Recomienda accion.", ["13", "entrar", "boxes"], 3),
    ("B", "Lluvia en 3 minutos con 80% probabilidad. Neumaticos slicks. Recomienda.", ["lluvia", "cambiar", "inter"], 3),
    ("C", "Safety Car activo con pneus al 95%. Estrategia?", ["SC", "pits", "entrar"], 3),
    # L4 - Multicampo
    ("A", "El piloto esta en P3 con VST a +2.1s y ALO a -1.2s. Analiza la batalla.", ["P3", "VST", "ALO", "batalla"], 4),
    ("B", "P1 con 28.5L, lluvia en 3min. Estrategia optima?", ["28", "lluvia", "cambiar"], 4),
    # L5 - RAG
    ("A", "Historico: hace 5 vueltas consumia 3.0L/v. Ahora 3.2L. Tendencia?", ["aumento", "2.0", "mas"], 5),
    ("B", "Hace 10 vueltas el consumo era 3.1L. Ahora 3.3L. Por que?", ["aumento", "gestion"], 5),
    # L6 - Multi-trigger
    ("C", "SC activo, pneus 95%, combustible 89.7L, P8. Recomendacion urgente.", ["SC", "pits", "ahora"], 6),
    ("B", "Combustible critico 5L y chuva en 3min. Prioridad?", ["combustible", "urgente", "entrar"], 6),
    # L7 - Edge cases
    ("D", "Por que no hay datos de neumaticos en este ticker?", ["vuelta", "2", "3"], 7),
    ("A", "El piloto esta en la vuelta 10 con 42.3L. Es normal?", ["normal", "si"], 7),
    # L8 - Temporal
    ("A", "Cual es la tendencia del desgaste de neumaticos en los ultimos ticks?", ["aumento", "degradacion", "aumento"], 8),
    ("B", "El consumo aumento de 3.1L a 3.3L. Por que puede ser?", ["temperatura", "combustion", "gestion"], 8),
]

def score_response(response: str, keywords: list[str], level: int) -> tuple[float, bool]:
    """Calcula score basado en keywords."""
    response_lower = response.lower()
    matches = sum(1 for kw in keywords if kw.lower() in response_lower)
    score = matches / len(keywords) if keywords else 0.5
    
    # Thresholds por nivel
    thresholds = {1: 0.5, 2: 0.4, 3: 0.4, 4: 0.3, 5: 0.35, 6: 0.4, 7: 0.3, 8: 0.25}
    threshold = thresholds.get(level, 0.3)
    return score, score >= threshold

def run_minimax_benchmark(api_key: str, model: str, base_url: str, output_dir: str):
    """Ejecuta el benchmark completo de MiniMax."""
    print(f"=== Benchmark MiniMax: {model} ===")
    print(f"Endpoint: {base_url}")
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    all_results = {}
    start_time = time.time()
    
    for ticker_id, question, expected_keywords, level in PROMPTS:
        ticker = TICKERS.get(ticker_id, "")
        
        # Construir mensaje
        user_content = f"### TELEMETRIA ###\n{ticker}\n\n### PREGUNTA ###\n{question}"
        
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': SYSTEM_PROMPT_TICKER},
                {'role': 'user', 'content': user_content}
            ],
            'max_tokens': 500,
            'temperature': 0.1,
        }
        
        try:
            req_start = time.time()
            response = httpx.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            ttft = (time.time() - req_start) * 1000
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                # Quitar tags de reasoning si existen
                if "<think>" in content:
                    content = content.split("")[-1].strip()
                if "<think>" in content:
                    parts = content.split("")
                    content = parts[-1].strip() if len(parts) > 1 else content
                
                score, passed = score_response(content, expected_keywords, level)
                print(f"[{len([r for r in PROMPTS if PROMPTS.index(r) < PROMPTS.index((ticker_id, question, expected_keywords, level))+1])}/{len(PROMPTS)}] L{level}: {question[:50]}...")
                print(f"  Score: {score*100:.0f}% | TTFT: {ttft:.0f}ms | Passed: {passed}")
            else:
                print(f"  ERROR: {response.status_code} - {response.text[:100]}")
                score, passed = 0, False
                content = ""
                ttft = 0
                
        except Exception as e:
            print(f"  ERROR: {e}")
            score, passed = 0, False
            content = ""
            ttft = 0
        
        if level not in all_results:
            all_results[level] = {"prompts": [], "name": f"L{level}"}
        all_results[level]["prompts"].append({
            "question": question,
            "ticker_id": ticker_id,
            "response": content,
            "score": score,
            "passed": passed,
            "ttft_ms": ttft,
        })
    
    total_time = time.time() - start_time
    
    # Generar reporte
    report = generate_report(all_results, model, total_time)
    
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_model = model.replace("/", "_")
    
    report_path = os.path.join(output_dir, f"{timestamp}_{safe_model}_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    json_path = os.path.join(output_dir, f"{timestamp}_{safe_model}_data.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\nReporte guardado: {report_path}")
    print(f"Datos guardados: {json_path}")
    
    return all_results

def generate_report(all_results: dict, model: str, total_time: float) -> str:
    """Genera reporte markdown."""
    lines = [
        f"# Benchmark LLM: {model}",
        "",
        f"- **Endpoint**: https://api.minimaxi.chat/v1",
        f"- **Modelo**: {model}",
        f"- **Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **Duracion total**: {total_time:.0f}s",
        "",
        "## Resultados por Nivel",
        "",
        "| Nivel | Nombre | Pts | Prompts | Aciertos | TTFT(ms) |",
        "|-------|--------|:---:|:-------:|:--------:|:--------:|",
    ]
    
    total_prompts = 0
    total_passed = 0
    
    for level in sorted(all_results.keys()):
        r = all_results[level]
        prompts = r["prompts"]
        n = len(prompts)
        passed = sum(1 for p in prompts if p.get("passed", False))
        avg_score = sum(p.get("score", 0) for p in prompts) / n if n > 0 else 0
        avg_ttft = sum(p.get("ttft_ms", 0) for p in prompts) / n if n > 0 else 0
        
        lines.append(f"| L{level} | {r['name']} | {avg_score*100:.1f}% | {n} | {passed}/{n} | {avg_ttft:.0f} |")
        
        total_prompts += n
        total_passed += passed
    
    lines += [
        "",
        "## Resumen Global",
        "",
        f"- **Prompts totales**: {total_prompts}",
        f"- **Aciertos totales**: {total_passed}/{total_prompts} ({total_passed/total_prompts*100:.1f}%)" if total_prompts > 0 else "",
    ]
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="Benchmark MiniMax API completo")
    parser.add_argument("--api-key", required=True, help="MiniMax API Key")
    parser.add_argument("--model", default="MiniMax-M2.7", help="Nombre del modelo")
    parser.add_argument("--base-url", default="https://api.minimaxi.chat/v1", help="URL base")
    parser.add_argument("--output-dir", default="./benchmark_reports", help="Directorio de salida")
    args = parser.parse_args()
    
    run_minimax_benchmark(args.api_key, args.model, args.base_url, args.output_dir)

if __name__ == "__main__":
    main()