#!/usr/bin/env python3
"""Debug StepFun - with and without thinking=off"""
import httpx, json

STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

headers = {'Authorization': f'Bearer {STEPFUN_KEY}', 'Content-Type': 'application/json'}
prompt = 'P3, fuel 42.3L. Cuanto combustible tengo?'

tests = [
    ('step-3.5-flash', {}, 'no extra'),
    ('step-3.5-flash', {'thinking': {'type': 'off'}}, 'thinking=off'),
    ('step-3.5-flash', {'reasoning': {'type': 'off'}}, 'reasoning=off'),
    ('step-3.5-flash', {'enable_thinking': False}, 'enable_thinking=False'),
    ('step-3.7-flash', {}, 'no extra'),
    ('step-3.7-flash', {'thinking': {'type': 'off'}}, 'thinking=off'),
]

for model, extra, desc in tests:
    payload = {
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'max_tokens': 200,
        **extra
    }
    
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers, json=payload, timeout=30)
    
    if r.status_code == 200:
        data = r.json()
        msg = data['choices'][0]['message']
        content = msg.get('content') or ''
        reasoning = msg.get('reasoning') or msg.get('reasoning_content') or ''
        
        print(model + ' (' + desc + '):')
        print('  content: "' + content[:80] + '"')
        print('  reasoning: "' + reasoning[:50] + '"')
        print('')
    else:
        print(model + ': ERROR ' + str(r.status_code))