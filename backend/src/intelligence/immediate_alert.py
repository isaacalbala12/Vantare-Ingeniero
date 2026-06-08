"""Alertas proactivas que deben emitirse sin pasar por commentary batch (LMU-33)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union

CommentaryEvent = tuple[str, str, str]  # event_id, summary, priority


@dataclass
class ImmediateAlert:
    event_id: str
    message: str
    priority: str  # CRITICAL | HIGH | MEDIUM | LOW
    category: str
    payload: dict = field(default_factory=dict)


ProactiveOutput = Union[ImmediateAlert, CommentaryEvent]

IMMEDIATE_EVENTS: frozenset[str] = frozenset({
    "race_start",
    "race_start_quality",
    "flags_yellow",
    "flags_safety_car",
    "flags_fcy",
    "flags_green",
    "flags_fcy_pits_closed",
    "flags_fcy_pits_open",
    "flags_fcy_last_lap",
    "flags_fcy_resume",
    "damage",
    "penalties",
    "penalty_new",
    "penalty_2_laps",
    "penalty_1_lap",
    "penalty_pit_now",
    "penalty_served",
    "penalty_disqualified",
    "penalty_not_served",
    "overtake",
    "being_overtaken",
    "rain_drizzle",
    "rain_light",
    "rain_mid",
    "rain_heavy",
    "rain_storm",
    "rain_stopped",
})

IMMEDIATE_PREFIXES: tuple[str, ...] = ("flags_fcy_", "flags_green", "flags_safety_car", "flags_yellow", "rain_", "penalty_")


def is_immediate_event(event_id: str) -> bool:
    if event_id in IMMEDIATE_EVENTS:
        return True
    return any(event_id.startswith(prefix) for prefix in IMMEDIATE_PREFIXES)


def proactive_event_id(evt: ProactiveOutput) -> str:
    if isinstance(evt, ImmediateAlert):
        return evt.event_id
    return evt[0]


def proactive_message(evt: ProactiveOutput) -> str:
    if isinstance(evt, ImmediateAlert):
        return evt.message
    return evt[1]


def to_proactive_output(
    event_id: str,
    message: str,
    priority: str,
    *,
    category: str | None = None,
    payload: dict | None = None,
) -> ProactiveOutput:
    if is_immediate_event(event_id):
        return ImmediateAlert(
            event_id=event_id,
            message=message,
            priority=priority,
            category=category or event_id.split("_", 1)[0],
            payload=payload or {},
        )
    return (event_id, message, priority)
