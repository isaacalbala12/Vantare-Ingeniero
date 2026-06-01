#!/usr/bin/env python3
"""Debug: Test if asyncio vs sync produces different results"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, asyncio, time

S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|92/94/98/96C|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|45:22|WTH:MED|22C|30%|+15min|SC:N',
}

Q_TEST = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L1', 'A', 'Cuanto combustible tengo y para cuantas vueltas?', ['42.3', '13', 'L']),
    ('L1', 'A', 'Cual es el consumo promedio por vuelta?', ['3.2', '3.2L']),
    ('L1', 'A', 'Cual es el desgaste del neumatico trasero derecho?', ['63', '63%']),
    ('L1', 'A', 'Quien va delante y a que distancia?', ['VST', '2.1', 'delante']),
]

ORIG_SYS = 'Eres un ingeniero de carrera. Maximo 2-3 frases. Estilo radio.'

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

def build_content(tid, q):
    return f'### TELEMETRIA ###\n{TICKERS.get(tid, "")}\n### PREGUNTA ###\n{q}'

# SYNC test
print('=== SYNC TEST ===')
h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
sync_scores = []
for i, (lvl, tid, q, kw) in enumerate(Q_TEST):
    content = build_content(tid, q)
    payload = {'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': ORIG_SYS}, {'role': 'user', 'content': content}], 'max_tokens': 500, 'temperature': 0.1, 'thinking': {'type': 'off'}}
    r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h, json=payload, timeout=120)
    text = extract_response(r.json()['choices'][0]['message']) if r.status_code == 200 else ''
    s = sc(text, kw)
    sync_scores.append(s)
    print(f'[{i+1}] {q[:40]} -> "{text[:80]}" -> {s*100:.0f}%')
sync_avg = sum(sync_scores) / len(Q_TEST) * 100
print(f'SYNC AVG: {sync_avg:.1f}%')

# ASYNC test
print('\n=== ASYNC TEST ===')
async def test_async():
    async_scores = []
    async with httpx.AsyncClient() as client:
        tasks = []
        for lvl, tid, q, kw in Q_TEST:
            content = build_content(tid, q)
            payload = {'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': ORIG_SYS}, {'role': 'user', 'content': content}], 'max_tokens': 500, 'temperature': 0.1, 'thinking': {'type': 'off'}}
            tasks.append(client.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h, json=payload, timeout=120))
        responses = await asyncio.gather(*tasks)
        for i, (r, (lvl, tid, q, kw)) in enumerate(zip(responses, Q_TEST)):
            text = extract_response(r.json()['choices'][0]['message']) if r.status_code == 200 else ''
            s = sc(text, kw)
            async_scores.append(s)
            print(f'[{i+1}] {q[:40]} -> "{text[:80]}" -> {s*100:.0f}%')
    return sum(async_scores) / len(Q_TEST) * 100

async_avg = asyncio.run(test_async())
print(f'ASYNC AVG: {async_avg:.1f}%')

print(f'\nSYNC: {sync_avg:.1f}% vs ASYNC: {async_avg:.1f}%')
