from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class LapCounterEvent(CrewChiefEventModule):
    event_name = "lap_counter"

    def __init__(self) -> None:
        self._last_lap_announced = False

    def clear_state(self) -> None:
        self._last_lap_announced = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_lap_counter_messages", True):
            return []
        if not is_racing_green(ctx.current, ctx.session):
            return []

        messages: list[CrewChiefMessage] = []
        laps_left = ctx.current.get("session_laps_left")
        if laps_left is not None and float(laps_left) > 1.0:
            self._last_lap_announced = False

        if laps_left is not None and float(laps_left) <= 1.0 and not self._last_lap_announced:
            self._last_lap_announced = True
            messages.append(
                CrewChiefMessage(
                    event_id="last_lap_race",
                    text=render_template("last_lap_race", {}),
                    priority=CrewChiefPriority.IMPORTANT,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=10000,
                    play_even_when_silenced=True,
                )
            )

        if lap_completed(ctx.previous, ctx.current):
            lap = int(ctx.current.get("lap_number") or ctx.current.get("completed_laps") or 0)
            if lap > 0 and self._should_announce_lap(lap, ctx.session):
                messages.append(
                    CrewChiefMessage(
                        event_id="lap_counter_announce",
                        text=render_template("lap_counter_announce", {"lap": str(lap)}),
                        priority=CrewChiefPriority.LOW,
                        channel=CrewChiefChannel.ENGINEER,
                        ttl_ms=6000,
                    )
                )
        return messages[:2]

    @staticmethod
    def _should_announce_lap(lap: int, session: dict) -> bool:
        level = str(session.get("verbosity_level") or "normal").lower()
        if level == "detailed":
            return True
        return lap % 5 == 0
