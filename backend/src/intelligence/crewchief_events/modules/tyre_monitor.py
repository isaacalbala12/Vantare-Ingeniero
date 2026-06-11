from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.phrase_picker import trigger_phrase_for_session
from src.intelligence.crewchief_events.vehicle_thresholds import (
    BRAKE_WEAR_WARN_PCT,
    TYRE_WEAR_WARN_PCT,
    avg_tyre_wear,
    max_brake_wear,
    tyre_temp_level,
)

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

CHECK_INTERVAL_S = 5.0


class TyreMonitorEvent(CrewChiefEventModule):
    event_name = "tyre_monitor"

    def __init__(self) -> None:
        self._warned_temp: set[str] = set()
        self._warned_wear = False
        self._warned_brake = False
        self._last_check_at = 0.0

    def clear_state(self) -> None:
        self._warned_temp.clear()
        self._warned_wear = False
        self._warned_brake = False
        self._last_check_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session) or ctx.current.get("in_pits"):
            return []
        now = ctx.now_monotonic
        if now - self._last_check_at < CHECK_INTERVAL_S:
            return []
        self._last_check_at = now

        out: list[CrewChiefMessage] = []
        if session_enable_flag(ctx.session, "enable_tyre_temp_messages", True):
            if msg := self._eval_temp(ctx):
                out.append(msg)
        if session_enable_flag(ctx.session, "enable_tyre_wear_messages", True):
            if msg := self._eval_wear(ctx):
                out.append(msg)
        if session_enable_flag(ctx.session, "enable_brake_wear_messages", True):
            if msg := self._eval_brake(ctx):
                out.append(msg)
        return out[:2]

    def _eval_temp(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        level = tyre_temp_level(ctx.current)
        if not level:
            return None
        wheel, kind = level
        key = f"{kind}:{wheel}"
        if key in self._warned_temp:
            return None
        self._warned_temp.add(key)
        event_id = "tyre_cooking" if kind == "cooking" else "tyre_hot"
        axle = "front" if wheel in ("fl", "fr") else "rear"
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, {"wheel": wheel, "axle": axle}),
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=10000,
        )

    def _eval_wear(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        avg = avg_tyre_wear(ctx.current, ctx.strategy)
        if avg < TYRE_WEAR_WARN_PCT or self._warned_wear:
            return None
        self._warned_wear = True
        fallback = render_template("tyre_wear_high", {"wear": f"{avg:.0f}"})
        return CrewChiefMessage(
            event_id="tyre_wear_high",
            text=trigger_phrase_for_session(ctx.session, "tyre_wear_high", fallback),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=12000,
        )

    def _eval_brake(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        mx = max_brake_wear(ctx.current, ctx.strategy)
        if mx < BRAKE_WEAR_WARN_PCT or self._warned_brake:
            return None
        self._warned_brake = True
        fallback = render_template("brake_wear_high", {"wear": f"{mx:.0f}"})
        return CrewChiefMessage(
            event_id="brake_wear_high",
            text=trigger_phrase_for_session(ctx.session, "brake_wear_high", fallback),
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=12000,
        )
