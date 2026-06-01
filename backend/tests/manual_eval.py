#!/usr/bin/env python3
"""Manual evaluation of M2.7 vs M3 strategic responses"""
import json, os

base = os.path.dirname(os.path.abspath(__file__))
m27_file = os.path.join(base, "benchmark_results", "MiniMax-M2.7_20260601_104526.json")
m3_file = os.path.join(base, "benchmark_results", "MiniMax-M3_20260601_112115.json")

with open(m27_file, encoding="utf-8") as f:
    m27_data = json.load(f)
with open(m3_file, encoding="utf-8") as f:
    m3_data = json.load(f)

# Key questions to evaluate
KEY_QUESTIONS = [
    # Tier 1 - traps
    ("tier1", "b", "DRS question - should NOT exist in LMU"),
    # Tier 2 - technical
    ("tier2", "e", "Critical engine situation"),
    # Tier 4 - strategy
    ("tier4", "a", "When to box?"),
    # Tier 5 - pressure
    ("tier5", "a", "Quick decision - can I finish?"),
    # Tier 6 - full strategy
    ("tier6", "a", "Pit now or continue?"),
    ("tier6", "b", "Defend or let pass?"),
    ("tier6", "c", "Weather change - pit strategy"),
    ("tier6", "e", "Maximum pressure - critical decision"),
]

print("="*80)
print("MANUAL EVALUATION: M2.7 vs M3 STRATEGIC RESPONSES")
print("="*80)

for tier, level, description in KEY_QUESTIONS:
    # Find matching questions
    m27_q = None
    m3_q = None
    
    for r in m27_data["results"]:
        if r["tier"] == tier and r["level"] == level:
            m27_q = r
            break
    
    for r in m3_data["results"]:
        if r["tier"] == tier and r["level"] == level:
            m3_q = r
            break
    
    if not m27_q or not m3_q:
        continue
    
    print(f"\n{'='*80}")
    print(f"EVAL: {description}")
    print(f"Tier: {tier}_{level} | Time: M2.7={m27_q['elapsed']:.1f}s | M3={m3_q['elapsed']:.1f}s")
    print(f"Q: {m27_q['question']}")
    print("-"*80)
    
    print(f"\n>>> M2.7 RESPONSE (len={len(m27_q['response'])})")
    print("-"*40)
    print(m27_q["response"][:1200] if m27_q["response"] else "[EMPTY]")
    
    print(f"\n>>> M3 RESPONSE (len={len(m3_q['response'])})")
    print("-"*40)
    print(m3_q["response"][:1200] if m3_q["response"] else "[EMPTY]")
    
    print("\n" + "-"*40)
    print("ANALYSIS:")
    print("  M2.7:", end=" ")
    
    # Simple heuristics
    m27_score = 0
    m3_score = 0
    
    resp_m27 = m27_q["response"].lower()
    resp_m3 = m3_q["response"].lower()
    
    # Check for hallucination (mentioning DRS when not in LMU)
    if tier == "tier1" and level == "b":
        if "no hay" in resp_m27 or "no disponible" in resp_m27 or "no existe" in resp_m27:
            m27_score += 1
            print("CORRECT (says no data) +1", end="")
        else:
            print("MAYBE HALLUCINATING", end="")
        
        if "no hay" in resp_m3 or "no disponible" in resp_m3 or "no existe" in resp_m3:
            m3_score += 1
            print(" | M3 CORRECT (says no data) +1", end="")
        else:
            print(" | M3 MAYBE HALLUCINATING", end="")
    # Check for actionable advice
    else:
        if any(word in resp_m27 for word in ["box", "pit", "entrar", "boxes", "stop"]):
            m27_score += 1
            print("HAS ACTION (+1)", end="")
        if any(word in resp_m3 for word in ["box", "pit", "entrar", "boxes", "stop"]):
            m3_score += 1
            print(" | M3 HAS ACTION (+1)", end="")
    
    # Check response length - too short may be bad
    if len(m27_q["response"]) > 100:
        m27_score += 1
        print(" | M2.7 SUBSTANTIAL (+1)", end="")
    if len(m3_q["response"]) > 100:
        m3_score += 1
        print(" | M3 SUBSTANTIAL (+1)", end="")
    
    print(f"\n  SCORE: M2.7={m27_score} | M3={m3_score}")
    
    if m27_score > m3_score:
        print("  => M2.7 WINNER")
    elif m3_score > m27_score:
        print("  => M3 WINNER")
    else:
        print("  => TIE")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)