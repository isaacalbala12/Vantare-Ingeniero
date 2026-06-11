from __future__ import annotations

import copy
import threading
from typing import Any


class TelemetryHub:
    """Last race snapshot for UI WebSocket broadcast (10 Hz)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] | None = None
        self._advice: dict[str, Any] | None = None
        self.tick_count: int = 0
        self.last_tick_monotonic: float = 0.0

    def update(self, *, snapshot: dict[str, Any], advice: dict[str, Any] | None) -> None:
        with self._lock:
            self._snapshot = copy.deepcopy(snapshot)
            self._advice = copy.deepcopy(advice) if advice else None
            self.tick_count += 1

    def get_latest(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        with self._lock:
            snap = copy.deepcopy(self._snapshot) if self._snapshot else None
            adv = copy.deepcopy(self._advice) if self._advice else None
            return snap, adv

    def record_tick_time(self, now: float) -> None:
        with self._lock:
            self.last_tick_monotonic = now
