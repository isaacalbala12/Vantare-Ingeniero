"""Adapta TelemetryFrame (sidecar) al formato de tick que espera SpotterService."""

from __future__ import annotations

from typing import Any


def _sanitize_gap_seconds(value: float) -> float:
    if value <= 0 or value > 3600:
        return 0.0
    return value


def _compute_gaps_from_advice(advice: dict | None) -> tuple[float, float]:
    """Obtiene gap adelante/atrás desde el advice de estrategia (fallback)."""
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


def _compute_gaps_from_frame(frame: dict, advice: dict | None) -> tuple[float, float]:
    """Prioriza gaps nativos LMU (coche en pista, todas las clases)."""
    car_ahead = _sanitize_gap_seconds(float(frame.get("time_gap_car_ahead") or 0))
    car_behind = _sanitize_gap_seconds(float(frame.get("time_gap_car_behind") or 0))
    if car_ahead > 0 or car_behind > 0:
        return car_ahead or 99.0, car_behind or 99.0

    place_ahead = _sanitize_gap_seconds(float(frame.get("time_gap_place_ahead") or 0))
    place_behind = _sanitize_gap_seconds(float(frame.get("time_gap_place_behind") or 0))
    if place_ahead > 0 or place_behind > 0:
        return place_ahead or 99.0, place_behind or 99.0

    return _compute_gaps_from_advice(advice)


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

    gap_ahead, gap_behind = _compute_gaps_from_frame(frame, advice)
    if frame.get("gap_ahead") is not None:
        gap_ahead = float(frame["gap_ahead"])
    if frame.get("gap_behind") is not None:
        gap_behind = float(frame["gap_behind"])

    return {
        "in_pits": bool(frame.get("in_pits", False)),
        "pit_limiter_active": bool(frame.get("pit_limiter_active", False)),
        "gap_ahead": gap_ahead,
        "gap_behind": gap_behind,
        "lap_number": int(frame.get("lap_number", 1)),
        "lap_distance": float(frame.get("lap_distance", 0.0)),
        "path_lateral": float(frame.get("path_lateral", 0.0)),
        "damage_aero": float(frame.get("damage_aero", 0.0)),
        "suspension_damage": float(frame.get("suspension_damage", 0.0)),
        "dent_severity_avg": float(frame.get("dent_severity_avg", 0.0)),
        "dent_severity_max": int(frame.get("dent_severity_max", 0) or 0),
        "detached": bool(frame.get("detached", False)),
        "last_impact_et": float(frame.get("last_impact_et", 0.0)),
        "last_impact_magnitude": float(frame.get("last_impact_magnitude", 0.0)),
        "local_accel_x": float(frame.get("local_accel_x", 0.0)),
        "local_accel_y": float(frame.get("local_accel_y", 0.0)),
        "local_accel_z": float(frame.get("local_accel_z", 0.0)),
        "tyre_flat_fl": bool(frame.get("tyre_flat_fl", False)),
        "tyre_flat_fr": bool(frame.get("tyre_flat_fr", False)),
        "tyre_flat_rl": bool(frame.get("tyre_flat_rl", False)),
        "tyre_flat_rr": bool(frame.get("tyre_flat_rr", False)),
        "yellow_flag_state": int(frame.get("yellow_flag_state", 0) or 0),
        "raining_intensity": float(frame.get("raining_intensity", 0.0)),
        "current_sector": int(frame.get("current_sector", 0) or 0),
        "damage": frame.get("damage"),
        "safety_car_active": bool(frame.get("safety_car_active", False)),
        "full_course_yellow_active": bool(frame.get("full_course_yellow_active", False)),
        "session_laps_left": float(frame.get("session_laps_left", 99.0)),
        "is_last_lap": bool(frame.get("is_last_lap", False)),
        "estimated_laps_remaining": _estimate_fuel_laps(frame, advice),
        "fuel_laps_remaining": _estimate_fuel_laps(frame, advice),
        "fuel_in_tank": float(frame.get("fuel_in_tank") or 0.0),
        "fuel_needed_to_finish": float((advice or {}).get("fuel", {}).get("fuel_needed_to_finish") or 0.0),
        "pit_stops_needed": int((advice or {}).get("fuel", {}).get("pit_stops_needed") or -1),
        "session_type": frame.get("session_type", "race"),
        "competitors": frame.get("competitors") or [],
        "pos_x": float(frame.get("pos_x", 0.0)),
        "pos_y": float(frame.get("pos_y", 0.0)),
        "pos_z": float(frame.get("pos_z", 0.0)),
        "vel_x": float(frame.get("vel_x", 0.0)),
        "vel_y": float(frame.get("vel_y", 0.0)),
        "vel_z": float(frame.get("vel_z", 0.0)),
        "ori_fwd_x": float(frame.get("ori_fwd_x", 0.0)),
        "ori_fwd_z": float(frame.get("ori_fwd_z", 0.0)),
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
