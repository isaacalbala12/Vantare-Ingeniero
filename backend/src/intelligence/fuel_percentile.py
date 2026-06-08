"""Percentil de consumo de combustible vs historial de sesión (estilo CC play-it-safe)."""

from __future__ import annotations

from typing import Optional

from src.persistence.history_store import HistoryStore


def fuel_consumption_percentile(
    history_store: HistoryStore | None,
    current_consumption_l: float,
) -> Optional[float]:
    """Devuelve percentil 0–100 del consumo actual vs vueltas previas. None si datos insuficientes."""
    if history_store is None or current_consumption_l <= 0:
        return None
    history = history_store.get_history()
    consumptions = [float(r["consumption"]) for r in history if r.get("consumption", 0) > 0]
    if len(consumptions) < 3:
        return None
    below = sum(1 for c in consumptions if c <= current_consumption_l)
    return round(100.0 * below / len(consumptions), 1)


def format_fuel_percentile_message(percentile: float, laps_remaining: float) -> str:
    if percentile <= 15:
        return (
            f"Consumo en el percentil {percentile:.0f} — muy eficiente. "
            f"Te quedan unas {laps_remaining:.0f} vueltas."
        )
    if percentile >= 85:
        return (
            f"Consumo en el percentil {percentile:.0f} — alto. "
            f"Considera ahorrar, quedan {laps_remaining:.1f} vueltas."
        )
    return f"Consumo en percentil {percentile:.0f}, {laps_remaining:.1f} vueltas restantes."
