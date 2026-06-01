#!/usr/bin/env python3
"""Debug SF response structure - what fields are populated?"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, json

S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TICKERS = {
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}

SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

Q_L3 = 'Combustible 0L. Que hago?'

content = f'### TELEMETRIA ###\n{TICKERS["E"]}\n### PREGUNTA ###\n{Q_L3}'

for thinking_val in ['off', 'disabled', None]:
    print(f'\n=== thinking={thinking_val} ===')
    payload = {
        'model': 'step-3.7-flash',
        'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}],
        'max_tokens': 200,
        'temperature': 0.1
    }
    if thinking_val:
        payload['thinking'] = {'type': thinking_val}
    
    h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h, json=payload, timeout=30)
    
    if r.status_code == 200:
        msg = r.json()['choices'][0]['message']
        print('Fields:', list(msg.keys()))
        print('content[:200]:', repr((msg.get('content') or '')[:200]))
        print('reasoning[:200]:', repr((msg.get('reasoning') or '')[:200]))
        print('reasoning_content[:200]:', repr((msg.get('reasoning_content') or '')[:200]))
        
        # Try benchmark extraction
        content_val = msg.get('content') or ''
        if not content_val.strip():
            content_val = msg.get('reasoning') or ''
        print('Extracted:', repr(content_val[:100]))
        print('Match "entrar":', 'entrar' in content_val.lower())
    else:
        print(f'Error: {r.status_code}', r.text[:200])
