#!/usr/bin/env python3
"""Definitive test - 3 runs, 4 best prompts, 10 questions - to get stable results"""
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
    think = re.sub(r'<think>.*?</think>', '', reasoning or content, flags=re.DOTALL).strip()
    lines = [l.strip() for l in think.split('\n') if l.strip()]
    data_lines = [l for l in lines if len(l) < 100 and (any(c.isdigit() for c in l) or any(w in l.lower() for w in ['entrar', 'boxes', 'urgente', 'gestionar', 'atacar', 'defender', 'si', 'no', 'critico', 'normal', 'aumentando', 'acelerando', 'hacer', 'parar', 'repostar']))]
    return data_lines[-1] if data_lines else (lines[-1] if lines else content.strip())

def extract_sf(msg):
    content = (msg.get('content') or msg.get('reasoning') or '').strip()
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    content = re.sub(r'\bWait[,\s]*(no[,\s]*)?(wait[,\s]*)*', ' ', content, flags=re.IGNORECASE)
    content = re.sub(r'\bGot it[,\s]*(let\'?s?|lets)[,\s]*(see|think)[,\s]*', ' ', content, flags=re.IGNORECASE)
    content = re.sub(r'^(Answer:|Response:|Datos:|Posición:|Respuesta:|Result:)\s*', '', content, flags=re.IGNORECASE).strip()
    lines = [l.strip() for l in content.split('\n') if l.strip() and len(l.strip()) < 120]
    return lines[-1] if lines else content[:200]

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|WTH:LOW|15C|90%|+0min|SC:N',
}
HIST_A = 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'
HIST_E = 'V30:1:50.8/F32.1L V31:1:51.2/F28.7L V32:1:52.1/F25.3L V33:1:52.8/F21.9L V34:1:53.5/F18.5L. Deg:2.4s->2.7s->3.2s->3.5s'

# 10 representative questions
Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
]

# Top 4 prompts from all tests
PROMPTS = [
    ('HY2', 'Short direct answer. For numbers: extract from telemetry. For advice: short action word. Max 5 words. No sentences.'),
    ('HY1', 'Race engineer response: Data questions → numbers only. Advice questions → short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'),
    ('VD1', 'You are a race engineer. State your answer in 1-3 words. No explanation. No sentences. Example: P3 L10 42.3'),
    ('AW1', 'ENGINEER: For advice questions use these words: Entrar, boxes, urgente, gestionar, atacar, defender. Answer ONLY with short action. For data: extract numbers.'),
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
        r = await client.post(url + '/chat/completions', headers=h, json=payload, timeout=12.0)
        if r.status_code == 200: return r.json()['choices'][0]['message']
    except: pass
    return {}

async def run():
    all_results = {p[0]: {'mm': [], 'sf': []} for p in PROMPTS}
    t0 = time.time()
    
    for run_i in range(3):
        print(f'\n=== RUN {run_i+1}/3 ===')
        for pname, sys_prompt in PROMPTS:
            mm_sc = sf_sc = 0
            async with httpx.AsyncClient() as client:
                tasks = []
                for item in Q:
                    tid, q = item[1], item[2]
                    extra = item[4] if len(item) > 4 else None
                    content = build_content(tid, q, extra)
                    tasks.append(call(client, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', M, sys_prompt, content, False))
                    tasks.append(call(client, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', S, sys_prompt, content, True))
                msgs = await asyncio.gather(*tasks)
                for i in range(len(Q)):
                    kw = Q[i][3]
                    mm_text = extract_mm(msgs[i*2]) if msgs[i*2] else ''
                    sf_text = extract_sf(msgs[i*2+1]) if msgs[i*2+1] else ''
                    mm_sc += sc(mm_text, kw)
                    sf_sc += sc(sf_text, kw)
            
            mm_pct = mm_sc / len(Q) * 100
            sf_pct = sf_sc / len(Q) * 100
            all_results[pname]['mm'].append(mm_pct)
            all_results[pname]['sf'].append(sf_pct)
            print(f'  {pname}: MM={mm_pct:.0f}% SF={sf_pct:.0f}%')
    
    print(f'\nDone in {time.time()-t0:.1f}s\n')
    print('--- AVERAGE OVER 3 RUNS ---')
    for pname in all_results:
        mms = all_results[pname]['mm']
        sfs = all_results[pname]['sf']
        avg_mm = sum(mms) / len(mms)
        avg_sf = sum(sfs) / len(sfs)
        avg = (avg_mm + avg_sf) / 2
        print(f'{pname}: MM={avg_mm:.1f}% SF={avg_sf:.1f}% AVG={avg:.1f}% (runs: {mms})')

asyncio.run(run())
