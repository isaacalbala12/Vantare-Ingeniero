"""VerbosityEngine — adjusts message filtering based on traffic density.

Levels: FULL(0), MED(5), LOW(10), SILENT(20).
Updates every 1s, caches result.
"""

import time
from typing import Dict, Any


class VerbosityLevel:
    FULL = 0     # All priorities >=1 pass (BACKGROUND included)
    MED = 5      # Only >= MEDIUM (10) pass
    LOW = 10     # Only >= HIGH (15) pass
    SILENT = 20  # Only >= CRITICAL (20) pass


class VerbosityEngine:
    def __init__(self):
        self._level: int = VerbosityLevel.FULL
        self._next_update: float = 0.0
        self._enabled: bool = True

    def evaluate(self, telemetry: Dict[str, Any]) -> int:
        """Returns verbosity level based on traffic density. Update every 1s."""
        if not self._enabled:
            return VerbosityLevel.FULL
        now = time.monotonic()
        if now < self._next_update:
            return self._level
        self._next_update = now + 1.0

        speed = float(telemetry.get("speed", 0.0))
        if speed < 5.0:
            self._level = VerbosityLevel.FULL
            return self._level

        gap_ahead = float(telemetry.get("gap_ahead", 99.0))
        gap_behind = float(telemetry.get("gap_behind", 99.0))
        in_close = (0 < gap_ahead < 1.5) and (0 < gap_behind < 1.5)
        very_close = (0 < gap_ahead < 1.0) or (0 < gap_behind < 1.0)
        in_traffic = (0 < gap_ahead < 3.0) and (0 < gap_behind < 3.0)
        car_close = (0 < gap_ahead < 2.0) or (0 < gap_behind < 2.0)

        if in_close or very_close:
            self._level = VerbosityLevel.LOW
        elif in_traffic or car_close:
            self._level = VerbosityLevel.MED
        else:
            self._level = VerbosityLevel.FULL
        return self._level
