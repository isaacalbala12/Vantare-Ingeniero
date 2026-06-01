#!/usr/bin/env python3
"""Ultra fast prompt test - 5 prompts"""
import httpx

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

T = 'P3|L10|42.3L|72%|VST+2.1s|ALO-1.2s'

Q = [
    ('Posicion?', ['P3', '3']),
    ('Combustible?', ['42.3']),
    ('Gap VST?', ['2.1', 'VST']),
    ('Vuelta?', ['L10', '10']),
    ('Puedo llegar?', ['si', '13']),
]

P = [
    ('A1', 'Extract: P L F. Numbers only. No text. Example: P3 L10 F42.3'),
    ('A2', 'Eres ingeniero F1. Responde SOLO con numeros. Ej: P3 L10 42.3'),
    ('A3', 'EXTRACT numbers. Position, Lap, Fuel, Gap. NO sentences. NO explanation.'),
    ('A4', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only.'),
    ('A5', 'Ingeniero: Extrae valores P=posicion L=vuelta F=fuel. Responde SOLO con numeros. Sin oraciones.'),
]

def ex(m): return (m.get('content') or m.get('reasoning') or '').strip()
def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

for name, sys in P:
    mm = sf = 0
    try:
        h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
        for q, k in Q:
            r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
                json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': T + ' ' + q}], 'max_tokens': 50}, timeout=15)
            if r.status_code == 200: mm += sc(ex(r.json()['choices'][0]['message']), k)
    except: pass
    try:
        h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
        for q, k in Q:
            r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
                json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': T + ' ' + q}], 'max_tokens': 50, 'thinking': {'type': 'off'}}, timeout=15)
            if r.status_code == 200: sf += sc(ex(r.json()['choices'][0]['message']), k)
    except: pass
    print(f'{name}: MM={mm/5*100:.0f}% SF={sf/5*100:.0f}%')