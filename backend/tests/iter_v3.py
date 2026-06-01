#!/usr/bin/env python3
"""Iterate on A4 which got 90%/90%"""
import httpx

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

T = 'DRV:P3|L10|F:42.3L|TYR:72%|BRK:38%|GAP>VST+2.1s|ALO-1.2s|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
HIST = 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'

Q = [
    ('Posicion/vuelta?', ['P3', 'L10']),
    ('Combustible/vueltas?', ['42.3', '13']),
    ('Gap VST/ALO?', ['VST', '2.1', '1.2']),
    ('Puedo atacar a VST?', ['2.1', 'si']),
    ('Consumo aumentando?', ['3.1', '3.4', 'si']),
    ('Degradacion normal?', ['normal', 'ok']),
    ('Frenos criticos?', ['38', 'normal']),
    ('Combustible 0L. Que hago?', ['entrar', 'urgente']),
]

P = [
    # A4 variants
    ('B1', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences. NO explanation.'),
    ('B2', 'EXTRACT: P, L, F, TYR%, BRK%, GAP. Answer ONLY with raw values from telemetry. No thinking. No sentences.'),
    ('B3', 'ENGINEER: Data extraction mode. P=position L=lap F=fuel. ONLY numbers. NO sentences. NO explanation. Example: P3 L10 42.3'),
    ('B4', 'EXTRACT values from telemetry. Respond ONLY with numbers. Position Lap Fuel Gap. NO sentences. NO thinking.'),
    ('B5', 'DATA EXTRACTION: Get P, L, F, gap values. Answer with ONLY numbers and names from telemetry. Max 5 words.'),
]

def ex(m): return (m.get('content') or m.get('reasoning') or '').strip()
def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

print('B4 got 90%/90%. Testing variants:')
print('='*50)

for name, sys in P:
    mm = sf = 0
    try:
        h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
        for q, k in Q:
            ctx = T + '\n' + q
            if 'HIST' in q or 'consumo' in q.lower() or 'degradacion' in q.lower():
                ctx = T + '\n' + HIST + '\n' + q
            r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
                json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': ctx}], 'max_tokens': 50}, timeout=15)
            if r.status_code == 200: mm += sc(ex(r.json()['choices'][0]['message']), k)
    except: pass
    try:
        h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
        for q, k in Q:
            ctx = T + '\n' + q
            if 'HIST' in q or 'consumo' in q.lower() or 'degradacion' in q.lower():
                ctx = T + '\n' + HIST + '\n' + q
            r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
                json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': ctx}], 'max_tokens': 50, 'thinking': {'type': 'off'}}, timeout=15)
            if r.status_code == 200: sf += sc(ex(r.json()['choices'][0]['message']), k)
    except: pass
    print(f'{name}: MM={mm/len(Q)*100:.0f}% SF={sf/len(Q)*100:.0f}%')