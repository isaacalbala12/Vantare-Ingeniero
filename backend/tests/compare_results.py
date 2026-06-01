#!/usr/bin/env python3
"""Compare benchmark results"""
import json, glob, os

files = glob.glob("benchmark_results/*.json")
files.sort()

print("="*70)
print("BENCHMARK RESULTS COMPARISON")
print("="*70)

for f in files:
    with open(f, encoding="utf-8") as fp:
        data = json.load(fp)
    
    model = data["model"]
    results = data["results"]
    
    # Count by tier
    tier_counts = {}
    total_time = 0
    errors = 0
    
    for r in results:
        tier = r["tier"]
        if tier not in tier_counts:
            tier_counts[tier] = 0
        tier_counts[tier] += 1
        total_time += r["elapsed"]
        if r["error"]:
            errors += 1
    
    print(f"\n{model}")
    print(f"  Questions: {len(results)}")
    print(f"  Time: {total_time:.1f}s avg {total_time/len(results):.1f}s/q")
    print(f"  Errors: {errors}")
    
    for tier in sorted(tier_counts.keys()):
        print(f"  {tier}: {tier_counts[tier]} questions")

print("\n" + "="*70)