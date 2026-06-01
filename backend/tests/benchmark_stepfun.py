#!/usr/bin/env python3
"""Benchmark V2 para StepFun API"""
import sys, httpx, json, time, re
sys.stdout.reconfigure(encoding='utf-8')

api_key = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'
base_url = 'https://api.stepfun.ai/step_plan/v1'

SYSTEM = """Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio."""

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|95/97/98/94C|BRK:75/72/68/65%|GAP>ALB:+15.2|d+0.3|<TSU:-8.3|SES:GT3|RACE|38L|3:45|WTH:LOW|15C|90%|+0min|SC:N',
}

HISTORICO_A = """HISTORICO (ultimas 5 vueltas):
V5: 1:48.2, Fuel 3.1L, TYR 52%, BRK 28%
V6: 1:48.5, Fuel 3.2L, TYR 58%, BRK 32%
V7: 1:48.1, Fuel 3.2L, TYR 64%, BRK 35%
V8: 1:48.9, Fuel 3.3L, TYR 68%, BRK 38%
V9: 1:49.2, Fuel 3.4L, TYR 72%, BRK 38%"""

HISTORICO_E = """STINT FINAL (ultimas 5 vueltas):
V30: Lap 1:50.8, Fuel 32.1L, TYR 78/76/74/72%
V31: Lap 1:51.2, Fuel 28.7L, TYR 82/80/78/76%
V32: Lap 1:52.1, Fuel 25.3L, TYR 85/83/81/79%
V33: Lap 1:52.8, Fuel 21.9L, TYR 87/85/83/81%
V34: Lap 1:53.5, Fuel 18.5L, TYR 88/85/83/80%

ANALISIS: Degradacion acelerandose: 2.4s -> 2.7s -> 3.2s -> 3.5s"""

headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}

prompts = [
    # L1 - Extraccion
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'A', 'Quien va delante y a que distancia?', ['VST', '2.1', 'delante']),
    ('L1', 'E', 'Tengo combustible para llegar a meta?', ['0', '0L', 'critico', 'no']),
    
    # L2 - Interpretacion
    ('L2', 'A', 'Puedo hacer la distancia hasta el final?', ['si', 'suficiente', '13']),
    ('L2', 'E', 'Tengo combustible para otra vuelta?', ['0', '0L', 'critico', 'no']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L2', 'E', 'Los frenos estan criticos?', ['75', '72', 'critico']),
    
    # L3 - Triggers
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L3', 'A', 'STINT de 10 vueltas con neumaticos 72%. Estrategia?', ['15', 'entrar', 'gestionar']),
    ('L3', 'A', 'ALO acaba de entrar a boxes. Me ataca por undercut?', ['undercut', 'ALO', 'boxes', 'si']),
    
    # L4 - Multicampo
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza la batalla.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L4', 'E', 'Combustible 0L, neumaticos 88%, brecha ALB +15.2s. Es critico?', ['0L', '88%', 'ALB', 'combustible']),
    
    # L5 - RAG (con historico rico)
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], HISTORICO_A),
    ('L5', 'E', 'La degradacion de neumaticos se esta acelerando? Cuanto mas lento por vuelta?', ['2.4', '3.5', 'acelerando', '+1.1', 'si'], HISTORICO_E),
    ('L5', 'A', 'Mi degradacion de neumaticos es normal o algo esta mal?', ['20%', 'normal', '5', 'vueltas', 'ok'], HISTORICO_A),
    
    # L6 - Multi-trigger
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L6', 'A', 'ALO entro boxes, gap VST +2.1s cerrando, P3. Ataco o cubro?', ['undercut', 'VST', 'cubrir', 'ALO']),
    
    # L7 - Edge cases
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    
    # L8 - Temporal
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

# First, test what model name works
print('=== Testing StepFun Models ===')

models_to_try = ['step-1v', 'step-1', 'step-2', 'step-2-mini', 'step-1-flash', 'step-2-flash']

for model_name in models_to_try:
    try:
        payload = {'model': model_name, 'messages': [
            {'role': 'user', 'content': 'Say hello in 3 words.'}
        ], 'max_tokens': 20}
        r = httpx.post(f'{base_url}/chat/completions', headers=headers, json=payload, timeout=20)
        if r.status_code == 200:
            print(f'✓ {model_name}: OK')
        else:
            print(f'✗ {model_name}: {r.status_code}')
    except Exception as e:
        print(f'✗ {model_name}: {e}')

print('\n=== Starting Benchmark ===')

results_by_level = {}
total_start = time.time()
total_ttft = 0

# Use step-1v as default, can be changed
model = 'step-1v'

for i, args in enumerate(prompts):
    level = args[0]
    tid = args[1]
    q = args[2]
    kw = args[3]
    rag = args[4] if len(args) > 4 else None
    
    user_parts = [f'### TELEMETRIA ###\n{TICKERS.get(tid, "")}']
    if rag:
        user_parts.append(f'\n### HISTORICO ###\n{rag}')
    user_parts.append(f'\n### PREGUNTA ###\n{q}')
    content = '\n'.join(user_parts)
    
    payload = {'model': model, 'messages': [
        {'role': 'system', 'content': SYSTEM},
        {'role': 'user', 'content': content}
    ], 'max_tokens': 500, 'temperature': 0.1}
    
    start = time.time()
    try:
        r = httpx.post(f'{base_url}/chat/completions', headers=headers, json=payload, timeout=120)
        ttft = (time.time() - start) * 1000
        total_ttft += ttft
        
        if r.status_code == 200:
            data = r.json()
            text = data['choices'][0]['message']['content'] or ''
            
            # Try to extract after think tags if present
            match = re.search(r'\s*(.+)', text, re.DOTALL)
            if match:
                text = match.group(1).strip()
            
            matches = sum(1 for k in kw if k.lower() in text.lower())
            score = matches / len(kw) if kw else 0.5
            
            if level not in results_by_level:
                results_by_level[level] = []
            results_by_level[level].append(score)
            
            print(f'[{i+1}/{len(prompts)}] {level}: {score*100:.0f}% | TTFT: {ttft:.0f}ms')
            if i < 3:
                print(f'    Response: {text[:80]}...')
        else:
            print(f'[{i+1}] ERROR: {r.status_code} - {r.text[:100]}')
            if level not in results_by_level:
                results_by_level[level] = []
            results_by_level[level].append(0)
    except Exception as e:
        print(f'[{i+1}] EXCEPTION: {e}')
        if level not in results_by_level:
            results_by_level[level] = []
        results_by_level[level].append(0)

total = time.time() - total_start
avg_ttft = total_ttft / len(prompts) if prompts else 0

# Calculate weighted score
total_score = sum(sum(scores) for scores in results_by_level.values())
total_prompts = sum(len(scores) for scores in results_by_level.values())
weighted = (total_score / total_prompts * 100) if total_prompts > 0 else 0

print(f'\n=== StepFun Results ===')
print(f'Tiempo: {total:.1f}s | Avg TTFT: {avg_ttft:.0f}ms')

for level in sorted(results_by_level.keys()):
    scores = results_by_level[level]
    avg = sum(scores) / len(scores) * 100
    print(f'  {level}: {avg:.1f}% ({len(scores)} prompts)')

print(f'  WEIGHTED: {weighted:.1f}%')