#!/usr/bin/env python3
"""Night screening v3 - strip thinking, proper extraction, 8 questions async"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, time, asyncio, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def ex(m):
    """Extract clean text - strip thinking blocks, get final answer"""
    raw = (m.get('content') or m.get('reasoning') or '').strip()
    # Remove thinking blocks
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    # Remove common prefixes
    raw = re.sub(r'^(Answer:|Response:|Datos:|Posición:|Respuesta:|Result:|Data:)\s*', '', raw, flags=re.IGNORECASE).strip()
    return raw

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|SES:GT3|RACE|38L|WTH:LOW|15C|90%|SC:N',
}

PROMPTS = [
    # Baseline A4
    ('A4', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'),
    # Very concise extraction
    ('C1', 'EXTRACTION: Extract P, L, F, gap from telemetry. Reply ONLY with values. No sentences.'),
    # Example-driven
    ('E1', 'ENGINEER: P/L/F extraction. Example: P3 L10 42.3 2.1s. Answer ONLY with values. No explanation. No thinking.'),
    # Minimal directive
    ('M1', 'Short answer. Numbers only. Extract: P=position L=lap F=fuel from data.'),
    # Force numeric
    ('N1', 'You must answer with ONLY numbers. No words. No sentences. Extract position, lap, fuel, gap.'),
    # Racing specific
    ('R1', 'RACE ENGINEER RADIO: State ONLY position, lap, fuel, gap. Example: P3 L10 F42.3 G+2.1. No sentences.'),
    # Compact
    ('K1', 'Data: P=X L=X F=X Gap=X. Reply ONLY with filled values. No explanation.'),
    # Ultra minimal
    ('U1', 'P L F gap. ONLY numbers. No thinking. No sentences.'),
]

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra:
        parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

async def call_model(client, url, model, api_key, system, content, is_stepfun):
    payload = {
        'model': model,
        'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': content}],
        'max_tokens': 60,
        'temperature': 0.1
    }
    if is_stepfun:
        payload['thinking'] = {'type': 'off'}
    h = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    try:
        r = await client.post(url + '/chat/completions', headers=h, json=payload, timeout=12.0)
        if r.status_code == 200:
            return ex(r.json()['choices'][0]['message'])
    except:
        pass
    return ''

async def run_prompt(name, sys_prompt):
    sem = asyncio.Semaphore(6)
    async with httpx.AsyncClient() as client:
        tasks_mm = []
        tasks_sf = []
        for item in Q:
            tid = item[1]
            q = item[2]
            extra = item[4] if len(item) > 4 else None
            content = build_content(tid, q, extra)
            tasks_mm.append(call_model(client, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', M, sys_prompt, content, False))
            tasks_sf.append(call_model(client, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', S, sys_prompt, content, True))
        
        # Run MM and SF concurrently  
        all_mm = await asyncio.gather(*tasks_mm)
        all_sf = await asyncio.gather(*tasks_sf)
        
        mm_pct = sum(sc(all_mm[i], Q[i][3]) for i in range(len(Q))) / len(Q) * 100
        sf_pct = sum(sc(all_sf[i], Q[i][3]) for i in range(len(Q))) / len(Q) * 100
        return name, mm_pct, sf_pct, (mm_pct + sf_pct) / 2

async def main():
    print(f'Screening {len(PROMPTS)} prompts x {len(Q)} questions')
    print('='*70)
    t0 = time.time()
    
    results = []
    for name, prompt in PROMPTS:
        _, mm, sf, avg = await run_prompt(name, prompt)
        results.append((name, mm, sf, avg, prompt))
        print(f'{name}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}% | {prompt[:55]}')
    
    results.sort(key=lambda x: x[3], reverse=True)
    print(f'\nDone in {time.time()-t0:.1f}s\n--- FINAL RANKING ---')
    for name, mm, sf, avg, _ in results:
        print(f'{name}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}%')
    print(f'\nBEST: {results[0][0]} AVG={results[0][3]:.0f}%')

if __name__ == '__main__':
    asyncio.run(main())
