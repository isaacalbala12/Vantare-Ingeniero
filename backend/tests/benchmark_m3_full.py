#!/usr/bin/env python3
import httpx, sys, time
sys.stdout.reconfigure(encoding='utf-8')
M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}
HIST_A = 'HISTORICO (ultimas 5 vueltas):\nV5: 1:48.2, Fuel 3.1L, TYR 52%, BRK 28%\nV6: 1:48.5, Fuel 3.2L, TYR 58%, BRK 32%\nV7: 1:48.1, Fuel 3.2L, TYR 64%, BRK 35%\nV8: 1:48.9, Fuel 3.3L, TYR 68%, BRK 38%\nV9: 1:49.2, Fuel 3.4L, TYR 72%, BRK 38%'
HIST_E = 'STINT FINAL (ultimas 5 vueltas):\nV30: Lap 1:50.8, Fuel 32.1L, TYR 78/76/74/72%\nV31: Lap 1:51.2, Fuel 28.7L, TYR 82/80/78/76%\nV32: Lap 1:52.1, Fuel 25.3L, TYR 85/83/81/79%\nV33: Lap 1:52.8, Fuel 21.9L, TYR 87/85/83/81%\nV34: Lap 1:53.5, Fuel 18.5L, TYR 88/85/83/80%\n\nANALISIS: Degradacion acelerandose: 2.4s -> 2.7s -> 3.2s -> 3.5s'

Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'A', 'Quien va delante y a que distancia?', ['VST', '2.1', 'delante']),
    ('L1', 'E', 'Tengo combustible para llegar a meta?', ['0', '0L', 'critico', 'no']),
    ('L2', 'A', 'Puedo hacer la distancia hasta el final?', ['si', 'suficiente', '13']),
    ('L2', 'E', 'Tengo combustible para otra vuelta?', ['0', '0L', 'critico', 'no']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L2', 'E', 'Los freins estan criticos?', ['75', '72', 'critico']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
    ('L3', 'A', 'ALO acaba de entrar a boxes. Me ataca por undercut?', ['undercut', 'ALO', 'boxes', 'si']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza la batalla.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L4', 'E', 'Combustible 0L, neumaticos 88%, brecha ALB +15.2s. Es critico?', ['0L', '88%', 'ALB', 'combustible']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HIST_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento por vuelta?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HIST_E),
    ('L5', 'A', 'Mi degradacion de neumaticos es normal o algo esta mal?', ['20%', 'normal', '5', 'vueltas', 'ok'], HIST_A),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L6', 'A', 'ALO entro boxes, gap VST +2.1s cerrando, P3. Ataco o cubro?', ['undercut', 'VST', 'cubrir', 'ALO']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes.'

def extract_answer(content):
    if '</think>' in content:
        after = content.split('</think>')[-1].strip()
        if after: return after
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    return lines[-1] if lines else content[:200]

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}

print('MiniMax-M3 FULL Benchmark (22q, 8000 tokens)\n' + '='*60)
t0 = time.time()
total = 0
by_level = {}

for i, item in enumerate(Q):
    lvl, tid, q, kw = item[0], item[1], item[2], item[3]
    extra = item[4] if len(item) > 4 else None
    
    content = f'### TELEMETRIA ###\n{TICKERS[tid]}\n'
    if extra: content += f'### HISTORICO ###\n{extra}\n'
    content += f'### PREGUNTA ###\n{q}'
    
    r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
        json={'model': 'MiniMax-M3', 'messages': [{'role': 'system', 'content': SYS}, {'role': 'user', 'content': content}],
        'max_tokens': 8000, 'temperature': 0.1}, timeout=120)
    
    if r.status_code == 200:
        text = extract_answer(r.json()['choices'][0]['message']['content'])
        s = sc(text, kw)
        total += s
        if lvl not in by_level: by_level[lvl] = []
        by_level[lvl].append(s)
        print(f'[{i+1:2d}/{len(Q)}] {lvl}: {s*100:.0f}% | {q[:35]}')
    else:
        print(f'[{i+1:2d}] ERR {r.status_code}')

print(f'\nTOTAL: {total/len(Q)*100:.1f}% ({time.time()-t0:.1f}s)')
print('\nBy Level:')
for lv in sorted(by_level.keys()):
    print(f'  {lv}: {sum(by_level[lv])/len(by_level[lv])*100:.1f}%')
