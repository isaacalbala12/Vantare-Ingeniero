from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed
from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.time_format import format_time_remaining

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class RaceTimeEvent(CrewChiefEventModule):
    event_name = "race_time"

    def __init__(self) -> None:
        self._last_announced_lap = 0

    def clear_state(self) -> None:
        self._last_announced_lap = 0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_race_time_messages", True):
            return []
        if not ctx.previous or not lap_completed(ctx.previous, ctx.current):
            return []

        lap = int(ctx.current.get("lap_number") or 0)
        if lap <= 0 or lap == self._last_announced_lap:
            return []
        if not self._should_announce(ctx, lap):
            return []

        self._last_announced_lap = lap
        laps_left = ctx.current.get("session_laps_left")
        time_left = ctx.current.get("session_time_left")

        if laps_left is not None and 0 < float(laps_left) < 999:
            return [
                CrewChiefMessage(
                    event_id="race_laps_remaining",
                    text=render_template("race_laps_remaining", {"laps": str(int(float(laps_left)))}),
                    priority=CrewChiefPriority.LOW,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=12000,
                )
            ]

        if time_left is not None and float(time_left) > 0:
            remaining = format_time_remaining(float(time_left))
            return [
                CrewChiefMessage(
                    event_id="race_time_remaining",
                    text=render_template("race_time_remaining", {"remaining": remaining}),
                    priority=CrewChiefPriority.LOW,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=12000,
                )
            ]
        return []

    @staticmethod
    def _should_announce(ctx: CrewChiefFrameContext, lap: int) -> bool:
        level = str(ctx.session.get("verbosity_level") or "normal").lower()
        if level == "detailed":
            return lap % 2 == 0
        return lap % 5 == 0
