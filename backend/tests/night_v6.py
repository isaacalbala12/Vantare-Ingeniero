#!/usr/bin/env python3
"""Night v6 - prompts that handle BOTH extraction AND advice questions"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm(msg):
    content = msg.get('content') or ''
    if content and '<think>' not in content:
        return content.strip()
    think = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    lines = [l.strip() for l in think.split('\n') if l.strip()]
    for line in reversed(lines):
        if any(c.isdigit() for c in line) and len(line) < 120:
            return line
    return think if think else content.strip()

def extract_sf(msg):
    content = (msg.get('content') or msg.get('reasoning') or '').strip()
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    content = re.sub(r'^(Answer:|Response:|Datos:|Posición:|Respuesta:|Result:)\s*', '', content, flags=re.IGNORECASE).strip()
    return content

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|WTH:LOW|15C|90%|+0min|SC:N',
}

HIST_A = 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'
HIST_E = 'V30:1:50.8/F32.1L V31:1:51.2/F28.7L V32:1:52.1/F25.3L V33:1:52.8/F21.9L V34:1:53.5/F18.5L. Deg:2.4s->2.7s->3.2s->3.5s'

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'E', 'Tengo combustible para llegar a meta?', ['0', '0L', 'no']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L2', 'E', 'Los frenos estan criticos?', ['75', '72', 'critico']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza la batalla.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento por vuelta?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HIST_E),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

# 8 new prompts - some handle advice, some are better at extraction
PROMPTS = [
    # Best from v5
    ('UC1', 'Data extraction. Answer ONLY with values from telemetry. No sentences. No explanation. Example: P3 L10 42.3'),
    # Hybrid - handles both data and advice
    ('HY1', 'Race engineer response: Data questions → numbers only. Advice questions → short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'),
    ('HY2', 'Short direct answer. For numbers: extract from telemetry. For advice: short action word. Max 5 words. No sentences.'),
    # More action-focused
    ('AC1', 'RACE ENGINEER: Extract data OR give short action advice. Be concise. Examples: P3 L10 42.3 OR Entrar urgente. No explanation.'),
    ('AC2', 'Answer concisely. Extract numbers OR give 1-2 word action advice. No sentences. No preamble.'),
    # Strong data focus with example
    ('SF1', 'Data extraction. Answer ONLY with values from telemetry. Example: P3 L10 42.3 2.1s. For advice questions, give short action: Entrar, Gestionar, Cuidar.'),
    # Single word answers
    ('SW1', 'One to three words only. Numbers or action. No explanation. No sentences. Examples: P3 L10 42.3 / Entrar boxes.'),
    # Ultra concise with context
    ('UC2', 'Answer ONLY with numbers from telemetry. No sentences. Example: P3 L10 42.3 2.1s'),
]

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra: parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

async def call(client, url, model, key, sys, content, is_sf):
    payload = {'model': model, 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'temperature': 0.1}
    if is_sf: payload['thinking'] = {'type': 'off'}
    h = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    try:
        r = await client.post(url + '/chat/completions', headers=h, json=payload, timeout=15.0)
        if r.status_code == 200: return r.json()['choices'][0]['message']
    except: pass
    return {}

async def run():
    results = []
    t0 = time.time()
    for pname, sys_prompt in PROMPTS:
        mm_scores = []
        sf_scores = []
        async with httpx.AsyncClient() as client:
            for qi, item in enumerate(Q):
                tid, q, kw = item[1], item[2], item[3]
                extra = item[4] if len(item) > 4 else None
                content = build_content(tid, q, extra)
                mm_msg, sf_msg = await asyncio.gather(
                    call(client, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', M, sys_prompt, content, False),
                    call(client, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', S, sys_prompt, content, True)
                )
                mm_text = extract_mm(mm_msg) if mm_msg else ''
                sf_text = extract_sf(sf_msg) if sf_msg else ''
                mm_scores.append(sc(mm_text, kw))
                sf_scores.append(sc(sf_text, kw))
        
        mm_pct = sum(mm_scores) / len(Q) * 100
        sf_pct = sum(sf_scores) / len(Q) * 100
        
        # By level
        by_level = {}
        for i, item in enumerate(Q):
            lvl = item[0]
            if lvl not in by_level: by_level[lvl] = [[], []]
            by_level[lvl][0].append(mm_scores[i])
            by_level[lvl][1].append(sf_scores[i])
        
        level_str = ' '.join(f'{lv}:{sum(by_level[lv][0])/len(by_level[lv][0])*100:.0f}/{sum(by_level[lv][1])/len(by_level[lv][1])*100:.0f}' for lv in sorted(by_level.keys()))
        avg = (mm_pct + sf_pct) / 2
        results.append((pname, mm_pct, sf_pct, avg, level_str, sys_prompt))
        print(f'{pname}: MM={mm_pct:.0f}% SF={sf_pct:.0f}% AVG={avg:.0f}% | {level_str}')
    
    print(f'\nDone in {time.time()-t0:.1f}s')
    results.sort(key=lambda x: x[3], reverse=True)
    print('\n--- RANKING ---')
    for n, mm, sf, avg, lvls, p in results:
        print(f'{n}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}%')
        print(f'  Levels: {lvls}')
        print(f'  Prompt: {p}')
    print(f'\nBEST: {results[0][0]} AVG={results[0][3]:.0f}%')

asyncio.run(run())
