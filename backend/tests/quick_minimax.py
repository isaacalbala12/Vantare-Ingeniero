#!/usr/bin/env python3
"""Quick benchmark MiniMax con 28 prompts."""
import sys, os, time, json, httpx
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
MODEL = 'MiniMax-M2.7'
URL = 'https://api.minimaxi.chat/v1'
OUT_DIR = 'C:/Users/isaac/Desktop/Vantare-Ingeniero/backend/benchmark_reports'

SYSTEM = 'Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio.'

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63.92/94/98/96\nBRK:38/35/22/20\nGAP>VST:+2.1.1:48.2|<ALO:-1.2.1:47.9.d-0.3\nSES:HY|RACE|38L|45:22\nWTH:MED|22|30%+15m|SC:N',
    'B': 'DRV:P1|L25|F:28.5L/3.3(7L)|TYR:55/52/50/48.88/90/91/89\nGAP>---|<HAM:-5.3.1:47.5.d+0.8\nSES:HY|RACE|38L|20:15\nWTH:LOW|18|80%+3m|SC:N',
    'C': 'DRV:P8|L8|F:89.7L/3.1(27L)|TYR:98/97/96/96.85/87/88/86\nGAP>BOT:+0.8.1:49.5|<SAI:-0.4.1:49.1.d-0.7\nSES:HY|RACE|38L|52:00\nWTH:GRN|26|10%+0m|SC:S',
    'D': 'DRV:P5|L2|F:96.8L/3.2(28L)\nGAP>VER:+3.5.1:47.8|<NOR:-2.1.1:48.5.d-0.7\nSES:HY|RACE|38L|55:30\nWTH:GRN|20|5%+0m|SC:N',
}

PROMPTS = [
    ('A', 'Cual es la posicion actual?', ['P3', '3'], 1),
    ('A', 'Cuanto combustible queda en el tanque?', ['42.3'], 1),
    ('A', 'Cual es el consumo promedio por vuelta?', ['3.2'], 1),
    ('A', 'Cuantas vueltas restantes de combustible estimadas?', ['13'], 1),
    ('A', 'Cual es el desgaste del neumatico delantero izquierdo?', ['72'], 1),
    ('B', 'Esta activo el Safety Car?', ['No', 'N'], 1),
    ('B', 'Cual es la probabilidad de lluvia?', ['80'], 1),
    ('B', 'En que vuelta estamos?', ['25', 'L25'], 1),
    ('C', 'Esta activo el Safety Car?', ['Si', 'S'], 1),
    ('D', 'Cual es la posicion?', ['5', 'P5'], 1),
    ('A', 'El piloto esta liderando o no?', ['liderando', 'lider', 'no lider'], 2),
    ('A', 'Cuanto falta para que termine la carrera?', ['45', '45:'], 2),
    ('B', 'El piloto lidera con cuanta ventaja?', ['5', 'lidera', '5.3'], 2),
    ('C', 'Hay SC en pista?', ['SC', 'activo', 'S'], 2),
    ('D', 'Por que no hay datos de neumaticos?', ['vuelta', '2', '3'], 2),
    ('A', 'Combustible 42.3L, consumo 3.2L. Cuantas vueltas quedan?', ['13', 'entrar', 'boxes'], 3),
    ('B', 'Lluvia en 3min, 80% probabilidad. Neumaticos slicks. Que recomiendas?', ['lluvia', 'cambiar'], 3),
    ('C', 'Safety Car activo con pneus 95%. Estrategia?', ['SC', 'pits', 'entrar'], 3),
    ('A', 'El piloto esta en P3 con VST a +2.1s y ALO a -1.2s. Analiza la batalla.', ['P3', 'VST', 'ALO'], 4),
    ('B', 'P1 con 28.5L, lluvia en 3min. Estrategia optima?', ['28', 'lluvia', 'cambiar'], 4),
    ('A', 'Historico: hace 5 vueltas consumia 3.0L/v, ahora 3.2L. Tendencia?', ['aumento', '2.0'], 5),
    ('B', 'Consumo aumento de 3.1L a 3.3L. Por que?', ['aumento', 'gestion'], 5),
    ('C', 'SC activo, pneus 95%, combustible 89.7L, P8. Recomendacion urgente.', ['SC', 'pits', 'ahora'], 6),
    ('B', 'Combustible critico 5L y lluvia en 3min. Prioridad?', ['combustible', 'urgente'], 6),
    ('D', 'Por que no hay datos de neumaticos en este ticker?', ['vuelta', '2', '3'], 7),
    ('A', 'Piloto en vuelta 10 con 42.3L. Es normal?', ['normal', 'si'], 7),
    ('A', 'Cual es la tendencia del desgaste de neumaticos?', ['aumento', 'degradacion'], 8),
    ('B', 'El consumo aumento de 3.1L a 3.3L. Por que?', ['temperatura', 'gestion'], 8),
]

headers = {'Authorization': f'Bearer {API_KEY}', 'Content-Type': 'application/json'}
results = {}
start = time.time()

for i, (tid, q, kw, lvl) in enumerate(PROMPTS):
    ticker = TICKERS.get(tid, '')
    content = f'### TELEMETRIA ###\n{ticker}\n\n### PREGUNTA ###\n{q}'
    
    payload = {'model': MODEL, 'messages': [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': content}
    ], 'max_tokens': 300, 'temperature': 0.1}
    
    req_start = time.time()
    try:
        r = httpx.post(f'{URL}/chat/completions', headers=headers, json=payload, timeout=60)
        ttft = (time.time() - req_start) * 1000
        
        if r.status_code == 200:
            data = r.json()
            text = data['choices'][0]['message']['content']
            if '<think>' in text:
                parts = text.split('')
                text = parts[-1].strip() if len(parts) > 1 else text
            
            matches = sum(1 for k in kw if k.lower() in text.lower())
            score = matches / len(kw) if kw else 0.5
        else:
            print(f'[{i+1}/{len(PROMPTS)}] ERROR {r.status_code}')
            score = 0
            ttft = 0
    except Exception as e:
        print(f'[{i+1}/{len(PROMPTS)}] EXCEPTION: {e}')
        score = 0
        ttft = 0
    
    print(f'[{i+1}/{len(PROMPTS)}] L{lvl}: {q[:40]:40s} Score: {score*100:5.1f}% TTFT: {ttft:6.0f}ms')
    
    if lvl not in results:
        results[lvl] = {'prompts': [], 'name': f'L{lvl}'}
    results[lvl]['prompts'].append({'question': q, 'score': score, 'ttft_ms': ttft, 'level': lvl})

total = time.time() - start

# Print summary
print(f'\n=== BENCHMARK MINI MAX COMPLETO ===')
print(f'Tiempo total: {total:.0f}s')
print(f'Total prompts: {len(PROMPTS)}')

total_score = 0
for lvl in sorted(results.keys()):
    r = results[lvl]
    avg = sum(p['score'] for p in r['prompts']) / len(r['prompts'])
    avg_ttft = sum(p['ttft_ms'] for p in r['prompts']) / len(r['prompts'])
    total_score += avg
    print(f'L{lvl}: {avg*100:5.1f}% avg, TTFT: {avg_ttft:6.0f}ms')

print(f'Global Score: {total_score / len(results) * 100:.1f}%')

# Save report
os.makedirs(OUT_DIR, exist_ok=True)
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
with open(f'{OUT_DIR}/{ts}_minimax_MiniMax-M2.7_data.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f'Report saved to {OUT_DIR}/{ts}_minimax_MiniMax-M2.7_data.json')