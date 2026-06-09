from __future__ import annotations

from src.intelligence.rain_monitor import RainLevelMonitor

from ..base import CrewChiefEventModule
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class RainEvent(CrewChiefEventModule):
    event_name = "rain"

    def __init__(self) -> None:
        self._monitor = RainLevelMonitor()

    def clear_state(self) -> None:
        self._monitor.reset_session()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        prev = float(
            (ctx.previous or {}).get("raining")
            or (ctx.previous or {}).get("rain_intensity")
            or (ctx.previous or {}).get("raining_intensity")
            or 0.0
        )
        curr = float(
            ctx.current.get("raining")
            or ctx.current.get("rain_intensity")
            or ctx.current.get("raining_intensity")
            or 0.0
        )
        if prev <= 0.0 and curr <= 0.0:
            return []

        alert = self._monitor.evaluate(curr, ctx.now_monotonic)
        if alert is None:
            return []

        priority = (
            CrewChiefPriority.IMPORTANT
            if alert.priority in ("HIGH", "CRITICAL")
            else CrewChiefPriority.NORMAL
        )
        return [
            CrewChiefMessage(
                alert.event_id,
                alert.message,
                priority,
                CrewChiefChannel.ENGINEER,
                ttl_ms=8000,
                validation_key=f"rain:{RainLevelMonitor._classify(curr).name.lower()}",
            )
        ]
