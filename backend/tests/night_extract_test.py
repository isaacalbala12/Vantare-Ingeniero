#!/usr/bin/env python3
"""Compare raw vs smart extraction + test better thinking extraction"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm_v1(msg):
    """Old: strip thinking, take last non-empty line with numbers"""
    content = msg.get('content') or ''
    if content and '<think>' not in content:
        return content.strip()
    think = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    lines = [l.strip() for l in think.split('\n') if l.strip()]
    for line in reversed(lines):
        if any(c.isdigit() for c in line) and len(line) < 120:
            return line
    return think if think else content.strip()

def extract_mm_v2(msg):
    """New: always extract from thinking, take last non-empty line (any content)"""
    content = msg.get('content') or ''
    reasoning = msg.get('reasoning') or ''
    think = reasoning or content
    think = re.sub(r'<think>.*?</think>', '', think, flags=re.DOTALL).strip()
    lines = [l.strip() for l in think.split('\n') if l.strip()]
    return lines[-1] if lines else content.strip()

def extract_mm_v3(msg):
    """New: extract from thinking, take ALL lines with numbers"""
    content = msg.get('content') or ''
    reasoning = msg.get('reasoning') or ''
    think = reasoning or content
    think = re.sub(r'<think>.*?</think>', '', think, flags=re.DOTALL).strip()
    lines = [l.strip() for l in think.split('\n') if l.strip()]
    data_lines = [l for l in lines if any(c.isdigit() for c in l) and len(l) < 150]
    return ' '.join(data_lines) if data_lines else (lines[-1] if lines else '')

def extract_sf(msg):
    content = (msg.get('content') or msg.get('reasoning') or '').strip()
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    content = re.sub(r'^(Answer:|Response:|Datos:|Posición:|Respuesta:|Result:)\s*', '', content, flags=re.IGNORECASE).strip()
    return content

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L5', 'A', 'El consumo esta aumentando? Cuanto perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
]

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|SES:GT3|RACE|38L|WTH:LOW|15C|90%|SC:N',
}

SYS = 'Answer ONLY with numbers from telemetry. No sentences. Example: P3 L10 42.3 2.1s'

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra: parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

print('Testing extraction methods:')
print('='*70)

mm_v1 = mm_v2 = mm_v3 = sf_sc = 0
for item in Q:
    tid, q, kw = item[1], item[2], item[3]
    extra = item[4] if len(item) > 4 else None
    content = build_content(tid, q, extra)
    
    # MM
    h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
    r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
        json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'temperature': 0.1}, timeout=15)
    if r.status_code == 200:
        msg = r.json()['choices'][0]['message']
        v1 = extract_mm_v1(msg)
        v2 = extract_mm_v2(msg)
        v3 = extract_mm_v3(msg)
        mm_v1 += sc(v1, kw)
        mm_v2 += sc(v2, kw)
        mm_v3 += sc(v3, kw)
        if q == Q[0][2]:  # Print first question details
            print(f'Q: {q}')
            print(f'  V1: "{v1[:80]}" -> {sc(v1, kw)*100:.0f}%')
            print(f'  V2: "{v2[:80]}" -> {sc(v2, kw)*100:.0f}%')
            print(f'  V3: "{v3[:80]}" -> {sc(v3, kw)*100:.0f}%')
    
    # SF
    h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
        json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'thinking': {'type': 'off'}}, timeout=15)
    if r.status_code == 200:
        sf_sc += sc(extract_sf(r.json()['choices'][0]['message']), kw)

n = len(Q)
print(f'\nMM V1 (last num line): {mm_v1/n*100:.0f}%')
print(f'MM V2 (last any line): {mm_v2/n*100:.0f}%')
print(f'MM V3 (all num lines): {mm_v3/n*100:.0f}%')
print(f'SF: {sf_sc/n*100:.0f}%')
print(f'AVG best MM: {(max(mm_v1,mm_v2,mm_v3)+sf_sc)/n/2*100:.0f}%')
