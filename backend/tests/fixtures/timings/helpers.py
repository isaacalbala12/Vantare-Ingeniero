from __future__ import annotations

import json
from pathlib import Path

from src.intelligence.crewchief_events.modules.timings import TimingsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext

FIXTURES = Path(__file__).parent


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def replay_timings_fixture(name: str) -> list:
    data = load_fixture(name)
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    module._sectors_until_next_behind = 0
    session = data.get("session", {})
    frames = data["frames"]
    collected = []
    prev = None
    for i, frame in enumerate(frames):
        if prev is None:
            prev = frame
            continue
        ctx = CrewChiefFrameContext(
            previous=prev,
            current=frame,
            strategy={},
            session=session,
            now_monotonic=float(i),
        )
        collected.extend(module.evaluate(ctx))
        prev = frame
    return collected
