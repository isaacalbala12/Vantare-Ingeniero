"""Helpers para cargar fixtures del spotter en tests y scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).resolve().parent


def load_frame(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_tick_sequence(name: str = "tick_sequence_overtake") -> list[dict[str, Any]]:
    data = load_frame(name)
    if isinstance(data, list):
        return data
    return data.get("ticks", [])


def assert_alerts_over_sequence(
    alerts: list[Any],
    *,
    min_proximity: int = 1,
    max_proximity: int | None = None,
    category: str = "proximity",
) -> None:
    prox = [a for a in alerts if getattr(a, "category", None) == category]
    assert len(prox) >= min_proximity, f"expected >= {min_proximity} {category}, got {len(prox)}"
    if max_proximity is not None:
        assert len(prox) <= max_proximity, f"expected <= {max_proximity} {category}, got {len(prox)}"
