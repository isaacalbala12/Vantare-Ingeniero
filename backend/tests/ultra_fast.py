#!/usr/bin/env python3
"""Ultra fast - 5 prompts x 3 iterations"""
import httpx

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'
T = 'P3|L10|42.3L|72%|VST+2.1s|ALO-1.2s'

Q = [('P/L?', ['P3', 'L10']), ('Fuel?', ['42.3']), ('Gap?', ['2.1', 'VST']), ('Frenos?', ['38']), ('Puedo?', ['si', '13'])]

P = [
    ('BEST', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'),
    ('V2', 'EXTRACT: P, L, F values. Answer ONLY with numbers. No sentences. No explanation.'),
    ('V3', 'ENGINEER MODE: Extract position lap fuel. Respond ONLY with data. Max 5 words. No sentences.'),
]

def ex(m): return (m.get('content') or m.get('reasoning') or '').strip()
def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

for name, sys in P:
    mm = sf = 0
    h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
    for q, k in Q:
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': T + ' ' + q}], 'max_tokens': 40}, timeout=12)
        if r.status_code == 200: mm += sc(ex(r.json()['choices'][0]['message']), k)
    h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
    for q, k in Q:
        r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
            json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': T + ' ' + q}], 'max_tokens': 40, 'thinking': {'type': 'off'}}, timeout=12)
        if r.status_code == 200: sf += sc(ex(r.json()['choices'][0]['message']), k)
    print(f'{name}: MM={mm/5*100:.0f}% SF={sf/5*100:.0f}%')