#!/usr/bin/env python3
"""Night iteration - test many prompt variants with 12 prompts, full benchmark to verify best"""
import httpx, time

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

# 12 prompts sampled across all 8 levels (from benchmark_compare_cloud.py)
TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}
HIST_A = 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'
HIST_E = 'V30:1:50.8/F32.1L V31:1:51.2/F28.7L V32:1:52.1/F25.3L V33:1:52.8/F21.9L V34:1:53.5/F18.5L. Deg:2.4s->2.7s->3.2s->3.5s'

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'E', 'Tengo combustible para llegar a meta?', ['0', '0L', 'no']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza la batalla.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento por vuelta?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HIST_E),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

PROMPTS = [
    # A4 baseline
    ('A4', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'),
    # B variants from iter_v3
    ('B1', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences. NO explanation.'),
    ('B2', 'EXTRACT: P, L, F, TYR%, BRK%, GAP. Answer ONLY with raw values from telemetry. No thinking. No sentences.'),
    ('B3', 'ENGINEER: Data extraction mode. P=position L=lap F=fuel. ONLY numbers. NO sentences. NO explanation. Example: P3 L10 42.3'),
    # New C variants - racing language + context
    ('C1', 'You are a race engineer. Short answers ONLY. Extract: P=position L=lap F=fuel. Respond with data only. No explanation.'),
    ('C2', 'ENGINEER RADIO: Data extraction. Position, Lap, Fuel, Gap. Reply ONLY with values found in telemetry. Max 3 words.'),
    ('C3', 'EXTRACCION: Extrae P L F gap. Responde SOLO con numeros. Sin oraciones. Ej: P3 L10 42.3 2.1s'),
    # More aggressive D variants
    ('D1', 'RACE ENGINEER: Short answer. Extract all numbers from telemetry. Output format: P=X L=X F=X. No sentences.'),
    ('D2', 'DATA MODE: Your job is data extraction. Answer ONLY with raw numbers from telemetry. No sentences. No explanation. No preamble.'),
    ('D3', 'Answer with EXACT values from telemetry. Format: Position=X Lap=X Fuel=X. No thinking. No sentences. No filler.'),
    # E variants - concise bilingual
    ('E1', 'ENGINEER: P/L/F/gap extraction. Answer ONLY. Example: P3 L10 42.3 2.1s. No sentences.'),
    ('E2', 'RACE DATA: Extract P, L, F, Gap from telemetry. Answer with numbers only. No explanation.'),
]

def ex(m): return (m.get('content') or m.get('reasoning') or '').strip()
def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

def run_model(api_key, base_url, model, is_stepfun, sys_prompt):
    mm_total = 0
    sf_total = 0
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    
    for level, tid, q, kw in Q:
        user_parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
        extra = None
        for item in Q:
            if item[2] == q and len(item) > 4:
                extra = item[4]
        if extra:
            user_parts.append('\n### HISTORICO ###\n' + extra)
        user_parts.append('\n### PREGUNTA ###\n' + q)
        content = '\n'.join(user_parts)
        
        payload = {
            'model': model,
            'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}],
            'max_tokens': 80,
            'temperature': 0.1
        }
        if is_stepfun:
            payload['thinking'] = {'type': 'off'}
        
        try:
            r = httpx.post(base_url + '/chat/completions', headers=h, json=payload, timeout=20)
            if r.status_code == 200:
                text = ex(r.json()['choices'][0]['message'])
                if 'minimaxi' in base_url:
                    mm_total += sc(text, kw)
                else:
                    sf_total += sc(text, kw)
        except:
            pass
    return mm_total / len(Q) * 100, sf_total / len(Q) * 100

print('Testing', len(PROMPTS), 'prompt variants with', len(Q), 'questions')
print('='*70)

results = []
for name, sys_prompt in PROMPTS:
    t0 = time.time()
    mm, sf = run_model(M, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', False, sys_prompt)
    mm2, sf2 = run_model(S, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', True, sys_prompt)
    t = time.time() - t0
    
    # Take the right SF score based on which API was called
    avg = (mm + sf2) / 2
    results.append((name, mm, sf2, avg, t, sys_prompt[:60]))
    results.sort(key=lambda x: x[3], reverse=True)
    
    print(f'{name}: MM={mm:.0f}% SF={sf2:.0f}% AVG={avg:.0f}% ({t:.1f}s) | {sys_prompt[:60]}...')

print('\n--- RANKING ---')
for i, (n, mm, sf, avg, t, _) in enumerate(results, 1):
    print(f'{i}. {n}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}%')
