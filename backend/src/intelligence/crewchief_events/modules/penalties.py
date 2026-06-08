from __future__ import annotations

from src.intelligence.penalty_tracker import PenaltyTracker

from ..base import CrewChiefEventModule
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


_PRIORITY_MAP = {
    "CRITICAL": CrewChiefPriority.CRITICAL,
    "HIGH": CrewChiefPriority.IMPORTANT,
    "MEDIUM": CrewChiefPriority.NORMAL,
    "LOW": CrewChiefPriority.LOW,
}


class PenaltiesEvent(CrewChiefEventModule):
    event_name = "penalties"

    def __init__(self, tracker: PenaltyTracker | None = None) -> None:
        self._tracker = tracker or PenaltyTracker()

    @property
    def tracker(self) -> PenaltyTracker:
        return self._tracker

    def clear_state(self) -> None:
        self._tracker.reset_session()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []

        current = ctx.current
        messages: list[CrewChiefMessage] = []

        cut = self._tracker.evaluate_cut_track(
            int(current.get("track_limits_steps") or 0),
            ctx.now_monotonic,
        )
        if cut is not None:
            messages.append(self._from_alert(cut))

        alert = self._tracker.evaluate(
            int(current.get("num_penalties") or 0),
            int(current.get("lap_number") or 0),
            int(
                current.get("current_sector")
                if current.get("current_sector") is not None
                else current.get("mSector")
                if current.get("mSector") is not None
                else current.get("sector")
                or 0
            ),
            bool(current.get("in_pits") or current.get("in_garage")),
        )
        if alert is not None:
            messages.append(self._from_alert(alert))
        return messages

    @staticmethod
    def _from_alert(alert) -> CrewChiefMessage:
        priority = _PRIORITY_MAP.get(alert.priority, CrewChiefPriority.IMPORTANT)
        return CrewChiefMessage(
            event_id=alert.event_id,
            text=alert.message,
            priority=priority,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=6000,
            play_even_when_silenced=alert.priority in ("CRITICAL", "HIGH"),
            payload=dict(alert.payload),
        )
