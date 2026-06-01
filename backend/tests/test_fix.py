#!/usr/bin/env python3
"""Quick test extract_response fix"""
import httpx

STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

headers = {'Authorization': f'Bearer {STEPFUN_KEY}', 'Content-Type': 'application/json'}

def extract_response(msg):
    if isinstance(msg, dict):
        content = msg.get('content') or ''
        if not content.strip():
            content = msg.get('reasoning_content') or ''
        if not content.strip():
            content = msg.get('reasoning') or ''
        return content.strip()
    return str(msg) if msg else ''

payload = {
    'model': 'step-3.5-flash',
    'messages': [{'role': 'user', 'content': 'P3, fuel 42.3L. Cuanto combustivel?'}],
    'max_tokens': 200,
    'thinking': {'type': 'off'}
}

r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers, json=payload, timeout=30)
data = r.json()
msg = data['choices'][0]['message']

print('Raw message fields:', list(msg.keys()))
print('content:', repr(msg.get('content')[:50] if msg.get('content') else 'EMPTY'))
print('reasoning_content:', repr(msg.get('reasoning_content')[:50] if msg.get('reasoning_content') else 'EMPTY'))
print('reasoning:', repr(msg.get('reasoning')[:50] if msg.get('reasoning') else 'EMPTY'))
print()
print('Extracted:', extract_response(msg)[:100])