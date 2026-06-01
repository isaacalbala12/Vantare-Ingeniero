#!/usr/bin/env python3
"""Debug all models - show actual responses"""
import httpx

# MiniMax
MINIMAX_KEY = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
# StepFun
STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

SYSTEM = 'Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio.'

TELEMETRIA = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N'

TESTS = [
    ('Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('Cuanto combustible tengo?', ['42.3', '42', 'L']),
    ('Quien va delante y a que distancia?', ['VST', '2.1', 'delante']),
]

MODELS = [
    ('MiniMax-M2.7', 'https://api.minimaxi.chat/v1', 'MiniMax-M2.7', MINIMAX_KEY, {}),
    ('StepFun-3.5', 'https://api.stepfun.ai/step_plan/v1', 'step-3.5-flash', STEPFUN_KEY, {'thinking': {'type': 'off'}}),
    ('StepFun-3.7', 'https://api.stepfun.ai/step_plan/v1', 'step-3.7-flash', STEPFUN_KEY, {'thinking': {'type': 'off'}}),
]

for model_name, base_url, model, api_key, extra in MODELS:
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    
    print('\n' + '='*60)
    print('MODEL: ' + model_name)
    print('='*60)
    
    for i, (question, keywords) in enumerate(TESTS):
        payload = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': SYSTEM},
                {'role': 'user', 'content': '### TELEMETRIA ###\n' + TELEMETRIA + '\n\n### PREGUNTA ###\n' + question}
            ],
            'max_tokens': 300,
            'temperature': 0.1,
            **extra
        }
        
        r = httpx.post(base_url + '/chat/completions', headers=headers, json=payload, timeout=30)
        
        if r.status_code == 200:
            data = r.json()
            msg = data['choices'][0]['message']
            content = msg.get('content') or msg.get('reasoning_content') or msg.get('reasoning') or ''
            
            matches = sum(1 for k in keywords if k.lower() in content.lower())
            score = matches / len(keywords) * 100
            
            print('\nQ' + str(i+1) + ': ' + question)
            print('Expected: ' + str(keywords))
            print('Score: ' + str(score) + '%')
            print('Response: ' + content[:200])
        else:
            print('\nQ' + str(i+1) + ': ERROR ' + str(r.status_code))