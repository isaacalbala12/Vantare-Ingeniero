#!/usr/bin/env python3
"""Quick test StepFun models"""
import httpx

api_key = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

SYSTEM = 'Eres ingeniero de carrera. Max 2 frases.'
prompt = 'P3, fuel 42.3L. Quanto combustivel tenho?'

tests = [
    ('step-3.5-flash', {}, 'Without extra'),
    ('step-3.5-flash', {'thinking': {'type': 'off'}}, 'With thinking=off'),
    ('step-3.7-flash', {}, 'Without extra'),
    ('step-3.7-flash', {'thinking': {'type': 'off'}}, 'With thinking=off'),
]

for model, extra, desc in tests:
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': prompt}
        ],
        'max_tokens': 300,
        'temperature': 0.1,
        **extra
    }
    
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers, json=payload, timeout=30)
    
    if r.status_code == 200:
        data = r.json()
        msg = data['choices'][0]['message']
        content = msg.get('content') or ''
        reasoning = msg.get('reasoning_content') or ''
        
        keywords = ['42', '42.3', '42,3', 'combustiv']
        matches = sum(1 for k in keywords if k.lower() in content.lower())
        score = matches / len(keywords) * 100
        
        print(model + ' (' + desc + '):')
        print('  Score: ' + str(score) + '%')
        print('  Content: ' + content[:100])
        reasoning_display = reasoning[:50] if reasoning else 'None'
        print('  Reasoning: ' + reasoning_display)
        print('')
    else:
        print(model + ': ERROR ' + str(r.status_code) + ' - ' + r.text[:100])
        print('')