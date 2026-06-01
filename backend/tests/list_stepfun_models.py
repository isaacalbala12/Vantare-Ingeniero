#!/usr/bin/env python3
"""List available StepFun models"""
import httpx, json

api_key = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

r = httpx.get('https://api.stepfun.ai/step_plan/v1/models', headers=headers, timeout=10)
models = r.json()['data']
print('Available StepFun models:')
for m in models:
    print('  - ' + m['id'])