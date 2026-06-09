from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class SessionEndEvent(CrewChiefEventModule):
    event_name = "session_end"

    def __init__(self) -> None:
        self._announced = False

    def clear_state(self) -> None:
        self._announced = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous or self._announced:
            return []
        if not session_enable_flag(ctx.session, "enable_session_end_messages", True):
            return []

        prev_over = bool(ctx.previous.get("session_over"))
        curr_over = bool(ctx.current.get("session_over"))
        lap = int(ctx.current.get("lap_number") or ctx.current.get("completed_laps") or 0)
        if lap < 2:
            return []

        if not (curr_over and not prev_over):
            return []

        self._announced = True
        return [self._build_message(ctx)]

    def _build_message(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage:
        tele = ctx.current
        pos = int(tele.get("standing_position") or 0)
        start = int(tele.get("start_standing_position") or tele.get("start_class_position") or pos)
        gain = start - pos
        lost = pos - start

        if tele.get("disqualified") or int(tele.get("num_penalties") or 0) >= 99:
            event_id = "session_disqualified"
        elif tele.get("dnf") or tele.get("retired"):
            event_id = "session_dnf"
        elif pos == 1:
            event_id = "session_victory"
        elif pos <= 3:
            event_id = "session_podium"
        elif lost >= 5:
            event_id = "session_bad_finish"
        elif gain >= 3:
            event_id = "session_finish"
        else:
            event_id = "session_finish"

        text = render_template(
            event_id,
            {
                "position": str(pos),
                "gain": str(gain),
                "lost": str(lost),
                "good_gain": gain >= 3,
            },
        )
        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=15000,
            play_even_when_silenced=True,
        )
