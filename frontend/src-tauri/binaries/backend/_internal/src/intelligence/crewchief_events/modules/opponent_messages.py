from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed
from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.driver_names import shorten_driver_name

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

FAST_LAP_TOLERANCE_S = 0.05


class OpponentMessagesEvent(CrewChiefEventModule):
    event_name = "opponent_messages"

    def __init__(self) -> None:
        self._competitor_laps: dict[int, int] = {}
        self._warned_fast: set[int] = set()

    def clear_state(self) -> None:
        self._competitor_laps.clear()
        self._warned_fast.clear()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session) or not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_opponent_messages", True):
            return []
        level = str(ctx.session.get("verbosity_level") or "normal").lower()
        if level != "detailed":
            return []

        if not lap_completed(ctx.previous, ctx.current):
            return []

        messages: list[CrewChiefMessage] = []
        for raw in ctx.current.get("competitors") or []:
            idx = int(raw.get("driver_index", -1))
            if idx < 0:
                continue
            clap = int(raw.get("lap_number", 0) or 0)
            prev = self._competitor_laps.get(idx, 0)
            if clap <= prev:
                continue
            lap_time = float(raw.get("lap_time_previous", 0) or 0)
            best = float(raw.get("lap_time_best", 0) or 0)
            if lap_time > 0 and best > 0 and lap_time <= best + FAST_LAP_TOLERANCE_S and idx not in self._warned_fast:
                self._warned_fast.add(idx)
                name = shorten_driver_name(str(raw.get("driver_name", "Rival")))
                messages.append(
                    CrewChiefMessage(
                        event_id="opponent_fast_lap",
                        text=render_template(
                            "opponent_fast_lap",
                            {"name": name, "time": f"{lap_time:.1f}"},
                        ),
                        priority=CrewChiefPriority.LOW,
                        channel=CrewChiefChannel.ENGINEER,
                        ttl_ms=10000,
                    )
                )
            self._competitor_laps[idx] = clap
        return messages[:1]
