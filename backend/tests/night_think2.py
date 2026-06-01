#!/usr/bin/env python3
"""Test MiniMax with thinking:disabled vs adaptive"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L|TYR:72%|BRK:38%|GAP>VST+2.1s|ALO-1.2s|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
Q = 'Cual es mi posicion y vuelta actual?'

SYS = 'ENGINEER RADIO: State position, lap, fuel, gap. Answer ONLY. Example: P3 L10 F42.3 G+2.1'

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

def ex(m):
    c = (m.get('content') or m.get('reasoning') or '').strip()
    c = re.sub(r'<think>.*?</think>', '', c, flags=re.DOTALL).strip()
    return c

for mode in ['default (thinking)', 'thinking:disabled', 'thinking:adaptive']:
    print(f'\n=== {mode} ===')
    payload = {'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': T + '\n' + Q}], 'max_tokens': 60, 'temperature': 0.1}
    if mode == 'thinking:disabled': payload['thinking'] = {'type': 'disabled'}
    elif mode == 'thinking:adaptive': payload['thinking'] = {'type': 'adaptive'}
    
    r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h, json=payload, timeout=15)
    if r.status_code == 200:
        msg = r.json()['choices'][0]['message']
        print('Fields:', list(msg.keys()))
        raw = (msg.get('content') or msg.get('reasoning') or '').strip()
        clean = ex(msg)
        print('RAW[:150]:', repr(raw[:150]))
        print('CLEAN[:150]:', repr(clean[:150]))
        print('Match P3,L10:', 'P3' in clean and 'L10' in clean)
    else:
        print('Error:', r.status_code, r.text[:200])
