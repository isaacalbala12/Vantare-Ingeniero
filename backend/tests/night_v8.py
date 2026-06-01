#!/usr/bin/env python3
"""Night v8 - Force answer placement + higher tokens + new prompts"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm(msg):
    """Extract: last non-empty line with digits, OR content after last tag"""
    content = msg.get('content') or ''
    reasoning = msg.get('reasoning') or ''
    
    # Try content first (no thinking)
    if content and '<think>' not in content:
        return content.strip()
    
    # Extract from thinking
    think = reasoning or content
    think = re.sub(r'<think>.*?</think>', '', think, flags=re.DOTALL).strip()
    
    # Try last line with digits
    lines = [l.strip() for l in think.split('\n') if l.strip()]
    for line in reversed(lines):
        if any(c.isdigit() for c in line) and len(line) < 120:
            return line
    
    # Fallback: last line
    return lines[-1] if lines else content.strip()

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
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza la batalla.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
]

# 6 new prompts
PROMPTS = [
    ('HY1', 'Race engineer response: Data questions → numbers only. Advice questions → short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'),
    # Force answer at end
    ('FE1', 'Think step by step. Then give your FINAL ANSWER in ONE LINE at the end. Format: FINAL: <answer>. Example: FINAL: P3 L10 42.3'),
    ('FE2', 'First analyze. Then answer with ONLY the data or action. Put answer on LAST LINE. No text after answer.'),
    # Action words explicit
    ('AW1', 'ENGINEER: For advice questions use these words: Entrar, boxes, urgente, gestionar, atacar, defender. Answer ONLY with short action.'),
    # Very direct
    ('VD1', 'You are a race engineer. State your answer in 1-3 words. No explanation. No sentences. Example: P3 L10 42.3'),
    # Structured
    ('ST1', 'Answer format: [NUMBER/numbers] or [ACTION]. Be precise. Examples: P3 L10 42.3 / Entrar boxes urgente. No explanation.'),
]

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra: parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

async def call(client, url, model, key, sys, content, is_sf):
    payload = {'model': model, 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': content}], 'max_tokens': 120, 'temperature': 0.1}
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
                tid, q = item[1], item[2]
                extra = item[4] if len(item) > 4 else None
                content = build_content(tid, q, extra)
                tasks.append(call(client, 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', M, sys_prompt, content, False))
                tasks.append(call(client, 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', S, sys_prompt, content, True))
            msgs = await asyncio.gather(*tasks)
            for i in range(len(Q)):
                kw = Q[i][3]
                mm_sc += sc(extract_mm(msgs[i*2]) if msgs[i*2] else '', kw)
                sf_sc += sc(extract_sf(msgs[i*2+1]) if msgs[i*2+1] else '', kw)
        
        mm_pct = mm_sc / len(Q) * 100
        sf_pct = sf_sc / len(Q) * 100
        avg = (mm_pct + sf_pct) / 2
        results.append((pname, mm_pct, sf_pct, avg, sys_prompt))
        print(f'{pname}: MM={mm_pct:.0f}% SF={sf_pct:.0f}% AVG={avg:.0f}%')
    
    print(f'\nDone in {time.time()-t0:.1f}s')
    results.sort(key=lambda x: x[3], reverse=True)
    print('\n--- RANKING ---')
    for n, mm, sf, avg, p in results:
        print(f'{n}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}% | {p}')

asyncio.run(run())
