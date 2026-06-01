#!/usr/bin/env python3
import httpx, sys
sys.stdout.reconfigure(encoding='utf-8')
M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
Q = [
    ('Data', 'Cual es mi posicion y vuelta actual?'),
    ('Advice', 'Combustible 0L. Que hago?'),
    ('Mixed', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%. Analiza.'),
]

SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

for model in ['MiniMax-M2.7', 'MiniMax-M3']:
    print(f'\n=== {model} ===')
    for tipo, q in Q:
        print(f'\n[{tipo}] {q}')
        content = f'### TELEMETRIA ###\n{T}\n### PREGUNTA ###\n{q}'
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': model, 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}], 'max_tokens': 300, 'temperature': 0.1}, timeout=60)
        if r.status_code == 200:
            msg = r.json()['choices'][0]['message']
            print(f'Keys: {list(msg.keys())}')
            print(f'content[:150]: {repr(msg.get("content", "")[:150])}')
            print(f'reasoning_content[:150]: {repr(msg.get("reasoning_content", "")[:150])}')
            print(f'reasoning[:150]: {repr(msg.get("reasoning", "")[:150])}')
            # Check which field is populated
            for k in msg.keys():
                val = msg[k]
                if val and len(str(val)) > 10:
                    print(f'{k} populated: {len(str(val))} chars')
        else:
            print(f'ERR: {r.status_code}')
