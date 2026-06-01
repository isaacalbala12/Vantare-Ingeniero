#!/usr/bin/env python3
"""Test StepFun 3.7 different configs"""
import httpx

api_key = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

prompt = 'P3, fuel 42.3L. Cuanto combustible tengo?'

tests = [
    ('step-3.7-flash', {}, 'default'),
    ('step-3.7-flash', {'thinking': {'type': 'off'}}, 'thinking=off'),
    ('step-3.7-flash', {'thinking': {'type': 'block'}}, 'thinking=block'),
    ('step-3.7-flash', {'thinking': {'type': 'reasoning'}}, 'thinking=reasoning'),
    ('step-3.7-flash', {'disable_thinking': True}, 'disable_thinking=True'),
    ('step-3.7-flash', {'reasoning': {'type': 'off'}}, 'reasoning=off'),
    ('step-3.5-flash', {'thinking': {'type': 'off'}}, '3.5-flash thinking=off'),
]

for model, extra, desc in tests:
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'Ingeniero de carrera.'},
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 300,
        **extra
    }
    
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers, json=payload, timeout=30)
    
    if r.status_code == 200:
        data = r.json()
        msg = data['choices'][0]['message']
        content = msg.get('content') or ''
        reasoning = msg.get('reasoning_content') or ''
        
        print(model + ' (' + desc + '):')
        print('  Content: ' + (content[:80] if content else '(empty)'))
        print('  Reasoning: ' + (reasoning[:50] if reasoning else 'None'))
        print('')
    else:
        print(model + ': ERROR ' + str(r.status_code))
        print('')