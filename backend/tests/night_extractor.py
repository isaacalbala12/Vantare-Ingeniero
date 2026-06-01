#!/usr/bin/env python3
"""Smart extractor - handles both thinking and direct response models"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import httpx, re

M = 'sk-cp-lVwmDjCdt5oqMiU5ySsVmOc_SrOQy0w3wawWINLKZOcbm0Q79cRhBp8ssD6ZmFqHVW9wZbBJnRsX93MuzzUl66UK6vglNxOo2czPx1sIXB79TFtfET-IUs0'
S = '5vQAZ5OKkVI0TrH09d5do3bul1pww94VaRrj3MjcSa2o8dHYDoWdpGp1iltDpvOJo'

def extract_mm(msg):
    """Extract from MiniMax - answer is usually in thinking content."""
    content = msg.get('content') or ''
    reasoning = msg.get('reasoning') or ''
    
    # If content is clean (no thinking tags), use it
    if content and '<think>' not in content and '</think>' not in content:
        return content.strip()
    
    # Otherwise extract from thinking
    think = reasoning or content
    # Remove thinking tags
    think = re.sub(r'<think>.*?</think>', '', think, flags=re.DOTALL).strip()
    
    # Look for answer patterns in the thinking
    # Pattern: "Position is X", "Lap is Y", "Fuel is Z", etc.
    # Also look for the last part of thinking (usually the conclusion)
    lines = think.split('\n')
    
    # Try to find lines with the data
    data_lines = []
    for line in lines:
        line = line.strip()
        if any(c in line for c in '0123456789') and len(line) < 100:
            data_lines.append(line)
    
    if data_lines:
        return data_lines[-1]
    return think if think else content.strip()

def extract_sf(msg):
    """Extract from StepFun - answer is in content or reasoning."""
    content = msg.get('content') or ''
    if not content.strip():
        content = msg.get('reasoning') or ''
    
    # Remove thinking tags if present
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    
    # Remove common prefixes
    content = re.sub(r'^(Answer:|Response:|Datos:|Posición:|Respuesta:|Result:|Data:)\s*', '', content, flags=re.IGNORECASE).strip()
    return content

def ex_mm(m): return extract_mm(m)
def ex_sf(m): return extract_sf(m)
def sc(t, k): return sum(1 for x in k if x.lower() in t.lower()) / len(k)

# Test questions
Q = [
    ('L1', 'A', 'Cual es mi posicion y vuelta actual?', ['P3', 'L10', '3', '10']),
    ('L2', 'A', 'Estoy amenazado por ALO desde atras?', ['-1.2', 'si', 'cerca']),
    ('L3', 'E', 'Combustible 0L. Que hago?', ['entrar', 'inmediato', 'urgente']),
    ('L4', 'A', 'P3 con VST +2.1s y ALO -1.2s. Neumaticos 72%, combustible 42.3L. Analiza.', ['P3', 'VST', 'ALO', '72%', '42.3']),
    ('L5', 'A', 'El consumo de combustible esta aumentando? Cuanto he ganado o perdido?', ['3.1', '3.4', 'aumentando', '+0.3', 'si'], 'V5:1:48.2/F3.1L V6:1:48.5/F3.2L V7:1:48.1/F3.2L V8:1:48.9/F3.3L V9:1:49.2/F3.4L'),
    ('L6', 'E', 'Combustible 0L, lluvia 90% ahora, neumaticos 88%. Prioridad?', ['combustible', 'urgente', 'entrar', 'lluvia']),
    ('L7', 'E', 'Fuel 5.2L en vuelta 35 de 38. Puedo hacer las 3 vueltas restantes?', ['3.4', '0', 'no', 'critico']),
    ('L8', 'A', 'Fuel cayendo: 42.3L -> 39.1L -> 35.9L -> 32.7L -> 29.5L en 5 ticks. Cual es la tendencia?', ['3.2', '3.3', '3.4', 'aumentando']),
]

TICKERS = {
    'A': 'DRV:P3|L10|F:42.3L/3.2(13L)|TYR:72/68/65/63|BRK:38/35/22/20%|GAP>VST:+2.1|d-0.3|<ALO:-1.2|SES:HY|RACE|38L|WTH:MED|22C|30%|SC:N',
    'E': 'DRV:P12|L35|F:5.2L/3.4(0L)|TYR:88/85/83/80|BRK:75/72/68/65%|GAP>ALB:+15.2|SES:GT3|RACE|38L|WTH:LOW|15C|90%|SC:N',
}

def build_content(tid, q, extra):
    parts = ['### TELEMETRIA ###\n' + TICKERS.get(tid, '')]
    if extra:
        parts.append('\n### HISTORICO ###\n' + extra)
    parts.append('\n### PREGUNTA ###\n' + q)
    return '\n'.join(parts)

print('Testing smart extractor with different prompts')
print('='*70)

# Different prompts to test
PROMPTS = [
    ('A4', 'RACE ENGINEER: Answer with ONLY data values. Position Lap Fuel Gap. Numbers only. NO sentences.'),
    ('R1', 'RACE ENGINEER RADIO: State ONLY position, lap, fuel, gap. Example: P3 L10 F42.3 G+2.1. No sentences.'),
    ('C3', 'EXTRACCION: Extrae P L F gap. Responde SOLO con numeros. Sin oraciones. Ej: P3 L10 42.3 2.1s'),
    ('D1', 'RACE ENGINEER: Short answer. Extract all numbers from telemetry. Output format: P=X L=X F=X. No sentences.'),
    ('E1', 'ENGINEER: P/L/F/gap extraction. Answer ONLY. Example: P3 L10 42.3 2.1s. No sentences.'),
    ('NEW', 'You are a race engineer. Short direct answers. Extract P, L, F, Gap. No explanation. No preamble.'),
]

results = []
for pname, sys_prompt in PROMPTS:
    mm_total = sf_total = 0
    for item in Q:
        tid = item[1]
        q = item[2]
        kw = item[3]
        extra = item[4] if len(item) > 4 else None
        content = build_content(tid, q, extra)
        
        # MM
        h = {'Authorization': f'Bearer {M}', 'Content-Type': 'application/json'}
        r = httpx.post('https://api.minimaxi.chat/v1/chat/completions', headers=h,
            json={'model': 'MiniMax-M2.7', 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'temperature': 0.1}, timeout=15)
        if r.status_code == 200:
            text = ex_mm(r.json()['choices'][0]['message'])
            mm_total += sc(text, kw)
        
        # SF
        h = {'Authorization': f'Bearer {S}', 'Content-Type': 'application/json'}
        r = httpx.post('https://api.stepfun.ai/step_plan/v1/chat/completions', headers=h,
            json={'model': 'step-3.7-flash', 'messages': [{'role': 'system', 'content': sys_prompt}, {'role': 'user', 'content': content}], 'max_tokens': 80, 'thinking': {'type': 'off'}}, timeout=15)
        if r.status_code == 200:
            text = ex_sf(r.json()['choices'][0]['message'])
            sf_total += sc(text, kw)
    
    mm_pct = mm_total / len(Q) * 100
    sf_pct = sf_total / len(Q) * 100
    avg = (mm_pct + sf_pct) / 2
    results.append((pname, mm_pct, sf_pct, avg, sys_prompt))
    print(f'{pname}: MM={mm_pct:.0f}% SF={sf_pct:.0f}% AVG={avg:.0f}% | {sys_prompt[:55]}')

results.sort(key=lambda x: x[3], reverse=True)
print('\n--- RANKING ---')
for n, mm, sf, avg, _ in results:
    print(f'{n}: MM={mm:.0f}% SF={sf:.0f}% AVG={avg:.0f}%')
print(f'\nBEST: {results[0][0]} AVG={results[0][3]:.0f}%')
