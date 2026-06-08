from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.crewchief_events.vehicle_thresholds import battery_low

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class BatteryEvent(CrewChiefEventModule):
    event_name = "battery"

    def __init__(self) -> None:
        self._low_warned = False

    def clear_state(self) -> None:
        self._low_warned = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_battery_messages", True):
            return []
        if ctx.current.get("in_pits") or self._low_warned:
            return []
        if not battery_low(ctx.current):
            return []
        self._low_warned = True
        return [
            CrewChiefMessage(
                event_id="battery_low_soc",
                text=render_template("battery_low_soc", {}),
                priority=CrewChiefPriority.IMPORTANT,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=12000,
            )
        ]
