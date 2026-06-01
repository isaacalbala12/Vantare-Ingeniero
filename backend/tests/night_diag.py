#!/usr/bin/env python3
"""Quick diagnostic - see actual model responses"""
import httpx

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

T = 'DRV:P3|L10|F:42.3L|TYR:72%|BRK:38%|GAP>VST+2.1s|ALO-1.2s|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
Q = 'Cual es mi posicion y vuelta actual?'

PROMPTS = [
    ('A4', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'),
    ('D1', 'RACE ENGINEER: Short answer. Extract all numbers from telemetry. Output format: P=X L=X F=X. No sentences.'),
    ('V2', 'Eres ingeniero F1. Responde SOLO con numeros. Ej: P3 L10 42.3'),
    ('V4', 'DATA ONLY. P=posicion L=vuelta F=combustible. Responde SOLO con valores. Sin oraciones.'),
    ('NEW1', 'Extract: P=position L=lap F=fuel from telemetry. Reply ONLY with values. Format: P=X L=X F=X. No explanation.'),
    ('NEW2', 'You are a race engineer. Your job is data extraction. Respond with ONLY numbers. Example response: P3 L10 42.3. No sentences. No preamble.'),
]

def ex(m):
    c = (m.get('content') or '').strip()
    if not c: c = (m.get('reasoning') or '').strip()
    return c

for name, sys in PROMPTS:
    # MiniMax
    h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
    r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
        json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': T + '\n' + Q}], 'max_tokens': 50}, timeout=15)
    mm_resp = ex(r.json()['choices'][0]['message']) if r.status_code == 200 else f'ERR:{r.status_code}'
    mm_match = 'P3' in mm_resp and ('L10' in mm_resp or '10' in mm_resp)
    
    # StepFun
    h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
        json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys}, {'role': 'user', 'content': T + '\n' + Q}], 'max_tokens': 50, 'thinking': {'type': 'off'}}, timeout=15)
    sf_resp = ex(r.json()['choices'][0]['message']) if r.status_code == 200 else f'ERR:{r.status_code}'
    sf_match = 'P3' in sf_resp and ('L10' in sf_resp or '10' in sf_resp)
    
    print(f'\n{name}:')
    print(f'  MM ({mm_match}): "{mm_resp}"')
    print(f'  SF ({sf_match}): "{sf_resp}"')
