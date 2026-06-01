#!/usr/bin/env python3
import httpx, sys, time
sys.stdout.reconfigure(encoding='utf-8')
M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

T = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N'
HIST = 'HISTORICO:\nV5: 1:48.2/F3.1L V6: 1:48.5/F3.2L V7: 1:48.1/F3.2L V8: 1:48.9/F3.3L V9: 1:49.2/F3.4L'

Q = [
    ('L1', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L2', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L4', 'P3 con VST +2.1s y ALO -1.2s. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'El consumo esta aumentando? Cuanto?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST),
    ('L6', 'Combustible 0L, lluvia 90%, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
]

SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

print('MiniMax-M3 Benchmark Test\n' + '='*50)
total = 0
t0 = time.time()

for item in Q:
    lvl = item[0]
    q = item[1]
    kw = item[2]
    extra = item[3] if len(item) > 3 and isinstance(item[3], str) else None

    content = f'### TELEMETRIA ###\n{T}\n### PREGUNTA ###\n{q}'
    
    r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
        json={'model': 'MiniMax-M3', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}], 'max_tokens': 200, 'temperature': 0.1}, timeout=60)
    
    if r.status_code == 200:
        text = r.json()['choices'][0]['message']['content']
        s = sc(text, kw)
        total += s
        print(f'[{lvl}] {s*100:.0f}% | {q[:40]}')
        print(f'    -> "{text[:100]}"')
    else:
        print(f'[{lvl}] ERR {r.status_code}: {r.text[:100]}')

print(f'\nTOTAL: {total/len(Q)*100:.1f}% ({time.time()-t0:.1f}s)')
