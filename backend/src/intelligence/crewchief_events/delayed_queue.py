"""Cola de mensajes CC retrasados durante hard-parts (PlaybackModerator parity)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .session_gates import is_hard_part
from .types import CrewChiefFrameContext, CrewChiefMessage

MESSAGE_EXPIRY_S = 10.0


@dataclass
class _DelayedEntry:
    message: CrewChiefMessage
    enqueued_at: float
    expires_at: float


@dataclass
class DelayedMessageQueue:
    """Retiene mensajes NORMAL durante hard-parts y valida antes de emitir."""

    _pending: list[_DelayedEntry] = field(default_factory=list)
    _hard_part_active: bool = False

    def clear(self) -> None:
        self._pending.clear()

    def set_hard_part_active(self, active: bool) -> None:
        self._hard_part_active = active

    @property
    def hard_part_active(self) -> bool:
        return self._hard_part_active

    def should_delay(self, message: CrewChiefMessage, *, hard_part_active: bool | None = None) -> bool:
        active = self._hard_part_active if hard_part_active is None else hard_part_active
        return active and not message.immediate

    def enqueue(
        self,
        message: CrewChiefMessage,
        *,
        now: float,
        hard_part_active: bool | None = None,
    ) -> bool:
        """Encola si hay hard-part. Devuelve True si quedó retenido."""
        if not self.should_delay(message, hard_part_active=hard_part_active):
            return False
        delay_s = max(0.0, message.delay_ms / 1000.0)
        self._pending.append(
            _DelayedEntry(
                message=message,
                enqueued_at=now,
                expires_at=now + delay_s + MESSAGE_EXPIRY_S,
            )
        )
        return True

    def ready(
        self,
        now: float,
        ctx: CrewChiefFrameContext | None = None,
        *,
        validator: Callable[[CrewChiefMessage, CrewChiefFrameContext | None], bool] | None = None,
    ) -> list[CrewChiefMessage]:
        if self._hard_part_active:
            self._drop_expired(now)
            return []

        validate = validator or is_message_still_valid
        released: list[CrewChiefMessage] = []

        for entry in self._pending:
            if now >= entry.expires_at:
                continue
            if validate(entry.message, ctx):
                released.append(entry.message)

        self._pending = []
        return released

    def _drop_expired(self, now: float) -> None:
        self._pending = [entry for entry in self._pending if now < entry.expires_at]


def is_message_still_valid(
    message: CrewChiefMessage,
    ctx: CrewChiefFrameContext | None,
) -> bool:
    """Re-validación estilo Timings.cs:isMessageStillValid antes de hablar."""
    if ctx is None:
        return True

    key = message.validation_key or ""
    curr = ctx.current
    prev = ctx.previous or {}

    if key.startswith("gap:ahead:"):
        trend = key.split(":", 2)[-1]
        curr_gap = float(curr.get("time_gap_car_ahead") or curr.get("gap_ahead") or 999.0)
        prev_gap = float(prev.get("time_gap_car_ahead") or prev.get("gap_ahead") or curr_gap)
        if not (0.05 < curr_gap < 30.0):
            return False
        if trend == "decreasing":
            return prev_gap - curr_gap >= 0.2
        if trend == "increasing":
            return curr_gap - prev_gap >= 0.2
        if trend == "holding":
            return abs(curr_gap - prev_gap) <= 0.2
        if trend == "holding_up":
            return curr_gap < 2.0
        return True

    if key.startswith("gap:behind:"):
        trend = key.split(":", 2)[-1]
        curr_gap = float(curr.get("time_gap_car_behind") or curr.get("gap_behind") or 999.0)
        prev_gap = float(prev.get("time_gap_car_behind") or curr.get("gap_behind") or curr_gap)
        if not (0.05 < curr_gap < 30.0):
            return False
        if trend == "pressure":
            return curr_gap < 1.0
        if trend == "increasing":
            return curr_gap - prev_gap >= 0.2 or curr_gap < 1.0
        if trend == "decreasing":
            return prev_gap - curr_gap >= 0.2
        if trend == "holding":
            return abs(curr_gap - prev_gap) <= 0.2
        return True

    if key == "gap:ahead":
        prev_gap = float(prev.get("time_gap_car_ahead") or 999.0)
        curr_gap = float(curr.get("time_gap_car_ahead") or 999.0)
        if curr_gap >= 999.0 or curr_gap <= 0.05:
            return False
        return prev_gap - curr_gap >= 0.3

    if key.startswith("gap:"):
        gap = float(curr.get("time_gap_car_ahead") or curr.get("time_gap_car_behind") or 999.0)
        return 0.05 < gap < 5.0

    if key.startswith("position:"):
        expected = key.split(":", 1)[-1]
        current = ctx.current_position
        return current is not None and str(current) == expected

    return True


def update_hard_part_from_telemetry(queue: DelayedMessageQueue, telemetry: dict) -> None:
    queue.set_hard_part_active(is_hard_part(telemetry))
