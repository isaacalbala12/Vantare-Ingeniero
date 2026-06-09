from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CrewChiefPriority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    IMPORTANT = "IMPORTANT"
    CRITICAL = "CRITICAL"

    @property
    def rank(self) -> int:
        return {
            CrewChiefPriority.LOW: 1,
            CrewChiefPriority.NORMAL: 2,
            CrewChiefPriority.IMPORTANT: 3,
            CrewChiefPriority.CRITICAL: 4,
        }[self]


class CrewChiefChannel(str, Enum):
    ENGINEER = "engineer"
    SPOTTER = "spotter"
    VOICE_RESPONSE = "voice_response"


@dataclass(frozen=True)
class CrewChiefMessage:
    event_id: str
    text: str
    priority: CrewChiefPriority
    channel: CrewChiefChannel
    ttl_ms: int = 10000
    delay_ms: int = 0
    play_even_when_silenced: bool = False
    can_interrupt: bool = True
    validation_key: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def immediate(self) -> bool:
        return (
            self.channel == CrewChiefChannel.SPOTTER
            or self.priority.rank >= CrewChiefPriority.IMPORTANT.rank
        )


@dataclass(frozen=True)
class CrewChiefFrameContext:
    previous: dict[str, Any] | None
    current: dict[str, Any]
    strategy: dict[str, Any]
    session: dict[str, Any]
    now_monotonic: float

    @property
    def previous_position(self) -> int | None:
        if not self.previous:
            return None
        raw = self.previous.get("standing_position")
        return int(raw) if raw is not None else None

    @property
    def current_position(self) -> int | None:
        raw = self.current.get("standing_position")
        return int(raw) if raw is not None else None
