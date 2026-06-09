"""Detección de transiciones de banderas para FlagsMonitorTrigger."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FlagEventType(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    BLUE = "blue"
    SAFETY_CAR = "safety_car"
    FCY = "fcy"


@dataclass(frozen=True)
class FlagSnapshot:
    yellow: bool = False
    safety_car: bool = False
    fcy: bool = False
    blue: bool = False
    session_stopped: bool = False
    session_over: bool = False


@dataclass(frozen=True)
class FlagEvent:
    event_type: FlagEventType
    message: str
    priority: int = 2


def snapshot_from_telemetry(telemetry: dict) -> FlagSnapshot:
    """Construye snapshot de banderas desde telemetría normalizada."""
    return FlagSnapshot(
        yellow=bool(telemetry.get("yellow_flag_active", False)),
        safety_car=bool(telemetry.get("safety_car_active", False)),
        fcy=bool(telemetry.get("full_course_yellow_active", False)),
        blue=bool(telemetry.get("blue_flag_active", False)),
        session_stopped=bool(telemetry.get("session_stopped", False)),
        session_over=bool(telemetry.get("session_over", False)),
    )


def detect_flag_transitions(
    previous: FlagSnapshot | None,
    current: FlagSnapshot,
) -> list[FlagEvent]:
    """Detecta cambios de bandera entre dos snapshots consecutivos."""
    if previous is None:
        return []

    events: list[FlagEvent] = []

    if not previous.safety_car and current.safety_car:
        events.append(
            FlagEvent(
                FlagEventType.SAFETY_CAR,
                "¡SAFETY CAR ACTIVO! Reduce velocidad y prepárate.",
                priority=4,
            )
        )
    if not previous.fcy and current.fcy:
        events.append(
            FlagEvent(
                FlagEventType.FCY,
                "¡FCY ACTIVO! Full Course Yellow desplegado.",
                priority=4,
            )
        )
    if not previous.yellow and current.yellow and not current.safety_car and not current.fcy:
        events.append(
            FlagEvent(
                FlagEventType.YELLOW,
                "Bandera amarilla. Precaución en pista.",
                priority=3,
            )
        )
    if previous.yellow and not current.yellow and not current.safety_car and not current.fcy:
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
