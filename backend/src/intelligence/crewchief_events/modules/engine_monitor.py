from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.crewchief_events.vehicle_thresholds import engine_overheat

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class EngineMonitorEvent(CrewChiefEventModule):
    event_name = "engine_monitor"

    def __init__(self) -> None:
        self._warned = False

    def clear_state(self) -> None:
        self._warned = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_engine_warnings", True):
            return []
        if ctx.current.get("in_pits") or self._warned:
            return []
        hit = engine_overheat(ctx.current)
        if not hit:
            return []
        _key, temp = hit
        self._warned = True
        return [
            CrewChiefMessage(
                event_id="engine_overheat",
                text=render_template("engine_overheat", {"temp": f"{temp:.0f}"}),
                priority=CrewChiefPriority.IMPORTANT,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=15000,
            )
        ]
