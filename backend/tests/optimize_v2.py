#!/usr/bin/env python3
"""Iterate on best prompts"""
import httpx

MINIMAX_KEY = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TELE = 'DRV:P3|L10|F:42.3L|TYR:72/68|BRK:38|GAP>VST:+2.1|<ALO:-1.2|SES:HY|RACE|WTH:MED|22C|30%|SC:N'

PROMPTS = [
    ('Posicion y vuelta?', ['P3', 'L10']),
    ('Combustible?', ['42.3']),
    ('Quien delante y gap?', ['VST', '2.1']),
    ('Consumo?', ['3.2']),
    ('Puedo hacer distancia?', ['13']),
    ('Neumatico trasero?', ['68']),
    ('Frenos?', ['38']),
    ('Amenazado por ALO?', ['1.2']),
    ('Combustible 0L. Que hago?', ['entrar']),
]

def ex(msg):
    return (msg.get('content') or msg.get('reasoning') or '').strip()

def sc(text, kw):
    return sum(1 for k in kw if k.lower() in text.lower()) / len(kw)

SYSTEMS = [
    ('SPANISH1', 'Eres ingeniero de carreras. Extrae SOLO los valores numericos. No oraciones. Ejemplo: P3 L10 42.3 3.2'),
    ('SPANISH2', 'Ingeniero F1. Responde SOLO con datos numericos. P=posicion, L=vuelta, F=combustible. Ejemplo: P3 L10 42.3L'),
    ('SPANISH3', 'ENGINEER MODE: Extract exact numbers. P=position, L=lap, F=fuel. Answer ONLY with numbers from data. No sentences.'),
    ('SPANISH4', 'Race engineer. EXTRACT: P, L, F, TYR%, gap values. RESPOND with raw data only. No explanation. No thinking.'),
    ('SPANISH5', 'Eres ingeniero de carrera. Responde SOLO con los valores numericos del telemetry. Sin oraciones. Sin pensar. Solo numeros.'),
]

print('Testing Spanish-focused prompts:')
print('='*50)

for name, sys in SYSTEMS:
    mm_scores = []
    sf_scores = []
    
    # MiniMax
    h = {'Authorization': f'Bearer {MINIMAX_KEY}', 'Content-Type': 'application/json'}
    for q, kw in PROMPTS:
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', 
            headers=h, 
            json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': TELE + '\n' + q}], 'max_tokens': 80}, 
            timeout=20)
        if r.status_code == 200:
            mm_scores.append(sc(ex(r.json()['choices'][0]['message']), kw))
    
    # StepFun
    h = {'Authorization': f'Bearer {STEPFUN_KEY}', 'Content-Type': 'application/json'}
    for q, kw in PROMPTS:
        r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions',
            headers=h,
            json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': TELE + '\n' + q}], 'max_tokens': 80, 'thinking': {'type': 'off'}},
            timeout=20)
        if r.status_code == 200:
            sf_scores.append(sc(ex(r.json()['choices'][0]['message']), kw))
    
    mm_avg = sum(mm_scores)/len(mm_scores)*100 if mm_scores else 0
    sf_avg = sum(sf_scores)/len(sf_scores)*100 if sf_scores else 0
    print(f'{name}: MM={mm_avg:.0f}% SF={sf_avg:.0f}% (avg={(mm_avg+sf_avg)/2:.0f}%)')