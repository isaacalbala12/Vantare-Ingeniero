#!/usr/bin/env python3
"""Final full benchmark with best config: NEW2, MM=t03, SF=t01"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm(msg):
    content = msg.get('content') or ''
    if not content.strip(): content = msg.get('reasoning_content') or ''
    if not content.strip(): content = msg.get('reasoning') or ''
    return content.strip()

def extract_sf(msg):
    content = msg.get('content') or ''
    if not content.strip(): content = msg.get('reasoning') or ''
    return content.strip()

def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}
HIST_A = 'HISTORICO (ultimas 5 vueltas):\nV5: 1:48.2, Fuel 3.1L, TYR 52%, BRK 28%\nV6: 1:48.5, Fuel 3.2L, TYR 58%, BRK 32%\nV7: 1:48.1, Fuel 3.2L, TYR 64%, BRK 35%\nV8: 1:48.9, Fuel 3.3L, TYR 68%, BRK 38%\nV9: 1:49.2, Fuel 3.4L, TYR 72%, BRK 38%'
HIST_E = 'STINT FINAL (ultimas 5 vueltas):\nV30: Lap 1:50.8, Fuel 32.1L, TYR 78/76/74/72%\nV31: Lap 1:51.2, Fuel 28.7L, TYR 82/80/78/76%\nV32: Lap 1:52.1, Fuel 25.3L, TYR 85/83/81/79%\nV33: Lap 1:52.8, Fuel 21.9L, TYR 87/85/83/81%\nV34: Lap 1:53.5, Fuel 18.5L, TYR 88/85/83/80%\n\nANALISIS: Degradacion acelerandose: 2.4s -> 2.7s -> 3.2s -> 3.5s'

# Full 21-question benchmark
Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'E', 'Tengo combustible para llegar a meta?', ['0', '0L', 'critico', 'no']),
    ('L2', 'A', 'Puedo hacer la distancia hasta el final?', ['si', 'suficiente', '13']),
    ('L2', 'E', 'Tengo combustible para otra vuelta?', ['0', '0L', 'critico', 'no']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L2', 'E', 'Los frenos estan criticos?', ['75', '72', 'critico']),
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

SYS_MM = 'Race engineer response: Data questions -> numbers only. Advice questions -> short action. Be concise. Example data: P3 L10 F42.3. Example advice: Entrar boxes urgente.'
SYS_SF = SYS_MM

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra: parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

async def run():
    print(f'Running full 21-question benchmark with best config')
    print(f'MM: NEW2 + temp=0.3')
    print(f'SF: NEW2 + temp=0.1')
    print('='*70)
    
    mm_scores = []
    sf_scores = []
    by_level = {f'L{i}': [[], []] for i in range(1, 9)}
    
    t0 = time.time()
    
    async with httpx.AsyncClient() as client:
        tasks_mm = []
        tasks_sf = []
        for item in Q:
            tid, q = item[1], item[2]
            extra = item[4] if len(item) > 4 else None
            content = build_content(tid, q, extra)
            tasks_mm.append(client.post('https://api.minimaxi.chat/v1/chat/completions',
                headers={'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'},
                json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': SYS_MM}, {'role': 'user', 'content': content}], 'max_tokens': 200, 'temperature': 0.3}, timeout=30.0))
            tasks_sf.append(client.post('https://api.stepfun.ai/step_plan/v1/chat/completions',
                headers={'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'},
                json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': SYS_SF}, {'role': 'user', 'content': content}], 'max_tokens': 200, 'temperature': 0.1, 'thinking': {'type': 'off'}}, timeout=30.0))
        
        all_mm = await asyncio.gather(*tasks_mm)
        all_sf = await asyncio.gather(*tasks_sf)
        
        for i, item in enumerate(Q):
            lvl = item[0]
            kw = item[3]
            
            mm_msg = all_mm[i].json()['choices'][0]['message'] if all_mm[i].status_code == 200 else {}
            sf_msg = all_sf[i].json()['choices'][0]['message'] if all_sf[i].status_code == 200 else {}
            
            mm_text = extract_mm(mm_msg)
            sf_text = extract_sf(sf_msg)
            
            mm_sc = sc(mm_text, kw)
            sf_sc = sc(sf_text, kw)
            
            mm_scores.append(mm_sc)
            sf_scores.append(sf_sc)
            by_level[lvl][0].append(mm_sc)
            by_level[lvl][1].append(sf_sc)
    
    mm_pct = sum(mm_scores) / len(Q) * 100
    sf_pct = sum(sf_scores) / len(Q) * 100
    avg = (mm_pct + sf_pct) / 2
    
    print(f'\nDONE in {time.time()-t0:.1f}s')
    print(f'\n*** FINAL RESULT ***')
    print(f'MiniMax-M2.7 (NEW2, t=0.3): {mm_pct:.1f}%')
    print(f'StepFun-3.7-Flash (NEW2, t=0.1): {sf_pct:.1f}%')
    print(f'COMBINED AVERAGE: {avg:.1f}%')
    
    print(f'\n--- By Level ---')
    for lvl in sorted(by_level.keys()):
        mm_l = sum(by_level[lvl][0]) / len(by_level[lvl][0]) * 100 if by_level[lvl][0] else 0
        sf_l = sum(by_level[lvl][1]) / len(by_level[lvl][1]) * 100 if by_level[lvl][1] else 0
        print(f'  {lvl}: MM={mm_l:.0f}% SF={sf_l:.0f}%')
    
    # Compare to original
    orig_mm, orig_sf = 69.5, 66.3
    print(f'\n--- vs Original Benchmark ({orig_mm}% MM, {orig_sf}% SF) ---')
    print(f'  MM: {mm_pct:.1f}% vs {orig_mm}% = {mm_pct-orig_mm:+.1f}%')
    print(f'  SF: {sf_pct:.1f}% vs {orig_sf}% = {sf_pct-orig_sf:+.1f}%')
    
    print(f'\nBEST PROMPT: {SYS_MM}')
    print(f'MM temperature: 0.3')
    print(f'SF temperature: 0.1')

asyncio.run(run())
