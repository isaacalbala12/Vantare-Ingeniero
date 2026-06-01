#!/usr/bin/env python3
"""Iterate on NEW2 (best) with more refined variants"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm(msg):
    content = msg.get('content') or ''
    if not content.strip():
        content = msg.get('reasoning_content') or ''
    if not content.strip():
        content = msg.get('reasoning') or ''
    return content.strip()

def extract_sf(msg):
    content = msg.get('content') or ''
    if not content.strip():
        content = msg.get('reasoning') or ''
    return content.strip()

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}
HIST_A = 'HISTORICO (ultimas 5 vueltas):\nV5: 1:48.2, Fuel 3.1L, TYR 52%, BRK 28%\nV6: 1:48.5, Fuel 3.2L, TYR 58%, BRK 32%\nV7: 1:48.1, Fuel 3.2L, TYR 64%, BRK 35%\nV8: 1:48.9, Fuel 3.3L, TYR 68%, BRK 38%\nV9: 1:49.2, Fuel 3.4L, TYR 72%, BRK 38%'
HIST_E = 'STINT FINAL (ultimas 5 vueltas):\nV30: Lap 1:50.8, Fuel 32.1L, TYR 78/76/74/72%\nV31: Lap 1:51.2, Fuel 28.7L, TYR 82/80/78/76%\nV32: Lap 1:52.1, Fuel 25.3L, TYR 85/83/81/79%\nV33: Lap 1:52.8, Fuel 21.9L, TYR 87/85/83/81%\nV34: Lap 1:53.5, Fuel 18.5L, TYR 88/85/83/80%\n\nANALISIS: Degradacion acelerandose: 2.4s -> 2.7s -> 3.2s -> 3.5s'

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'E', 'Tengo combustible para llegar a meta?', ['0', '0L', 'critico', 'no']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L2', 'E', 'Los frenos estan criticos?', ['75', '72', 'critico']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza la batalla.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HIST_E),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

PROMPTS = [
    # Best from night_real_bench
    ('NEW2', 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'),
    # NEW2 + more examples
    ('V1', 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3 G+2.1. Example advice: Entrar boxes urgente. Gestionar stint. Atacar ahora.'),
    # NEW2 + more specific data labels
    ('V2', 'Race engineer: Extract data: Position Lap Fuel Gap. Answer with numbers. For action questions: give short verb. Examples: P3 L10 42.3 2.1s | Entrar boxes | Gestionar neum.'),
    # NEW2 with race context
    ('V3', 'You are a race engineer in a F1/GT3 race. Short answers. Data: numbers. Action: short verb phrase. Be concise. Examples: P3 L10 F42.3 | Entrar boxes urgente.'),
    # Original + data directive
    ('V4', 'Eres ingeniero de carrera. Estilo radio, maximo 2-3 frases. Para datos: extrae numeros. Para accion: verbo corto. Ejemplo: P3 L10 42.3 | Entrar boxes.'),
    # NEW2 without "be concise"
    ('V5', 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente. Keep answers very short.'),
    # With more action verbs
    ('V6', 'Race engineer: Data → numbers (P3 L10 42.3). Action → verb: Entrar, Gestionar, Atacar, Defender, Repostar. Short answers. Examples: P3 L10 42.3 | Entrar boxes urgente.'),
]

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra: parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

async def call(client, url, model, key, sys, content, is_sf):
    payload = {'model': model, 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': content}], 'max_tokens': 200, 'temperature': 0.1}
    if is_sf: payload['thinking'] = {'type': 'off'}
    h = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    try:
        r = await client.post(url + '/chat/completions', headers=h, json=payload, timeout=30.0)
        if r.status_code == 200: return r.json()['choices'][0]['message']
    except: pass
    return {}

async def run():
    results = []
    t0 = time.time()
    
    for pname, sys_prompt in PROMPTS:
        mm_sc = sf_sc = 0
        async with httpx.AsyncClient() as client:
            tasks_mm = []
            tasks_sf = []
            for item in Q:
                tid, q = item[1], item[2]
                extra = item[4] if len(item) > 4 else None
                content = build_content(tid, q, extra)
                tasks_mm.append(call(client, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', M, sys_prompt, content, False))
                tasks_sf.append(call(client, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', S, sys_prompt, content, True))
            
            all_mm = await asyncio.gather(*tasks_mm)
            all_sf = await asyncio.gather(*tasks_sf)
            
            for i, item in enumerate(Q):
                kw = item[3]
                mm_text = extract_mm(all_mm[i]) if all_mm[i] else ''
                sf_text = extract_sf(all_sf[i]) if all_sf[i] else ''
                mm_sc += sc(mm_text, kw)
                sf_sc += sc(sf_text, kw)
        
        mm_pct = mm_sc / len(Q) * 100
        sf_pct = sf_sc / len(Q) * 100
        avg = (mm_pct + sf_pct) / 2
        results.append((pname, mm_pct, sf_pct, avg, sys_prompt))
        print(f'{pname}: MM={mm_pct:.0f}% SF={sf_pct:.0f}% AVG={avg:.0f}%')
    
    print(f'\nDone in {time.time()-t0:.1f}s')
    results.sort(key=lambda x: x[3], reverse=True)
    print('\n--- RANKING ---')
    for n, mm, sf, avg, p in results:
        print(f'{n}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}%')
    print(f'\nBEST: {results[0][0]} AVG={results[0][3]:.0f}%')
    print(f'PROMPT: {results[0][4]}')

asyncio.run(run())
