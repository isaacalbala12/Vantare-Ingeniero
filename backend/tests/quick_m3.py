#!/usr/bin/env python3
"""Quick test MiniMax-M3 with 5 questions"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'

Q = [
    ('Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('P3 con VST +2.1s y ALO -1.2s. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
]

ORIG_SYS = 'Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio.'
NEW_SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

def extract_mm(msg):
    content = msg.get('content') or ''
    if not content.strip(): content = msg.get('reasoning_content') or ''
    if not content.strip(): content = msg.get('reasoning') or ''
    return content.strip()

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

for name, sys_p in [('ORIG', ORIG_SYS), ('NEW', NEW_SYS)]:
    print(f'\n=== MiniMax-M3 [{name}] ===')
    total = 0
    for q, kw in Q:
        payload = {'model': 'MiniMax-M3', 'messages': [{'role': 'system', 'content': sys_p}, {'role': 'user', 'content': T + '\n' + q}], 'max_tokens': 500, 'temperature': 0.1}
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h, json=payload, timeout=60)
        if r.status_code == 200:
            text = extract_mm(r.json()['choices'][0]['message'])
            s = sc(text, kw)
            total += s
            print(f'  [{s*100:.0f}%] {q[:40]} -> "{text[:80]}"')
        else:
            print(f'  [ERR {r.status_code}] {q[:40]}')
    print(f'  TOTAL: {total/len(Q)*100:.1f}%')
