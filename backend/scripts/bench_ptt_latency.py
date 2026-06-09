"""Benchmark latencia PTT: TTFT + total (stream) y /ask E2E."""
import asyncio
import statistics
import time

import httpx

from src.intelligence.context_builder import build_pilot_question_messages
from src.intelligence.llm_client import VLLMClient

QUESTIONS = [
    "como va mi ritmo en pista?",
    "cuantas vueltas de combustible me quedan?",
    "que estrategia recomiendas para boxes?",
]


async def bench_stream(client: VLLMClient, messages: list) -> dict:
    t0 = time.perf_counter()
    ttft = None
    parts: list[str] = []
    async for tok in client.ask_streaming_messages(messages):
        if tok and ttft is None:
            ttft = time.perf_counter() - t0
        parts.append(tok)
    total = time.perf_counter() - t0
    text = "".join(parts)
    return {
        "ttft_ms": round((ttft or total) * 1000),
        "total_ms": round(total * 1000),
        "chars": len(text),
        "text": text[:160],
    }


async def bench_ask(question: str) -> dict:
    t0 = time.perf_counter()
    async with httpx.AsyncClient() as c:
        r = await c.post(
            "http://127.0.0.1:8008/ask",
            json={"question": question},
            timeout=90.0,
        )
    total = time.perf_counter() - t0
    return {
        "total_ms": round(total * 1000),
        "status": r.status_code,
        "chars": len(r.text),
        "text": r.text[:160],
    }


async def main() -> None:
    client = VLLMClient()
    print("=== config ===")
    print("model:", client._model)
    print("base:", client._base_url)
    print("stepfun:", client._is_stepfun())

    snapshot = {
        "lap_number": 5,
        "place": 3,
        "fuel_in_tank": 42.0,
        "speed": 180,
        "gap_ahead": 2.1,
        "gap_behind": 1.5,
        "fuel_laps_remaining": 10.0,
    }
    telemetry = {
        "lap_number": 5,
        "position": 3,
        "fuel_laps_remaining": 10.0,
        "session_type": "RACE",
        "competitors": [],
    }

    messages = build_pilot_question_messages(
        snapshot=snapshot,
        pilot_question=QUESTIONS[0],
        telemetry_frame=telemetry,
    )
    sys_c = len(messages[0]["content"])
    usr_c = len(messages[1]["content"])
    print("\n=== prompt PTT (nuevo formato) ===")
    print(f"system: {sys_c} chars | user: {usr_c} chars | total: {sys_c + usr_c}")
    print("user preview:", messages[1]["content"][:220].replace("\n", " | "))

    print("\n=== warmup LLM stream ===")
    w = await bench_stream(client, messages)
    print(w)

    print("\n=== LLM stream x3 ===")
    runs = []
    for i in range(3):
        r = await bench_stream(client, messages)
        runs.append(r)
        print(f"  run {i + 1}: TTFT={r['ttft_ms']}ms total={r['total_ms']}ms chars={r['chars']}")
    ttfts = [r["ttft_ms"] for r in runs]
    totals = [r["total_ms"] for r in runs]
    print(f"  avg TTFT={statistics.mean(ttfts):.0f}ms median={statistics.median(ttfts):.0f}ms")
    print(f"  avg total={statistics.mean(totals):.0f}ms median={statistics.median(totals):.0f}ms")
    print(f"  last response: {runs[-1]['text']!r}")

    print("\n=== HTTP /ask E2E ===")
    for q in QUESTIONS:
        r = await bench_ask(q)
        print(f"  Q: {q}")
        print(f"     total={r['total_ms']}ms status={r['status']} chars={r['chars']}")
        print(f"     -> {r['text']!r}")


if __name__ == "__main__":
    asyncio.run(main())
