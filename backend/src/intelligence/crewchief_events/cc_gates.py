"""Gates estilo Crew Chief UserSettings (Tasks 17–21)."""

from __future__ import annotations

from shared_telemetry.session_kind import is_race_session

from src.intelligence.flags_monitor import FlagEventType

# Defaults alineados con CC (enable_* = true salvo gaps)
DEFAULT_ENABLE_BLUE_FLAG = True
DEFAULT_ENABLE_LOCAL_YELLOW = True
DEFAULT_ENABLE_FCY = True

FLAG_COOLDOWN_S: dict[FlagEventType, float] = {
    FlagEventType.YELLOW: 25.0,
    FlagEventType.BLUE: 15.0,
    FlagEventType.RED: 15.0,
}


def session_enable_flag(session: dict, key: str, default: bool = True) -> bool:
    raw = session.get(key)
    if raw is None:
        return default
    return bool(raw)


def should_emit_flag_event(
    event_type: FlagEventType,
    *,
    telemetry: dict,
    session: dict,
    in_pits: bool,
) -> bool:
    if in_pits and event_type in (FlagEventType.BLUE, FlagEventType.YELLOW):
        return False
    if event_type == FlagEventType.BLUE:
        return session_enable_flag(session, "enable_blue_flag_messages", DEFAULT_ENABLE_BLUE_FLAG)
    if event_type == FlagEventType.YELLOW:
        return session_enable_flag(session, "enable_local_yellow_messages", DEFAULT_ENABLE_LOCAL_YELLOW)
    if event_type in (
        FlagEventType.FCY,
        FlagEventType.FCY_PITS_CLOSED,
        FlagEventType.FCY_PITS_OPEN,
        FlagEventType.FCY_LAST_LAP,
        FlagEventType.FCY_RESUME,
        FlagEventType.SAFETY_CAR,
    ):
        return session_enable_flag(session, "enable_fcy_messages", DEFAULT_ENABLE_FCY)
    return True


def flag_on_cooldown(
    event_type: FlagEventType,
    now: float,
    last_played: dict[FlagEventType, float],
) -> bool:
    cooldown = FLAG_COOLDOWN_S.get(event_type, 0.0)
    if cooldown <= 0:
        return False
    last = last_played.get(event_type, 0.0)
    return last > 0 and (now - last) < cooldown


def is_race_session_ctx(telemetry: dict, session: dict) -> bool:
    return is_race_session(telemetry, session)


DEFAULT_ENABLE_GAP_MESSAGES = True
DEFAULT_GAP_AHEAD_FREQUENCY = 5
DEFAULT_GAP_BEHIND_FREQUENCY = 5
DEFAULT_GAP_MESSAGE_RANDOMNESS = 5
NEAR_RACE_END_LAPS = 2


def should_emit_gap_message(telemetry: dict, session: dict) -> bool:
    if not session_enable_flag(session, "enable_gap_messages", DEFAULT_ENABLE_GAP_MESSAGES):
        return False
    if bool(telemetry.get("in_pits")):
        return False
    if not is_race_session_ctx(telemetry, session):
        return False
    if is_near_race_end(telemetry):
        return False
    return True


def is_near_race_end(telemetry: dict) -> bool:
    laps_left = telemetry.get("session_laps_left")
    if laps_left is None:
        return False
    return 0 < float(laps_left) <= NEAR_RACE_END_LAPS


def gap_frequency_sectors(session: dict, which: str) -> tuple[int, int]:
    key = (
        "frequency_of_gap_ahead_reports"
        if which == "ahead"
        else "frequency_of_gap_behind_reports"
    )
    default = DEFAULT_GAP_AHEAD_FREQUENCY if which == "ahead" else DEFAULT_GAP_BEHIND_FREQUENCY
    freq = int(session.get(key, default))
    freq = max(1, min(10, freq))
    randomness = int(session.get("gap_message_randomness", DEFAULT_GAP_MESSAGE_RANDOMNESS))
    randomness = max(0, min(10, randomness))
    base = 1 + (10 - freq)
    return base, base + randomness
