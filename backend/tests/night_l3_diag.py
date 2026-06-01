#!/usr/bin/env python3
"""L3 Diagnostic - see what models output for advice questions"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, re

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
    return lines[-1] if lines else content.strip()

def extract_sf(msg):
    content = (msg.get('content') or msg.get('reasoning') or '').strip()
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    return content

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

TICKERS = {
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|WTH:LOW|15C|90%|+0min|SC:N',
}

L3_Q = [
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
]

PROMPTS = [
    ('HY1', 'Race engineer response: Data questions → numbers only. Advice questions → short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'),
    ('HY2', 'Short direct answer. For numbers: extract from telemetry. For advice: short action word. Max 5 words. No sentences.'),
    ('VD1', 'You are a race engineer. State your answer in 1-3 words. No explanation. No sentences. Example: P3 L10 42.3'),
    ('AW1', 'ENGINEER: For advice questions use these words: Entrar, boxes, urgente, gestionar, atacar, defender. Answer ONLY with short action.'),
]

for pname, sys_prompt in PROMPTS:
    print(f'\n==== {pname} ====')
    for lvl, tid, q, kw in L3_Q:
        content = f'### TELEMETRIA ###\n{TICKERS[tid]}\n### PREGUNTA ###\n{q}'
        
        # MM
        h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'temperature': 0.1}, timeout=15)
        mm_clean = extract_mm(r.json()['choices'][0]['message']) if r.status_code == 200 else f'ERR:{r.status_code}'
        mm_score = sc(mm_clean, kw)
        
        # SF
        h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
        r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
            json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'thinking': {'type': 'off'}}, timeout=15)
        sf_clean = extract_sf(r.json()['choices'][0]['message']) if r.status_code == 200 else f'ERR:{r.status_code}'
        sf_score = sc(sf_clean, kw)
        
        print(f'  [{lvl}] {q}')
        print(f'    MM ({mm_score*100:.0f}%): "{mm_clean}"')
        print(f'    SF ({sf_score*100:.0f}%): "{sf_clean}"')
