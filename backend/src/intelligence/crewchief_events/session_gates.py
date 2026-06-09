from __future__ import annotations

from shared_telemetry.session_kind import is_race_session


def should_suppress_race_event(telemetry: dict, session: dict) -> bool:
    return not is_race_session(telemetry, session)


def is_manual_formation_lap(telemetry: dict, session: dict) -> bool:
    if bool(
        telemetry.get("manual_formation_lap")
        or session.get("manual_formation_lap")
        or telemetry.get("on_manual_formation_lap")
    ):
        return True
    phase = str(session.get("phase") or telemetry.get("session_type") or "").strip().lower()
    if phase != "race":
        return False
    if "lap_number" not in telemetry and "completed_laps" not in telemetry:
        return False
    lap = int(telemetry.get("lap_number") or telemetry.get("completed_laps") or 0)
    return lap <= 0


def is_racing_green(telemetry: dict, session: dict) -> bool:
    if should_suppress_race_event(telemetry, session):
        return False
    if bool(telemetry.get("full_course_yellow_active") or telemetry.get("safety_car_active")):
        return False
    if bool(telemetry.get("yellow_flag_active") or telemetry.get("red_flag_active")):
        return False
    if is_manual_formation_lap(telemetry, session):
        return False
    return True


def is_hard_part(telemetry: dict) -> bool:
    brake = float(telemetry.get("brake_pressure") or telemetry.get("brake") or 0.0)
    speed = float(telemetry.get("speed_ms") or telemetry.get("speed") or 0.0)
    steering = abs(float(telemetry.get("steering") or 0.0))
    return speed > 25.0 and (brake >= 0.15 or steering >= 0.35)
