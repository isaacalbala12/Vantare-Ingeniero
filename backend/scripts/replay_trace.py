#!/usr/bin/env python3
"""Feed .trace JSONL @ 20Hz through CrewChiefGameStateLoop; stdout = timeline JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.intelligence.crewchief_events.game_state import CrewChiefGameStateLoop
from src.intelligence.crewchief_events.suite_factory import build_crewchief_suite
from src.intelligence.engine import IntelligenceEngine


def load_entries(path: Path) -> list[dict]:
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_path", type=Path)
    parser.add_argument("--hz", type=float, default=20.0)
    args = parser.parse_args()

    sent: list[dict] = []

    def _capture(message) -> None:
        if hasattr(message, "model_dump"):
            sent.append(message.model_dump(mode="json"))
        elif isinstance(message, dict):
            sent.append(message)
        else:
            sent.append({"message": str(message)})

    engine = IntelligenceEngine(broadcast_callback=_capture)
    engine.apply_runtime_config({"verbosityLevel": "normal", "engineerEnabled": True})
    engine.crewchief_suite = build_crewchief_suite(engine)
    loop = CrewChiefGameStateLoop(engine=engine)

    entries = load_entries(args.trace_path)
    dt = 1.0 / args.hz if args.hz > 0 else 0.05
    timeline: list[dict] = []
    for i, entry in enumerate(entries):
        now = float(entry.get("t", i * dt))
        frame = entry.get("frame") or {}
        before = len(sent)
        loop.on_frame(frame, now=now, strategy={})
        for msg in sent[before:]:
            payload = msg.get("payload") or {}
            timeline.append(
                {
                    "t": now,
                    "event_id": payload.get("event_id") or msg.get("category"),
                    "text": msg.get("message"),
                    "channel": msg.get("category"),
                }
            )
    json.dump(timeline, sys.stdout, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
