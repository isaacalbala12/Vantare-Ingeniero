"""Lectura robusta del pit limiter desde telemetría LMU."""

from __future__ import annotations

from typing import Any


def pit_limiter_engaged(player_tele: Any | None) -> bool:
    """True si el limiter está activo o el toggle del piloto sigue ON."""
    if player_tele is None:
        return False
    if bool(getattr(player_tele, "mSpeedLimiterActive", False)):
        return True
    return int(getattr(player_tele, "mSpeedLimiter", 0) or 0) != 0
