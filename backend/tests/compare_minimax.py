#!/usr/bin/env python3
"""Compare MiniMax M2.7 vs M3 benchmark results"""
import json

# Load both results
m27_file = "benchmark_results/MiniMax-M2.7_20260601_104526.json"
m3_file = "benchmark_results/MiniMax-M3_20260601_112115.json"

with open(m27_file, encoding="utf-8") as f:
    m27_data = json.load(f)
with open(m3_file, encoding="utf-8") as f:
    m3_data = json.load(f)

def analyze(data):
    results = data["results"]
    total_time = sum(r["elapsed"] for r in results)
    errors = sum(1 for r in results if r["error"])
    
    by_tier = {}
    for r in results:
        tier = r["tier"]
        if tier not in by_tier:
            by_tier[tier] = {"count": 0, "time": 0, "resp_len": 0}
        by_tier[tier]["count"] += 1
        by_tier[tier]["time"] += r["elapsed"]
        by_tier[tier]["resp_len"] += len(r.get("response", ""))
    
    return {
        "total": len(results),
        "time": total_time,
        "avg_time": total_time / len(results),
        "errors": errors,
        "by_tier": by_tier,
    }

m27 = analyze(m27_data)
m3 = analyze(m3_data)

print("="*70)
print("MINIMAX M2.7 vs M3 BENCHMARK COMPARISON")
print("="*70)

print(f"\n{'Model':<20} {'Questions':<10} {'Total Time':<12} {'Avg/Q':<10} {'Errors':<8}")
print("-"*60)
print(f"{'MiniMax-M2.7':<20} {m27['total']:<10} {m27['time']:<12.1f} {m27['avg_time']:<10.1f} {m27['errors']:<8}")
print(f"{'MiniMax-M3':<20} {m3['total']:<10} {m3['time']:<12.1f} {m3['avg_time']:<10.1f} {m3['errors']:<8}")

print(f"\nM3 is {m3['avg_time']/m27['avg_time']:.1f}x SLOWER than M2.7")

print("\n" + "="*70)
print("BY TIER")
print("="*70)

print(f"\n{'Tier':<10} {'M2.7 Avg':<12} {'M3 Avg':<12} {'Ratio':<8}")
print("-"*40)
for tier in sorted(m27["by_tier"].keys()):
    m27_avg = m27["by_tier"][tier]["time"] / m27["by_tier"][tier]["count"]
    m3_avg = m3["by_tier"][tier]["time"] / m3["by_tier"][tier]["count"]
    ratio = m3_avg / m27_avg if m27_avg > 0 else 0
    print(f"{tier:<10} {m27_avg:<12.1f} {m3_avg:<12.1f} {ratio:<8.1f}x")

print("\n" + "="*70)
print("SAMPLE RESPONSES")
print("="*70)

# Show first tier6 response from each
for data, name in [(m27_data, "M2.7"), (m3_data, "M3")]:
    print(f"\n--- {name} Tier6 Q1 (Strategy) ---")
    for r in data["results"]:
        if r["tier"] == "tier6" and r["level"] == "a":
            print(f"\nQ: {r['question']}")
            resp = r["response"][:500] if r["response"] else "[empty]"
            print(f"A: {resp}...")
            print(f"Time: {r['elapsed']:.1f}s")
            break