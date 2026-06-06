#!/usr/bin/env python3
"""Benchmark de latencia del SpotterService.evaluate()."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from src.intelligence.spotter import SpotterService  # noqa: E402


def _make_tick(i: int) -> dict:
    return {
        "in_pits": i % 17 == 0,
        "pit_limiter_active": i % 23 == 0,
        "gap_ahead": 0.3 + (i % 5) * 0.1,
        "gap_behind": 0.4 + (i % 7) * 0.1,
        "damage_aero": 0.0,
        "suspension_damage": 0.0,
        "safety_car_active": i % 500 == 0,
        "full_course_yellow_active": False,
        "session_laps_left": 10.0,
        "estimated_laps_remaining": 5.0,
        "session_type": "race",
        "pos_x": float(i % 100),
        "pos_y": 0.0,
        "pos_z": float(i % 200),
        "competitors": [],
    }


def run_benchmark(ticks: int = 10_000) -> dict:
    spotter = SpotterService()
    samples_ms: list[float] = []

    for i in range(ticks):
        tick = _make_tick(i)
        start = time.perf_counter()
        spotter.evaluate(tick)
        samples_ms.append((time.perf_counter() - start) * 1000)

    avg_ms = statistics.mean(samples_ms)
    sorted_ms = sorted(samples_ms)
    p99_index = min(len(sorted_ms) - 1, int(len(sorted_ms) * 0.99))
    p99_ms = sorted_ms[p99_index]
    throughput_hz = 1000.0 / avg_ms if avg_ms > 0 else 0.0

    return {
        "ticks": ticks,
        "avg_ms": round(avg_ms, 4),
        "p99_ms": round(p99_ms, 4),
        "throughput_hz": round(throughput_hz, 2),
        "max_ms": round(max(samples_ms), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark SpotterService.evaluate()")
    parser.add_argument("--ticks", type=int, default=10_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".omo" / "benchmarks" / "spotter-baseline.json",
    )
    args = parser.parse_args()

    result = run_benchmark(args.ticks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
