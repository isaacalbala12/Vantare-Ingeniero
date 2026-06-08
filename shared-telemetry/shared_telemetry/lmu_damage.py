"""Extrae campos de daño/impacto desde telemetría LMU (shared memory)."""

from __future__ import annotations

import math
from typing import Any


def _safe_float(val: Any) -> float:
    try:
        f = float(val)
        return f if math.isfinite(f) else 0.0
    except (TypeError, ValueError):
        return 0.0


def damage_fields_from_player_telemetry(player_tele: Any | None) -> dict[str, float | bool | list[int]]:
    """Mapea mDentSeverity / mLastImpact* al dict usado por strategy + spotter."""
    empty: dict[str, float | bool | list[int]] = {
        "damage_aero": 0.0,
        "suspension_damage": 0.0,
        "dent_severity": [0] * 8,
        "dent_severity_avg": 0.0,
        "dent_severity_max": 0,
        "detached": False,
        "last_impact_et": 0.0,
        "last_impact_magnitude": 0.0,
    }
    if player_tele is None:
        return empty

    dents = [int(player_tele.mDentSeverity[i]) for i in range(8)]
    dent_max = max(dents) if dents else 0
    dent_avg = sum(dents) / 8.0
    detached = bool(getattr(player_tele, "mDetached", False))

    return {
        "damage_aero": min(100.0, dent_avg / 2.0 * 100.0),
        "suspension_damage": 100.0 if detached else 0.0,
        "dent_severity": dents,
        "dent_severity_avg": dent_avg,
        "dent_severity_max": dent_max,
        "detached": detached,
        "last_impact_et": _safe_float(getattr(player_tele, "mLastImpactET", 0.0)),
        "last_impact_magnitude": _safe_float(getattr(player_tele, "mLastImpactMagnitude", 0.0)),
    }
