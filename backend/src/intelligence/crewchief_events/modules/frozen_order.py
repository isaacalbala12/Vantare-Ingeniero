from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class FrozenOrderEvent(CrewChiefEventModule):
    event_name = "frozen_order"

    def __init__(self, stability_seconds: float = 2.0) -> None:
        self._stability_seconds = stability_seconds
        self._candidate: str | None = None
        self._candidate_since = 0.0
        self._last_spoken: str | None = None
        self._was_active = False

    def clear_state(self) -> None:
        self._candidate = None
        self._candidate_since = 0.0
        self._last_spoken = None
        self._was_active = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_frozen_order_messages", True):
            return []

        active = bool(ctx.current.get("frozen_order_active") or ctx.current.get("frozen_order"))
        was = bool(ctx.previous.get("frozen_order_active") or ctx.previous.get("frozen_order"))
        messages: list[CrewChiefMessage] = []

        if active and not was:
            messages.append(
                CrewChiefMessage(
                    event_id="frozen_order",
                    text=render_template("frozen_order", {}),
                    priority=CrewChiefPriority.CRITICAL,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=8000,
                    play_even_when_silenced=True,
                )
            )
        elif was and not active:
            messages.append(
                CrewChiefMessage(
                    event_id="frozen_order_cleared",
                    text=render_template("frozen_order_cleared", {}),
                    priority=CrewChiefPriority.IMPORTANT,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=8000,
                )
            )

        self._was_active = active
        if not active:
            self._candidate = None
            return messages

        instruction = str(ctx.current.get("frozen_order_message") or "").strip()
        if not instruction:
            return messages
        if instruction != self._candidate:
            self._candidate = instruction
            self._candidate_since = ctx.now_monotonic
            return messages
        if instruction == self._last_spoken or ctx.now_monotonic - self._candidate_since < self._stability_seconds:
            return messages
        self._last_spoken = instruction
        messages.append(
            CrewChiefMessage(
                event_id="frozen_order_instruction",
                text=instruction,
                priority=CrewChiefPriority.CRITICAL,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=5000,
                play_even_when_silenced=True,
                validation_key="frozen_order",
            )
        )
        return messages[:2]
