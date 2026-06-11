"""Convierte TelemetryFrame a texto compacto para embedding ChromaDB.

El formato usa prefijos fijos para que el embedding capture relaciones semánticas.
Dos eventos con telemetría similar tendrán vectores cercanos en ChromaDB.

Formato:
L{vuelta}|P{pos}|F{combustible}|T{FL/FR/RL/RR}|SC{S/N}|YF{S/N}|G{+ahead/-behind}|S{velocidad}|CLD{0-10}|RAIN{0.0-1.0}|WET{0.0-1.0}|A{°C}|TEMP{°C}|DRS{S/N}|PIT{0-4}|BAT{%}|D{%}|E{event_type}

Regla especial: si lap ≤ 3, se omite el campo T (neumáticos no representativos).
"""

from typing import Any


def format_event_text(frame: dict, event_type: str, lap: int) -> str:
    """Convierte un TelemetryFrame a texto compacto para embedding.

    Args:
        frame: TelemetryFrame como dict (vía Pydantic model_dump(mode="json")).
        event_type: Tipo de evento (ej. "lap_completed", "safety_car").
        lap: Número de vuelta actual.

    Returns:
        String con formato de prefijos fijos (~120 chars).
    """
    parts: list[str] = []

    # L: vuelta
    parts.append(f"L{lap}")

    # P: posición
    pos = frame.get("standing_position") or frame.get("place") or 0
    parts.append(f"P{pos}")

    # F: combustible en litros
    fuel = _safe_float(frame.get("fuel_in_tank"))
    parts.append(f"F{fuel:.1f}")

    # T: neumáticos (omitir si lap ≤ 3)
    if lap > 3:
        fl = _safe_float(frame.get("tyre_wear_fl", 0.0))
        fr = _safe_float(frame.get("tyre_wear_fr", 0.0))
        rl = _safe_float(frame.get("tyre_wear_rl", 0.0))
        rr = _safe_float(frame.get("tyre_wear_rr", 0.0))
        parts.append(f"T{fl:.0f}/{fr:.0f}/{rl:.0f}/{rr:.0f}")

    # SC: Safety Car
    sc = frame.get("safety_car_active", False)
    parts.append("SCS" if sc else "SCN")

    # YF: Yellow Flag
    yf = frame.get("yellow_flag_active", False) or frame.get("full_course_yellow_active", False)
    parts.append("YFS" if yf else "YFN")

    # G: gap
    gap_ahead = _safe_float(frame.get("time_gap_place_ahead", 0.0))
    gap_behind = _safe_float(frame.get("time_gap_place_behind", 0.0))
    if gap_ahead > 0:
        parts.append(f"G+{gap_ahead:.1f}")
    elif gap_behind > 0:
        parts.append(f"G-{gap_behind:.1f}")
    else:
        parts.append("G+0.0")

    # S: velocidad m/s
    speed = _safe_float(frame.get("speed", 0.0))
    parts.append(f"S{int(speed)}")

    # CLD: cobertura nubes
    cld = _safe_int(frame.get("cloud_coverage", 0))
    parts.append(f"CLD{cld}")

    # RAIN: lluvia
    rain = _safe_float(frame.get("raining", 0.0))
    parts.append(f"RAIN{rain:.1f}")

    # WET: mojado
    wet = _safe_float(frame.get("avg_path_wetness", 0.0))
    parts.append(f"WET{wet:.1f}")

    # A: temperatura ambiente
    ambient = _safe_float(frame.get("ambient_temp", 20.0))
    parts.append(f"A{int(ambient)}")

    # TEMP: temperatura pista
    track_temp = _safe_float(frame.get("track_temp", 20.0))
    parts.append(f"TEMP{int(track_temp)}")

    # DRS
    drs = frame.get("drs_state", False) or frame.get("rear_flap_activated", False)
    parts.append("DRSS" if drs else "DRSN")

    # PIT: estado boxes
    pit = _safe_int(frame.get("pit_state", 0))
    parts.append(f"PIT{pit}")

    # BAT: batería
    bat = _safe_float(frame.get("battery_charge", 100.0))
    parts.append(f"BAT{int(bat)}")

    # D: daños
    dent = _safe_float(frame.get("dent_severity_avg", 0.0))
    parts.append(f"D{int(dent)}")

    # E: evento
    parts.append(f"E{event_type}")

    return "|".join(parts)


def _safe_float(val: Any) -> float:
    """Convierte a float de forma segura, previniendo None y valores inválidos."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(val: Any) -> int:
    """Convierte a int de forma segura."""
    if val is None:
        return 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0
