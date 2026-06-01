#!/usr/bin/env python3
"""Test MiniMax with thinking disabled vs enabled"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L|TYR:72%|BRK:38%|GAP>VST+2.1s|ALO-1.2s|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
Q = 'Cual es mi posicion y vuelta actual?'

SYS = 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'

def ex(m):
    c = (m.get('content') or m.get('reasoning') or '').strip()
    c = re.sub(r'<think>.*?</think>', '', c, flags=re.DOTALL).strip()
    return c

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

# Test with thinking ON (default)
print('=== With thinking ON (default) ===')
r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
    json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': T + '\n' + Q}], 'max_tokens': 60, 'temperature': 0.1}, timeout=15)
msg = r.json()['choices'][0]['message']
print('Fields:', list(msg.keys()))
print('Content:', repr(msg.get('content', '')[:300]))
print('Reasoning:', repr(msg.get('reasoning', '')[:300]))
print('Cleaned:', repr(ex(msg)[:200]))

# Test with thinking OFF
print('\n=== With thinking OFF ===')
r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
    json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': T + '\n' + Q}], 'max_tokens': 60, 'temperature': 0.1, 'thinking': {'type': 'off'}}, timeout=15)
if r.status_code == 200:
    msg = r.json()['choices'][0]['message']
    print('Fields:', list(msg.keys()))
    print('Content:', repr(msg.get('content', '')[:300]))
    print('Reasoning:', repr(msg.get('reasoning', '')[:300]))
    print('Cleaned:', repr(ex(msg)[:200]))
else:
    print('Error:', r.status_code, r.text[:200])

# Test with reasoning_content field
print('\n=== Check for reasoning_content field ===')
r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
    json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': T + '\n' + Q}], 'max_tokens': 60, 'temperature': 0.1}, timeout=15)
msg = r.json()['choices'][0]['message']
print('All keys:', [k for k in msg.keys()])
rc = msg.get('reasoning_content', '')
print('reasoning_content:', repr(rc[:200]) if rc else 'EMPTY')
