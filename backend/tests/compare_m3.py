#!/usr/bin/env python3
import httpx, sys, time
sys.stdout.reconfigure(encoding='utf-8')
M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

T = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
Q = [
    ('Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
]
SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

for model in ['MiniMax-M2.7', 'MiniMax-M3']:
    print(f'\n=== {model} ===')
    total = 0
    t0 = time.time()
    for q, kw in Q:
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': model, 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': T+'\n'+q}], 'max_tokens': 200, 'temperature': 0.1}, timeout=60)
        text = r.json()['choices'][0]['message']['content'] if r.status_code==200 else ''
        s = sc(text, kw)
        total += s
        print(f'  [{s*100:.0f}%] "{text[:100]}"')
    print(f'  AVG: {total/len(Q)*100:.1f}% | Time: {time.time()-t0:.1f}s')
