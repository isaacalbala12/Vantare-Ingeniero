"""Session/Phase Normalization for the new event system.

Converts LMU session values (int 0-4, string "race"/"RACE") to canonical
SessionType and SessionPhase enums. This adapter is the ONLY entry point
for session data in the new system.
"""

from enum import Enum


class SessionType(str, Enum):
    PRACTICE = "Practice"
    QUALIFY = "Qualify"
    RACE = "Race"
    HOTLAP = "HotLap"
    FORMATION = "Formation"


class SessionPhase(str, Enum):
    GREEN = "Green"
    COUNTDOWN = "Countdown"
    FINISHED = "Finished"


# LMU shared memory maps: 0=Practice, 1=Qualify, 2=Race, 3=HotLap, 4=Formation
_LMU_INT_MAP = {
    0: "Practice",
    1: "Qualify",
    2: "Race",
    3: "HotLap",
    4: "Formation",
}

_LMU_STR_MAP = {
    "practice": "Practice",
    "practise": "Practice",
    "qualify": "Qualify",
    "qualifying": "Qualify",
    "qual": "Qualify",
    "race": "Race",
    "racing": "Race",
    "hotlap": "HotLap",
    "hot_lap": "HotLap",
    "formation": "Formation",
}


def normalize_session_type(raw) -> str:
    """Convert LMU session_type to canonical SessionType string."""
    if isinstance(raw, int):
        return _LMU_INT_MAP.get(raw, "Race")
    if isinstance(raw, str):
        return _LMU_STR_MAP.get(raw.strip().lower(), "Race")
    return "Race"


def normalize_session_phase(raw_phase: str) -> str:
    """Derive session phase. Finished/checkered/chequered -> Finished."""
    p = (raw_phase or "").strip().lower()
    if p in ("finished", "checkered", "chequered"):
        return "Finished"
    if p in ("countdown", "pre_race", "formation"):
        return "Countdown"
    return "Green"
