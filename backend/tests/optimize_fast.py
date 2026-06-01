#!/usr/bin/env python3
"""Quick prompt optimization - 10 prompts"""
import httpx, time

MINIMAX_KEY = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TELEMETRIA = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'

PROMPTS = [
    ('Cual es mi posicion?', ['P3', '3']),
    ('Cuanto combustible tengo?', ['42.3', 'litros']),
    ('En que vuelta voy?', ['L10', '10']),
    ('Quien va delante y cuanto?', ['VST', '2.1']),
    ('Consumo por vuelta?', ['3.2']),
    ('Puedo hacer la distancia?', ['13', 'si']),
    ('Neumaticos trasero derecho?', ['72']),
    ('Frenos criticos?', ['38', 'normal']),
    ('Estoy amenazado por ALO?', ['-1.2', 'cerca']),
    ('Combustible 0L. Que hago?', ['entrar', 'urgente']),
]

SYSTEMS = [
    ('BASELINE', 'You are a race engineer. Answer briefly.'),
    ('EXTRACT', 'Extract ONLY numbers and names from telemetry. No sentences. Answer with raw data.'),
    ('ENGINEER', 'Race engineer mode. Extract exact values. P=position, L=lap, F=fuel liters. Answer with numbers only.'),
    ('DIRECT', 'Answer with EXACT values from telemetry. No explanation. Example: P3 L10 F42.3'),
    ('ULTRA', 'EXTRACT: position, lap, fuel, tyre%, gap. RESPOND: only values from data. Format: P3 L10 42.3'),
]

def extract(msg):
    c = msg.get('content') or msg.get('reasoning') or msg.get('reasoning_content') or ''
    return c.strip()

def score(text, kw):
    return sum(1 for k in kw if k.lower() in text.lower()) / len(kw)

results = []
for name, sys in SYSTEMS:
    print(name + '...', end=' ', flush=True)
    
    # MiniMax
    mm_scores = []
    headers = {'Authorization': f'Bearer {MINIMAX_KEY}', 'Content-Type': 'application/json'}
    for q, kw in PROMPTS:
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', 
            headers=headers, json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': TELEMETRIA + '\n' + q}], 'max_tokens': 100}, timeout=30)
        if r.status_code == 200:
            mm_scores.append(score(extract(r.json()['choices'][0]['message']), kw))
    
    # StepFun
    sf_scores = []
    headers = {'Authorization': f'Bearer {STEPFUN_KEY}', 'Content-Type': 'application/json'}
    for q, kw in PROMPTS:
        r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions',
            headers=headers, json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': TELEMETRIA + '\n' + q}], 'max_tokens': 100, 'thinking': {'type': 'off'}}, timeout=30)
        if r.status_code == 200:
            sf_scores.append(score(extract(r.json()['choices'][0]['message']), kw))
    
    mm_avg = sum(mm_scores)/len(mm_scores)*100 if mm_scores else 0
    sf_avg = sum(sf_scores)/len(sf_scores)*100 if sf_scores else 0
    results.append((name, sys, mm_avg, sf_avg))
    print(f'MM={mm_avg:.0f}% SF={sf_avg:.0f}%')

print()
print('BEST:')
best = max(results, key=lambda x: (x[2]+x[3])/2)
print(f'{best[0]}: MM={best[2]:.0f}% SF={best[3]:.0f}%')
print(f'System: {best[1]}')