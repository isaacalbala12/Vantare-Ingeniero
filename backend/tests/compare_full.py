#!/usr/bin/env python3
import httpx, sys
sys.stdout.reconfigure(encoding='utf-8')
M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
Q_TEST = [
    ('Data', 'Cual es mi posicion y vuelta actual?'),
    ('Advice', 'Combustible 0L. Que hago?'),
]

SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

for model in ['MiniMax-M2.7', 'MiniMax-M3']:
    print(f'\n=== {model} ===')
    for tipo, q in Q_TEST:
        print(f'\n[{tipo}] {q}')
        content = f'### TELEMETRIA ###\n{T}\n### PREGUNTA ###\n{q}'
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': model, 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}], 'max_tokens': 300, 'temperature': 0.1}, timeout=60)
        if r.status_code == 200:
            full = r.json()['choices'][0]['message']['content']
            print(f'FULL RESPONSE ({len(full)} chars):')
            print('='*60)
            print(full)
            print('='*60)
            # Check if there's content AFTER the thinking block
            if '</think>' in full:
                after_think = full.split('</think>')[-1].strip()
                print(f'AFTER THINKING: "{after_think}"')
        else:
            print(f'ERR: {r.status_code}')
