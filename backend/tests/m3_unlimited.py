#!/usr/bin/env python3
import httpx, sys
sys.stdout.reconfigure(encoding='utf-8')
M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
HIST = 'HISTORICO (ultimas 5 vueltas):\nV5: 1:48.2, Fuel 3.1L, TYR 52%, BRK 28%\nV6: 1:48.5, Fuel 3.2L, TYR 58%, BRK 32%\nV7: 1:48.1, Fuel 3.2L, TYR 64%, BRK 35%\nV8: 1:48.9, Fuel 3.3L, TYR 68%, BRK 38%\nV9: 1:49.2, Fuel 3.4L, TYR 72%, BRK 38%'

Q = [
    ('L5', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido? Analiza TODO el historico en detalle.', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST),
    ('L3', 'Combustible 0L. Que hago? Dame una respuesta completa y detallada.', ['entrar', 'inmediato', 'urgente']),
]

SYS = 'You are a race engineer. Answer the question completely and in detail. Show all your reasoning.'

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

for model in ['MiniMax-M2.7', 'MiniMax-M3']:
    print(f'\n=== {model} (NO TOKEN LIMIT) ===')
    for lvl, q, kw in Q:
        content = f'### TELEMETRIA ###\n{T}\n### HISTORICO ###\n{kw if isinstance(kw, str) else ""}\n### PREGUNTA ###\n{q}'
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': model, 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}],
            'max_tokens': 32000, 'temperature': 0.1}, timeout=180)
        if r.status_code == 200:
            full = r.json()['choices'][0]['message']['content']
            print(f'[{lvl}] {q[:50]}')
            print(f'FULL ({len(full)} chars):')
            print('='*60)
            print(full)
            print('='*60)
        else:
            print(f'ERR: {r.status_code}')
