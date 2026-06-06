"""Adapta TelemetryFrame (sidecar) al formato de tick que espera SpotterService."""

from __future__ import annotations

from typing import Any


def _compute_gaps_from_advice(advice: dict | None) -> tuple[float, float]:
    """Obtiene gap adelante/atrás desde el advice de estrategia."""
    gap_ahead = 99.0
    gap_behind = 99.0
    if not advice:
        return gap_ahead, gap_behind

    for comp in advice.get("competitors") or []:
        if not isinstance(comp, dict):
            continue
        gap = float(comp.get("gap_to_player", 99.0))
        if gap < 0:
            gap_ahead = min(gap_ahead, abs(gap))
        elif gap > 0:
            gap_behind = min(gap_behind, gap)
    return gap_ahead, gap_behind


def _estimate_fuel_laps(frame: dict, advice: dict | None) -> float:
    if advice:
        fuel_info = advice.get("fuel") or {}
        laps = fuel_info.get("estimated_laps_remaining")
        if laps is not None:
            return float(laps)

    used = float(frame.get("fuel_used_lap_raw") or 0.0)
    in_tank = float(frame.get("fuel_in_tank") or 0.0)
    if used > 0.01:
        return in_tank / used
    return float(frame.get("estimated_laps_remaining", 99.0))


def frame_to_spotter_tick(frame: dict, advice: dict | None = None) -> dict:
    """Convierte un TelemetryFrame (dict) al tick plano del spotter."""
    if frame.get("gap_ahead") is not None and "session_type" not in frame:
        return frame

    gap_ahead, gap_behind = _compute_gaps_from_advice(advice)
    if frame.get("gap_ahead") is not None:
        gap_ahead = float(frame["gap_ahead"])
    if frame.get("gap_behind") is not None:
        gap_behind = float(frame["gap_behind"])
    if frame.get("time_gap_place_ahead") is not None:
        gap_ahead = float(frame["time_gap_place_ahead"])
    if frame.get("time_gap_place_behind") is not None:
        gap_behind = float(frame["time_gap_place_behind"])

    return {
        "in_pits": bool(frame.get("in_pits", False)),
        "pit_limiter_active": bool(frame.get("pit_limiter_active", False)),
        "gap_ahead": gap_ahead,
        "gap_behind": gap_behind,
        "damage_aero": float(frame.get("damage_aero", 0.0)),
        "suspension_damage": float(frame.get("suspension_damage", 0.0)),
        "damage": frame.get("damage"),
        "safety_car_active": bool(frame.get("safety_car_active", False)),
        "full_course_yellow_active": bool(frame.get("full_course_yellow_active", False)),
        "session_laps_left": float(frame.get("session_laps_left", 99.0)),
        "is_last_lap": bool(frame.get("is_last_lap", False)),
        "estimated_laps_remaining": _estimate_fuel_laps(frame, advice),
        "fuel_laps_remaining": _estimate_fuel_laps(frame, advice),
        "session_type": frame.get("session_type", "race"),
        "competitors": frame.get("competitors") or [],
        "pos_x": float(frame.get("pos_x", 0.0)),
        "pos_y": float(frame.get("pos_y", 0.0)),
        "pos_z": float(frame.get("pos_z", 0.0)),
        "vel_x": float(frame.get("vel_x", 0.0)),
        "vel_y": float(frame.get("vel_y", 0.0)),
        "vel_z": float(frame.get("vel_z", 0.0)),
        "player_class": frame.get("player_class", ""),
        "vehicle_name": frame.get("vehicle_name", ""),
    }


def resolve_spotter_input(state: Any, advice: dict | None = None) -> dict:
    """Normaliza RaceState, Pydantic o dict al tick del spotter."""
    if isinstance(state, dict):
        return frame_to_spotter_tick(state, advice)
    if hasattr(state, "model_dump"):
        return frame_to_spotter_tick(state.model_dump(mode="json"), advice)
    if hasattr(state, "dict"):
        return frame_to_spotter_tick(state.dict(), advice)
    try:
        return frame_to_spotter_tick(vars(state), advice)
    except Exception:
        return {}
