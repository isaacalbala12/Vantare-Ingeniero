"""Detección de transiciones de banderas para FlagsMonitorTrigger."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FlagEventType(StrEnum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    BLUE = "blue"
    SAFETY_CAR = "safety_car"
    FCY = "fcy"
    FCY_PITS_CLOSED = "fcy_pits_closed"
    FCY_PITS_OPEN = "fcy_pits_open"
    FCY_LAST_LAP = "fcy_last_lap"
    FCY_RESUME = "fcy_resume"


FCY_PHASE_MESSAGES: dict[int, tuple[str, int]] = {
    1: ("Bandera amarilla en todo el circuito.", 4),
    2: ("Safety Car desplegado. Pits cerrados.", 4),
    4: ("Pits abiertos.", 3),
    5: ("Última vuelta de Safety Car.", 3),
    6: ("Prepárate para relanzamiento.", 3),
}


@dataclass(frozen=True)
class FlagSnapshot:
    yellow: bool = False
    local_yellow: bool = False
    safety_car: bool = False
    fcy: bool = False
    blue: bool = False
    session_stopped: bool = False
    session_over: bool = False
    fcy_phase: int = 0
    game_phase: int = 5
    sector_flags: tuple[int, int, int] = (0, 0, 0)


@dataclass(frozen=True)
class FlagEvent:
    event_type: FlagEventType
    message: str
    priority: int = 2


def _sector_flags_from_telemetry(telemetry: dict) -> tuple[int, int, int]:
    raw = telemetry.get("sector_flags") or [0, 0, 0]
    values = [int(x or 0) for x in list(raw)[:3]]
    while len(values) < 3:
        values.append(0)
    return values[0], values[1], values[2]


def _local_yellow_from_telemetry(telemetry: dict) -> bool:
    if telemetry.get("local_yellow_active") is not None:
        return bool(telemetry.get("local_yellow_active"))
    sector_flags = _sector_flags_from_telemetry(telemetry)
    if any(flag != 0 for flag in sector_flags):
        return True
    if bool(telemetry.get("full_course_yellow_active") or telemetry.get("safety_car_active")):
        return False
    return bool(telemetry.get("yellow_flag_active", False))


def snapshot_from_telemetry(telemetry: dict) -> FlagSnapshot:
    """Construye snapshot de banderas desde telemetría normalizada."""
    game_phase = int(telemetry.get("game_phase", 0) or 0)
    if not game_phase:
        if telemetry.get("full_course_yellow_active") or telemetry.get("safety_car_active"):
            game_phase = 6
        elif telemetry.get("session_over"):
            game_phase = 8
        else:
            game_phase = 5
    return FlagSnapshot(
        yellow=bool(telemetry.get("yellow_flag_active", False)),
        local_yellow=_local_yellow_from_telemetry(telemetry),
        safety_car=bool(telemetry.get("safety_car_active", False)),
        fcy=bool(telemetry.get("full_course_yellow_active", False)),
        blue=bool(telemetry.get("blue_flag_active", False)),
        session_stopped=bool(telemetry.get("session_stopped", False)),
        session_over=bool(telemetry.get("session_over", False)),
        fcy_phase=int(telemetry.get("yellow_flag_state", 0) or 0),
        game_phase=game_phase,
        sector_flags=_sector_flags_from_telemetry(telemetry),
    )


def detect_fcy_phase_transitions(
    previous: Optional[FlagSnapshot],
    current: FlagSnapshot,
) -> list[FlagEvent]:
    if previous is None:
        return []
    events: list[FlagEvent] = []
    prev_phase = previous.fcy_phase
    curr_phase = current.fcy_phase
    if prev_phase == curr_phase:
        return events
    if curr_phase in FCY_PHASE_MESSAGES and curr_phase != prev_phase:
        msg, prio = FCY_PHASE_MESSAGES[curr_phase]
        event_map = {
            1: FlagEventType.FCY,
            2: FlagEventType.FCY_PITS_CLOSED,
            4: FlagEventType.FCY_PITS_OPEN,
            5: FlagEventType.FCY_LAST_LAP,
            6: FlagEventType.FCY_RESUME,
        }
        events.append(
            FlagEvent(
                event_map[curr_phase],
                msg,
                priority=prio,
            )
        )
    return events


def detect_flag_transitions(
    previous: FlagSnapshot | None,
    current: FlagSnapshot,
) -> list[FlagEvent]:
    """Detecta cambios de bandera entre dos snapshots consecutivos."""
    if previous is None:
        previous = FlagSnapshot()

    events: list[FlagEvent] = []
    events.extend(detect_fcy_phase_transitions(previous, current))

    # Fallback gamePhase si mYellowFlagState no cambia
    if not events and previous.game_phase != current.game_phase:
        if previous.game_phase != 6 and current.game_phase == 6 and not previous.safety_car:
            events.append(
                FlagEvent(
                    FlagEventType.FCY,
                    "Bandera amarilla en todo el circuito.",
                    priority=4,
                )
            )
        if previous.game_phase == 6 and current.game_phase == 5:
            events.append(
                FlagEvent(
                    FlagEventType.GREEN,
                    "Bandera verde. A tope.",
                    priority=3,
                )
            )

    if not previous.safety_car and current.safety_car and not any(
        e.event_type == FlagEventType.FCY_PITS_CLOSED for e in events
    ):
        events.append(
            FlagEvent(
                FlagEventType.SAFETY_CAR,
                "¡SAFETY CAR ACTIVO! Reduce velocidad y prepárate.",
                priority=4,
            )
        )
    if not previous.fcy and current.fcy and not events:
        events.append(
            FlagEvent(
                FlagEventType.FCY,
                "¡FCY ACTIVO! Full Course Yellow desplegado.",
                priority=4,
            )
        )
    if not previous.local_yellow and current.local_yellow:
        events.append(
            FlagEvent(
                FlagEventType.YELLOW,
                "Bandera amarilla. Precaución en pista.",
                priority=3,
            )
        )
    elif (
        previous.sector_flags != current.sector_flags
        and any(flag != 0 for flag in current.sector_flags)
        and not any(flag != 0 for flag in previous.sector_flags)
        and not current.fcy
    ):
        events.append(
            FlagEvent(
                FlagEventType.YELLOW,
                "Bandera amarilla. Precaución en pista.",
                priority=3,
            )
        )
    if previous.local_yellow and not current.local_yellow and not current.fcy:
        if not any(e.event_type == FlagEventType.GREEN for e in events):
            events.append(
                FlagEvent(
                    FlagEventType.GREEN,
                    "Bandera verde. A tope.",
                    priority=2,
                )
            )
    if not previous.blue and current.blue:
        events.append(
            FlagEvent(
                FlagEventType.BLUE,
                "Bandera azul — coche más rápido detrás.",
                priority=3,
            )
        )
    if previous.blue and not current.blue:
        events.append(
            FlagEvent(
                FlagEventType.GREEN,
                "Bandera azul retirada.",
                priority=1,
            )
        )
    if not previous.session_stopped and current.session_stopped:
        events.append(
            FlagEvent(
                FlagEventType.RED,
                "Bandera roja — sesión detenida.",
                priority=4,
            )
        )
    if not previous.session_over and current.session_over:
        events.append(
            FlagEvent(
                FlagEventType.RED,
                "Sesión terminada.",
                priority=3,
            )
        )

    return events


def pick_highest_priority_event(events: list[FlagEvent]) -> FlagEvent | None:
    if not events:
        return None
    return max(events, key=lambda e: e.priority)
