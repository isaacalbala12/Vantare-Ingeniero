from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.sector_analysis import analyze_sectors

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

REPORT_INTERVAL_S = 60.0


class StrategyEvent(CrewChiefEventModule):
    event_name = "strategy"

    def __init__(self) -> None:
        self._last_report_at = 0.0

    def clear_state(self) -> None:
        self._last_report_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_strategy_messages", True):
            return []
        level = str(ctx.session.get("verbosity_level") or "normal").lower()
        if level not in ("detailed", "low"):
            return []

        now = ctx.now_monotonic
        if now - self._last_report_at < REPORT_INTERVAL_S:
            return []

        track = str(ctx.current.get("track_name") or "")
        track_len = float(ctx.current.get("track_length") or ctx.strategy.get("track_length") or 7000)
        fuel_raw = ctx.current.get("fuel_per_lap_raw") or ctx.strategy.get("fuel_per_lap_raw") or []
        fuel_last = ctx.current.get("fuel_per_lap_last") or ctx.strategy.get("fuel_per_lap_last") or []
        if not track or not fuel_raw or not fuel_last:
            return []

        insights = analyze_sectors(fuel_raw, fuel_last, track, track_len)
        if not insights:
            return []

        top = insights[0]
        advice = f"{top.corner_name}: conviene {top.recommendation}."
        self._last_report_at = now
        return [
            CrewChiefMessage(
                event_id="strategy_sector_advice",
                text=render_template("strategy_sector_advice", {"advice": advice}),
                priority=CrewChiefPriority.LOW,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=15000,
            )
        ]
