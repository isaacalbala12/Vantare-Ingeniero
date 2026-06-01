#!/usr/bin/env python3
"""Night v5 - ultra aggressive prompt variants, smart extraction, 8 questions async"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm(msg):
    content = msg.get('content') or ''
    reasoning = msg.get('reasoning') or ''
    
    if content and '<think>' not in content:
        return content.strip()
    
    think = reasoning or content
    think = re.sub(r'<think>.*?</think>', '', think, flags=re.DOTALL).strip()
    
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

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L5', 'A', 'El consumo esta aumentando? Cuanto perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
]

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|SES:GT3|RACE|38L|WTH:LOW|15C|90%|SC:N',
}

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra: parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

# 10 prompt variants - mix of styles
PROMPTS = [
    # Top performers from v4
    ('RAD', 'ENGINEER RADIO: State position, lap, fuel, gap. Answer ONLY. Example: P3 L10 F42.3 G+2.1'),
    ('R1', 'RACE ENGINEER RADIO: State ONLY position, lap, fuel, gap. Example: P3 L10 F42.3 G+2.1. No sentences.'),
    # Ultra concise
    ('UC1', 'Data extraction. Answer ONLY with values from telemetry. No sentences. No explanation. Example: P3 L10 42.3'),
    ('UC2', 'Answer ONLY with numbers from telemetry. No sentences. Example: P3 L10 42.3 2.1s'),
    # Bilingual
    ('BI1', 'ENGINEER: Extrae P L F gap. Responde SOLO con valores. Sin oraciones. Ejemplo: P3 L10 42.3 2.1'),
    # Force format
    ('FM1', 'Format: P=X L=X F=X Gap=X. Reply ONLY with filled format. No sentences.'),
    ('FM2', 'OUTPUT: P=X L=X F=X G=X. FILL IN values from telemetry. No thinking. No sentences.'),
    # New directions
    ('ND1', 'You are a race engineer. Extract: Position, Lap, Fuel, Gap. Answer ONLY with extracted values. Max 5 words.'),
    ('ND2', 'Strip all text. Output ONLY the raw data values found in telemetry. No labels. No explanation. Example: P3 L10 42.3 2.1s'),
    # Very direct
    ('VD1', 'Position. Lap. Fuel. Gap. Give me just the numbers. Nothing else.'),
]

async def call(client, url, model, key, sys, content, is_sf):
    payload = {'model': model, 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': content}], 'max_tokens': 60, 'temperature': 0.1}
    if is_sf: payload['thinking'] = {'type': 'off'}
    h = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    try:
        r = await client.post(url + '/chat/completions', headers=h, json=payload, timeout=12.0)
        if r.status_code == 200: return r.json()['choices'][0]['message']
    except: pass
    return {}

async def run():
    results = []
    t0 = time.time()
    for pname, sys_prompt in PROMPTS:
        mm_sc = sf_sc = 0
        async with httpx.AsyncClient() as client:
            tasks = []
            for item in Q:
                tid, q, kw = item[1], item[2], item[3]
                extra = item[4] if len(item) > 4 else None
                content = build_content(tid, q, extra)
                tasks.append(call(client, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', M, sys_prompt, content, False))
                tasks.append(call(client, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', S, sys_prompt, content, True))
            msgs = await asyncio.gather(*tasks)
            for i in range(len(Q)):
                kw = Q[i][3]
                mm_text = extract_mm(msgs[i*2])
                sf_text = extract_sf(msgs[i*2+1])
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
        print(f'    Prompt: {p}')
    print(f'\nBEST: {results[0][0]} AVG={results[0][3]:.0f}%')

asyncio.run(run())
