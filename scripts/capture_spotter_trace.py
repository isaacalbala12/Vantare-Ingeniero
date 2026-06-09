#!/usr/bin/env python3
"""Captura ticks sidecar/strategy para fixtures spotter (30s o hasta N frames).

Uso (con backend + sidecar activos):
  python scripts/capture_spotter_trace.py --output backend/tests/fixtures/spotter/captured_session.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

try:
    import websockets
except ImportError:
    print("Instala websockets: pip install websockets", file=sys.stderr)
    sys.exit(1)


async def capture(url: str, duration_s: float, max_frames: int, nearest_m: float) -> list[dict]:
    frames: list[dict] = []
    deadline = time.monotonic() + duration_s

    async with websockets.connect(url) as ws:
        while time.monotonic() < deadline and len(frames) < max_frames:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=2.0)
            except asyncio.TimeoutError:
                continue
            if isinstance(raw, bytes):
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if msg.get("event") != "strategy":
                continue
            payload = msg.get("data") or msg.get("payload") or {}
            competitors = payload.get("competitors") or []
            if not competitors:
                continue
            px = float(payload.get("pos_x", 0))
            pz = float(payload.get("pos_z", 0))
            min_dist = min(
                (
                    ((float(c.get("pos_x", 0)) - px) ** 2 + (float(c.get("pos_z", 0)) - pz) ** 2) ** 0.5
                    for c in competitors
                ),
                default=999.0,
            )
            if min_dist <= nearest_m:
                frames.append(payload)

    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description="Captura traza spotter desde WS strategy")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8008)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--max-frames", type=int, default=200)
    parser.add_argument("--nearest-m", type=float, default=20.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    url = f"ws://{args.host}:{args.port}/ws"
    frames = asyncio.run(capture(url, args.duration, args.max_frames, args.nearest_m))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump({"ticks": frames, "captured_at": time.time(), "count": len(frames)}, f, indent=2)

    print(f"Capturados {len(frames)} frames → {args.output}")


if __name__ == "__main__":
    main()
