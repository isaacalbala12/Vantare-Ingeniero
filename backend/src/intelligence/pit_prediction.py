"""Estimación read-only de posición tras parada (sin API write LMU)."""

from __future__ import annotations

from typing import Optional


def estimate_position_after_pit_stop(
    current_position: int,
    competitors_ahead_in_pits: int,
    competitors_behind_passing: int,
) -> int:
    """Estimación simple: posición actual + coches que pasarían durante parada."""
    if current_position <= 0:
        return current_position
    gain_from_pits = max(0, competitors_ahead_in_pits)
    loss_from_passing = max(0, competitors_behind_passing)
    return max(1, current_position + loss_from_passing - gain_from_pits)


def format_pit_exit_prediction(
    current_position: int,
    estimated_position: int,
    pit_window_open: bool,
) -> Optional[str]:
    if current_position <= 0:
        return None
    if estimated_position == current_position:
        base = f"Tras parada estimada: P{estimated_position}."
    else:
        base = f"Tras parada estimada: P{estimated_position} (ahora P{current_position})."
    if pit_window_open:
        return f"Ventana de boxes abierta. {base}"
    return base


def count_pit_context(competitors: list[dict], player_index: int = 0) -> tuple[int, int]:
    """Cuenta rivales en boxes delante y rivales activos detrás que podrían pasar."""
    ahead_in_pits = 0
    behind_active = 0
    player_pos = None
    for c in competitors:
        idx = int(c.get("driver_index", -1))
        pos = int(c.get("standing_position", 0) or 0)
        if idx == player_index:
            player_pos = pos
    if player_pos is None:
        return 0, 0
    for c in competitors:
        idx = int(c.get("driver_index", -1))
        if idx < 0:
            continue
        pos = int(c.get("standing_position", 0) or 0)
        in_pits = bool(c.get("in_pits", False))
        if in_pits and 0 < pos < player_pos:
            ahead_in_pits += 1
        if not in_pits and pos > player_pos:
            behind_active += 1
    return ahead_in_pits, behind_active
