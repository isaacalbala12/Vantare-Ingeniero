#!/usr/bin/env python3
"""Optimize system prompt for benchmark"""
import httpx, time, json

# Keys
MINIMAX_KEY = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TELEMETRIA = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N'
HISTORICO = 'HISTORICO: V5:1:48.2/F3.1L/TYR52% V6:1:48.5/F3.2L/TYR58% V7:1:48.1/F3.2L/TYR64% V8:1:48.9/F3.3L/TYR68% V9:1:49.2/F3.4L/TYR72%'

PROMPTS = [
    ('L1', 'TELEMETRIA: ' + TELEMETRIA, 'Cual es mi posicion y vuelta actual?', ['P3', 'L10']),
    ('L1', 'TELEMETRIA: ' + TELEMETRIA, 'Cuanto combustible tengo?', ['42.3', 'litros']),
    ('L1', 'TELEMETRIA: ' + TELEMETRIA, 'Cual es el consumo por vuelta?', ['3.2']),
    ('L1', 'TELEMETRIA: ' + TELEMETRIA, 'Desgaste neumatico trasero derecho?', ['63']),
    ('L1', 'TELEMETRIA: ' + TELEMETRIA, 'Quien va delante y a cuanto?', ['VST', '2.1']),
    ('L1', 'TELEMETRIA: ' + TELEMETRIA, 'Tengo combustible para llegar?', ['13', 'vueltas']),
    ('L2', 'TELEMETRIA: ' + TELEMETRIA, 'Puedo hacer la distancia?', ['si', '13']),
    ('L2', 'TELEMETRIA: ' + TELEMETRIA, 'Estoy amenazado por ALO?', ['-1.2', 'cerca']),
    ('L2', 'TELEMETRIA: ' + TELEMETRIA, 'Los frenos criticos?', ['38', 'normal']),
    ('L2', 'TELEMETRIA: ' + TELEMETRIA, 'Puedo atacar a VST?', ['2.1', 'si']),
    ('L3', 'TELEMETRIA: ' + TELEMETRIA, 'Combustible 0L. Que hago?', ['entrar', 'urgente']),
    ('L3', 'TELEMETRIA: ' + TELEMETRIA, 'Neumaticos 72%. Estrategia?', ['15', 'gestionar']),
    ('L3', 'TELEMETRIA: ' + TELEMETRIA, 'ALO entra a boxes. Undercut?', ['undercut', 'si']),
    ('L4', 'TELEMETRIA: ' + TELEMETRIA, 'P3, VST+2.1, ALO-1.2, neumaticos 72%. Analiza.', ['P3', 'VST', 'ALO', '72']),
    ('L4', 'TELEMETRIA: ' + TELEMETRIA, '0L combustible, 88% neumaticos, brecha +15.2s. Critico?', ['0L', 'urgente']),
    ('L5', 'TELEMETRIA: ' + TELEMETRIA + '\n' + HISTORICO, 'Consumo aumentando? Cuanto?', ['3.1', '3.4', 'aumentando']),
    ('L5', 'TELEMETRIA: ' + TELEMETRIA + '\n' + HISTORICO, 'Degradacion neumaticos normal?', ['5', 'vueltas', 'normal']),
    ('L5', 'TELEMETRIA: ' + TELEMETRIA + '\n' + HISTORICO, 'Ritmo vs VST?', ['1:48', 'consistent']),
    ('L6', 'TELEMETRIA: ' + TELEMETRIA, '0L, lluvia 90%, 88% neumaticos. Prioridad?', ['combustible', 'urgente']),
    ('L6', 'TELEMETRIA: ' + TELEMETRIA, 'ALO entra, gap VST+2.1s cerrando. Atacar?', ['undercut', 'cubrir']),
    ('L7', 'TELEMETRIA: ' + TELEMETRIA, 'Fuel 5.2L en vuelta 35. Puedo llegar?', ['3.4', 'no']),
    ('L8', 'TELEMETRIA: ' + TELEMETRIA, 'Fuel cayendo 42.3->29.5L en 5 ticks. Tendencia?', ['3.2', '3.4', 'aumentando']),
]

