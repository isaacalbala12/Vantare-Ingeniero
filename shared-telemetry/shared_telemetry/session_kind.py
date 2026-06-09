"""Clasificación de sesión LMU → practice | qualifying | race."""

from __future__ import annotations

SESSION_KINDS = frozenset({"practice", "qualifying", "race"})

# Eventos de commentary batch que solo deben emitirse en carrera (defensa en profundidad).
RACE_ONLY_COMMENTARY_EVENT_IDS = frozenset({
    "position_change",
    "pit_stops",
    "push_now",
    "session_end",
    "gap_update",
    "strategy",
    "opponents",
    "frozen_order",
    "driver_swaps",
    "overtake",
    "being_overtaken",
    "penalty_new",
    "penalty_2_laps",
    "penalty_1_lap",
    "penalty_pit_now",
    "penalty_served",
    "penalty_disqualified",
    "penalty_not_served",
})

# LMUSession (lmu_enum.py): TestDay=0, Practice1-4=1-4, Qualifying1-4=5-8, Warmup=9, Race1-4=10-13
_LMU_PRACTICE = frozenset(range(0, 5))
_LMU_QUALIFYING = frozenset(range(5, 10))
_LMU_RACE = frozenset(range(10, 14))

_LABEL_TO_KIND: dict[str, str] = {
    "practice": "practice",
    "practica": "practice",
    "prac": "practice",
    "test": "practice",
    "testday": "practice",
    "pra": "practice",
    "pra1": "practice",
    "pra2": "practice",
    "pra3": "practice",
    "pra4": "practice",
    "qualifying": "qualifying",
    "quali": "qualifying",
    "qualy": "qualifying",
    "qual": "qualifying",
    "q1": "qualifying",
    "q2": "qualifying",
    "q3": "qualifying",
    "q4": "qualifying",
    "wup": "qualifying",
    "warmup": "qualifying",
    "race": "race",
    "r": "race",
    "green": "race",
}


def session_kind_from_lmu_int(session_type_int: int) -> str:
    """Mapea mSession entero LMU a practice | qualifying | race."""
    value = int(session_type_int)
    if value in _LMU_PRACTICE:
        return "practice"
    if value in _LMU_QUALIFYING:
        return "qualifying"
    if value in _LMU_RACE:
        return "race"
    if value < 5:
        return "practice"
    if value < 10:
        return "qualifying"
    return "race"


def normalize_session_label(label: str) -> str:
    """Normaliza etiquetas de sesión (ticker, REST, strings) a practice | qualifying | race."""
    key = (label or "race").strip().lower()
    if key in _LABEL_TO_KIND:
        return _LABEL_TO_KIND[key]
    if key.startswith("pra"):
        return "practice"
    if key.startswith("qual") or key.startswith("qualy"):
        return "qualifying"
    if len(key) == 2 and key[0] == "q" and key[1].isdigit():
        return "qualifying"
    if key.startswith("race") or key == "green":
        return "race"
    return "race"


def sync_session_fields(
    telemetry: dict | None = None,
    session: dict | None = None,
) -> tuple[dict, dict]:
    """Alinea session_type_int entre telemetría y sesión; el int LMU manda sobre strings stale."""
    telemetry = dict(telemetry or {})
    session = dict(session or {})
    raw_int = telemetry.get("session_type_int")
    if raw_int is None:
        raw_int = session.get("session_type_int")
    if raw_int is not None:
        sti = int(raw_int)
        kind = session_kind_from_lmu_int(sti)
        telemetry["session_type_int"] = sti
        session["session_type_int"] = sti
        telemetry["session_type"] = kind
        session["phase"] = kind
    else:
        kind = resolve_session_kind(telemetry, session)
        telemetry["session_type"] = kind
        session["phase"] = kind
    return telemetry, session


def resolve_session_kind(
    telemetry: dict | None = None,
    session: dict | None = None,
) -> str:
    """Resuelve el tipo de sesión desde telemetría y/o dict de sesión del engine."""
    telemetry = telemetry or {}
    session = session or {}

    # mSession (int) es la fuente autoritativa LMU; el string puede venir stale del sidecar.
    for source in (telemetry, session):
        raw_int = source.get("session_type_int")
        if raw_int is not None:
            return session_kind_from_lmu_int(int(raw_int))

    raw = (
        session.get("phase")
        or session.get("session_kind")
        or telemetry.get("session_type")
        or telemetry.get("session_phase")
        or "race"
    )
    return normalize_session_label(str(raw))


def is_race_commentary_event_id(event_id: str) -> bool:
    return event_id in RACE_ONLY_COMMENTARY_EVENT_IDS


def should_emit_commentary_event(
    event_id: str,
    telemetry: dict | None = None,
    session: dict | None = None,
) -> bool:
    if is_race_commentary_event_id(event_id) and not is_race_session(telemetry, session):
        return False
    return True


def is_race_session(
    telemetry: dict | None = None,
    session: dict | None = None,
) -> bool:
    return resolve_session_kind(telemetry, session) == "race"


def is_practice_session(
    telemetry: dict | None = None,
    session: dict | None = None,
) -> bool:
    return resolve_session_kind(telemetry, session) == "practice"
