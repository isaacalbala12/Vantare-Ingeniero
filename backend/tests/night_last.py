#!/usr/bin/env python3
"""Night last - Final aggressive iteration with action-specific prompts"""
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
    content = re.sub(r'\bPrimero[,\s]*(miro|ver|espera)[,\s]*', ' ', content, flags=re.IGNORECASE)
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
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento por vuelta?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HIST_E),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

# 8 new prompts targeting both data extraction AND action keywords
PROMPTS = [
    # Best so far
    ('HY2', 'Short direct answer. For numbers: extract from telemetry. For advice: short action word. Max 5 words. No sentences.'),
    # Explicit action verbs
    ('AV1', 'Race engineer: Data answers → numbers. Action answers → MUST use these verbs: Entrar boxes, Gestionar neum, Atacar ahora, Defender posicion, Repostar urgente, No puede. Max 3 words.'),
    # Action-first
    ('AF1', 'ACTION WORDS: Entrar, Gestionar, Atacar, Defender, Repostar, No. Answer in 1-3 words. No explanation. Examples: P3 L10 42.3 / Entrar boxes.'),
    # Combined with strong examples
    ('CS1', 'Race engineer. Data: extract numbers (P3 L10 42.3). Advice: short verb phrase with boxes/urgente/gestionar. Max 3 words. Examples: P3 L10 42.3 | Entrar boxes urgente | Gestionar stint.'),
    # Ultra-direct
    ('UD1', '1-3 words. Numbers or action verb. No explanation. Examples: P3 L10 42.3 | Entrar boxes.'),
    # With explicit action list
    ('AL1', 'Answer with action verbs: Entrar boxes, Gestionar, Atacar, Defender, Repostar, Parar. 1-3 words only. No explanation. For data: numbers only.'),
    # New hybrid
    ('NH1', 'RACE ENGINEER: Max 3 words. Data → numbers. Advice → action verb from: Entrar, Gestionar, Atacar, Defender, Repostar, Parar. Example: P3 L10 42.3 | Entrar boxes.'),
    # Very concise
    ('VC1', 'Max 3 words. Numbers or verb. No sentences. Example: P3 L10 42.3 | Entrar boxes.'),
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
    results = []
    t0 = time.time()
    
    for pname, sys_prompt in PROMPTS:
        mm_sc = sf_sc = 0
        mm_lv = {l: [] for l in 'L1L2L3L4L5L6L7L8'.split('L') if l}
        sf_lv = {l: [] for l in 'L1L2L3L4L5L6L7L8'.split('L') if l}
        
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
                lvl = Q[i][0]
                mm_text = extract_mm(msgs[i*2]) if msgs[i*2] else ''
                sf_text = extract_sf(msgs[i*2+1]) if msgs[i*2+1] else ''
                mm_s = sc(mm_text, kw)
                sf_s = sc(sf_text, kw)
                mm_sc += mm_s
                sf_sc += sf_s
                mm_lv.get(lvl, []).append(mm_s)
                sf_lv.get(lvl, []).append(sf_s)
        
        mm_pct = mm_sc / len(Q) * 100
        sf_pct = sf_sc / len(Q) * 100
        avg = (mm_pct + sf_pct) / 2
        
        lv_str = ' '.join(f'{lv}:{sum(mm_lv.get(lv,[]))/len(mm_lv.get(lv,[1]))*100:.0f}/{sum(sf_lv.get(lv,[]))/len(sf_lv.get(lv,[1]))*100:.0f}' for lv in sorted(mm_lv.keys()))
        results.append((pname, mm_pct, sf_pct, avg, lv_str, sys_prompt))
        print(f'{pname}: MM={mm_pct:.0f}% SF={sf_pct:.0f}% AVG={avg:.0f}% | {lv_str}')
    
    print(f'\nDone in {time.time()-t0:.1f}s')
    results.sort(key=lambda x: x[3], reverse=True)
    print('\n--- FINAL RANKING ---')
    for n, mm, sf, avg, lv, p in results:
        print(f'{n}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}%')
        print(f'  {lv}')
    print(f'\n*** BEST: {results[0][0]} AVG={results[0][3]:.0f}% MM={results[0][1]:.0f}% SF={results[0][2]:.0f}% ***')
    print(f'PROMPT: {results[0][5]}')

asyncio.run(run())
