from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class OvertakingAidsEvent(CrewChiefEventModule):
    event_name = "overtaking_aids"

    def __init__(self) -> None:
        self._last_drs = False
        self._last_ptp = False

    def clear_state(self) -> None:
        self._last_drs = False
        self._last_ptp = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous or should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_overtaking_aids_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        if msg := self._eval_drs(ctx):
            messages.append(msg)
        if len(messages) < 1 and (msg := self._eval_ptp(ctx)):
            messages.append(msg)
        return messages

    def _eval_drs(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        drs = bool(
            ctx.current.get("drs_state")
            or ctx.current.get("rear_flap_activated")
        )
        was = bool(
            ctx.previous.get("drs_state")
            or ctx.previous.get("rear_flap_activated")
        )
        if drs == was:
            self._last_drs = drs
            return None
        self._last_drs = drs
        event_id = "drs_available" if drs else "drs_unavailable"
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, {}),
            priority=CrewChiefPriority.LOW,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
        )

    def _eval_ptp(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        ptp = bool(ctx.current.get("ptp_active") or ctx.current.get("power_to_pass_active"))
        was = bool(ctx.previous.get("ptp_active") or ctx.previous.get("power_to_pass_active"))
        if not ptp or ptp == was:
            self._last_ptp = ptp
            return None
        self._last_ptp = ptp
        return CrewChiefMessage(
            event_id="ptp_available",
            text=render_template("ptp_available", {}),
            priority=CrewChiefPriority.LOW,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
        )
