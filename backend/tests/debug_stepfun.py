#!/usr/bin/env python3
"""Debug StepFun 3.7 raw response"""
import httpx, json

api_key = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'
headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

payload = {
    'model': 'step-3.7-flash',
    'messages': [
        {'role': 'user', 'content': 'P3, fuel 42.3L. Cuanto combustible tengo?'}
    ],
    'max_tokens': 300
}

r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers, json=payload, timeout=30)
print('Status:', r.status_code)
data = r.json()
print('Full response:')
print(json.dumps(data, indent=2, ensure_ascii=False)[:1000])