# System prompts to test
SYSTEM_PROMPTS = [
    # V0 - Baseline
    ('v0_baseline', 'You are a race engineer. Answer in 2-3 sentences. Radio style.'),
    
    # V1 - More context
    ('v1_context', 'You are a race engineer for endurance racing. Answer ONLY with the data asked. No explanations. 2 sentences max.'),
    
    # V2 - Direct extraction
    ('v2_direct', 'Race engineer. Extract data: P=position, L=lap, F=fuel liters, TYR=tyre%, BRK=brake%, GAP=gap seconds. Answer with ONLY numbers and names from telemetry. Max 1 sentence.'),
    
    # V3 - Strict format
    ('v3_strict', 'You MUST extract exact values from telemetry. Format: ANSWER: [value]. No thinking. No explanation. Max 5 words.'),
    
    # V4 - Ultra short
    ('v4_ultrashort', 'EXTRACT: position, lap, fuel, tyre%. RESPOND ONLY with the values asked. Example: "P3 L10 42.3L 63%"'),
    
    # V5 - Engineered for extraction
    ('v5_extraction', 'You extract numbers from telemetry. P3 = position 3. L10 = lap 10. F42.3 = 42.3 liters. TYR63 = 63%. GAP+2.1 = 2.1 seconds ahead. Answer: ONLY the extracted values. No sentences. No thinking.'),
]

def extract_response(msg):
    if isinstance(msg, dict):
        content = msg.get('content') or ''
        if not content.strip():
            content = msg.get('reasoning_content') or ''
        if not content.strip():
            content = msg.get('reasoning') or ''
        return content.strip()
    return str(msg) if msg else ''

def test_prompt(system_prompt_name, system_prompt_text, verbose=True):
    results = {'MiniMax': [], 'StepFun': []}
    
    # MiniMax
    headers_mm = {'Authorization': f'Bearer {MINIMAX_KEY}', 'Content-Type': 'application/json'}
    for level, telemetry, question, keywords in PROMPTS:
        payload = {
            'model': 'MiniMax-M2.7',
            'messages': [{'role': 'system', 'content': system_prompt_text}, {'role': 'user', 'content': telemetry + '\n\n' + question}],
            'max_tokens': 200, 'temperature': 0.1
        }
        try:
            r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=headers_mm, json=payload, timeout=60)
            if r.status_code == 200:
                text = extract_response(r.json()['choices'][0]['message'])
                score = sum(1 for k in keywords if k.lower() in text.lower()) / len(keywords)
                results['MiniMax'].append(score)
        except: pass
    
    # StepFun
    headers_sf = {'Authorization': f'Bearer {STEPFUN_KEY}', 'Content-Type': 'application/json'}
    for level, telemetry, question, keywords in PROMPTS:
        payload = {
            'model': 'step-3.7-flash',
            'messages': [{'role': 'system', 'content': system_prompt_text}, {'role': 'user', 'content': telemetry + '\n\n' + question}],
            'max_tokens': 200, 'temperature': 0.1, 'thinking': {'type': 'off'}
        }
        try:
            r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers_sf, json=payload, timeout=60)
            if r.status_code == 200:
                text = extract_response(r.json()['choices'][0]['message'])
                score = sum(1 for k in keywords if k.lower() in text.lower()) / len(keywords)
                results['StepFun'].append(score)
        except: pass
    
    mm_avg = sum(results['MiniMax']) / len(results['MiniMax']) * 100 if results['MiniMax'] else 0
    sf_avg = sum(results['StepFun']) / len(results['StepFun']) * 100 if results['StepFun'] else 0
    combined = (mm_avg + sf_avg) / 2
    
    if verbose:
        print(f'{system_prompt_name}: MiniMax={mm_avg:.1f}% StepFun={sf_avg:.1f}% Combined={combined:.1f}%')
    
    return {'name': system_prompt_name, 'prompt': system_prompt_text, 'MiniMax': mm_avg, 'StepFun': sf_avg, 'Combined': combined}

# Run experiments
print('='*60)
print('PROMPT OPTIMIZATION')
print('='*60)
print()

best = None
for name, text in SYSTEM_PROMPTS:
    result = test_prompt(name, text)
    if best is None or result['Combined'] > best['Combined']:
        best = result

print()
print('='*60)
print('BEST PROMPT: ' + best['name'])
print('='*60)
print('MiniMax:', best['MiniMax'], '%')
print('StepFun:', best['StepFun'], '%')
print('Combined:', best['Combined'], '%')
print()
print('Prompt text:')
print('-'*40)
print(best['prompt'])
print('-'*40)