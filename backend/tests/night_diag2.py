#!/usr/bin/env python3
"""Diagnostic - print exact model responses with keyword matching"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|SES:GT3|RACE|38L|WTH:LOW|15C|90%|SC:N',
}

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
]

PROMPTS = [
    ('A4', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'),
    ('R1', 'RACE ENGINEER RADIO: State ONLY position, lap, fuel, gap. Example: P3 L10 F42.3 G+2.1. No sentences.'),
]

def ex(m):
    raw = (m.get('content') or m.get('reasoning') or '').strip()
    raw = re.sub(r'<think>.*?</think>', '', raw, flags=re.DOTALL).strip()
    raw = re.sub(r'^(Answer:|Response:|Datos:|Posición:|Respuesta:|Result:|Data:)\s*', '', raw, flags=re.IGNORECASE).strip()
    return raw

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

def build_content(tid, q):
    return '### TELEMETRIA ###\n' + TICKERS.get(tid, '') + '\n### PREGUNTA ###\n' + q

for pname, sys_prompt in PROMPTS:
    print(f'\n==== PROMPT: {pname} ====')
    for qname, tid, q, kw in Q:
        content = build_content(tid, q)
        
        # MM
        h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}], 'max_tokens': 60, 'temperature': 0.1}, timeout=15)
        if r.status_code == 200:
            msg = r.json()['choices'][0]['message']
            raw = (msg.get('content') or msg.get('reasoning') or '**EMPTY**').strip()
            clean = ex(msg)
            score = sc(clean, kw)
            print(f'\n  [{qname}] MM score={score*100:.0f}%')
            print(f'    RAW: {repr(raw[:200])}')
            print(f'    CLEAN: {repr(clean[:200])}')
        
        # SF  
        h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
        r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
            json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}], 'max_tokens': 60, 'thinking': {'type': 'off'}}, timeout=15)
        if r.status_code == 200:
            msg = r.json()['choices'][0]['message']
            raw = (msg.get('content') or msg.get('reasoning') or '**EMPTY**').strip()
            clean = ex(msg)
            score = sc(clean, kw)
            print(f'  [{qname}] SF score={score*100:.0f}%')
            print(f'    RAW: {repr(raw[:200])}')
            print(f'    CLEAN: {repr(clean[:200])}')
