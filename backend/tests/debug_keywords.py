#!/usr/bin/env python3
"""Debug - see actual content vs expected keywords"""
import httpx

STEPFUN_KEY = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

SYSTEM = 'Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio.'

TELEMETRIA = 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N'

TEST_QUESTIONS = [
    ('Cual es mi posicion?', ['P3', '3', 'posicion']),
    ('Cuanto combustible tengo?', ['42.3', '42', 'combustible']),
    ('En que vuelta voy?', ['10', 'L10', 'vuelta']),
    ('Quien va delante?', ['VST', 'delante', '2.1']),
]

print('Testing StepFun-3.5-flash with broader keywords')
print('='*60)

headers = {'Authorization': f'Bearer {STEPFUN_KEY}', 'Content-Type': 'application/json'}

for question, broad_kw in TEST_QUESTIONS:
    payload = {
        'model': 'step-3.5-flash',
        'messages': [
            {'role': 'system', 'content': SYSTEM},
            {'role': 'user', 'content': '### TELEMETRIA ###\n' + TELEMETRIA + '\n\n### PREGUNTA ###\n' + question}
        ],
        'max_tokens': 300,
        'thinking': {'type': 'off'}
    }
    
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=headers, json=payload, timeout=30)
    
    if r.status_code == 200:
        data = r.json()
        content = data['choices'][0]['message'].get('content') or ''
        
        matches = [kw for kw in broad_kw if kw.lower() in content.lower()]
        missing = [kw for kw in broad_kw if kw.lower() not in content.lower()]
        
        print('\nQ: ' + question)
        print('Keywords: ' + str(broad_kw))
        print('Found: ' + str(matches))
        print('Missing: ' + str(missing))
        print('Content: ' + content[:150])
    else:
        print('ERROR: ' + str(r.status_code))