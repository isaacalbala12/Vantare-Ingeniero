#!/usr/bin/env python3
"""Compare ORIG vs NEW2 on the FULL 22-question original benchmark set"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time

S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}
HISTORICO_A = 'HISTORICO (ultimas 5 vueltas):\nV5: 1:48.2, Fuel 3.1L, TYR 52%, BRK 28%\nV6: 1:48.5, Fuel 3.2L, TYR 58%, BRK 32%\nV7: 1:48.1, Fuel 3.2L, TYR 64%, BRK 35%\nV8: 1:48.9, Fuel 3.3L, TYR 68%, BRK 38%\nV9: 1:49.2, Fuel 3.4L, TYR 72%, BRK 38%'
HISTORICO_E = 'STINT FINAL (ultimas 5 vueltas):\nV30: Lap 1:50.8, Fuel 32.1L, TYR 78/76/74/72%\nV31: Lap 1:51.2, Fuel 28.7L, TYR 82/80/78/76%\nV32: Lap 1:52.1, Fuel 25.3L, TYR 85/83/81/79%\nV33: Lap 1:52.8, Fuel 21.9L, TYR 87/85/83/81%\nV34: Lap 1:53.5, Fuel 18.5L, TYR 88/85/83/80%\n\nANALISIS: Degradacion acelerandose: 2.4s -> 2.7s -> 3.2s -> 3.5s'

ORIG_Q = [
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
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HISTORICO_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento por vuelta?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HISTORICO_E),
    ('L5', 'A', 'Mi degradacion de neumaticos es normal o algo esta mal?', ['20%', 'normal', '5', 'vueltas', 'ok'], HISTORICO_A),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L6', 'A', 'ALO entro boxes, gap VST +2.1s cerrando, P3. Ataco o cubro?', ['undercut', 'VST', 'cubrir', 'ALO']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

ORIG_SYS = 'Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio.'
NEW_SYS = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'

def extract_response(msg):
    if isinstance(msg, dict):
        content = msg.get('content') or ''
        if not content.strip():
            content = msg.get('reasoning_content') or ''
        if not content.strip():
            content = msg.get('reasoning') or ''
        return content.strip()
    return str(msg) if msg else ''

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra:
        parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

async def run():
    print('Comparing ORIG vs NEW2 on full 22-question set')
    print('Running 3 iterations each\n')
    
    results = {'ORIG': [], 'NEW': []}
    
    for run_i in range(3):
        print(f'=== Run {run_i+1}/3 ===')
        
        for prompt_name, sys_prompt in [('ORIG', ORIG_SYS), ('NEW', NEW_SYS)]:
            total_sc = 0
            by_level = {}
            
            async with httpx.AsyncClient() as client:
                tasks = []
                for item in ORIG_Q:
                    tid, q = item[1], item[2]
                    extra = item[4] if len(item) > 4 else None
                    content = build_content(tid, q, extra)
                    payload = {
                        'model': 'step-3.7-flash',
                        'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}],
                        'max_tokens': 500, 'temperature': 0.1, 'thinking': {'type': 'off'}
                    }
                    tasks.append(client.post('https://api.stepfun.ai/step_plan/v1/chat/completions',
                        headers={'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'},
                        json=payload, timeout=120))
                
                responses = await asyncio.gather(*tasks)
                
                for i, item in enumerate(ORIG_Q):
                    lvl, kw = item[0], item[3]
                    text = extract_response(responses[i].json()['choices'][0]['message']) if responses[i].status_code == 200 else ''
                    s = sc(text, kw)
                    total_sc += s
                    if lvl not in by_level:
                        by_level[lvl] = []
                    by_level[lvl].append(s)
            
            pct = total_sc / len(ORIG_Q) * 100
            results[prompt_name].append(pct)
            
            lvl_str = ' '.join(f'{lv}:{sum(by_level[lv])/len(by_level[lv])*100:.0f}' for lv in sorted(by_level.keys()))
            print(f'  {prompt_name}: {pct:.1f}% | {lvl_str}')
    
    print('\n=== SUMMARY (3 runs) ===')
    for name in ['ORIG', 'NEW']:
        runs = results[name]
        avg = sum(runs) / len(runs)
        print(f'{name}: avg={avg:.1f}% runs={[f"{r:.1f}" for r in runs]}')
    
    orig_avg = sum(results['ORIG']) / 3
    new_avg = sum(results['NEW']) / 3
    print(f'\nORIG avg: {orig_avg:.1f}%')
    print(f'NEW avg: {new_avg:.1f}%')
    print(f'DIFF: {new_avg - orig_avg:+.1f}%')

asyncio.run(run())
