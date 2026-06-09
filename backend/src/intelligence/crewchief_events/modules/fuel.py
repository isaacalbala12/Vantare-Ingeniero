from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed, read_sector
from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.fuel_safety import fuel_critical_from_strategy, fuel_critical_from_tick
from src.persistence.fuel_usage_store import FuelUsageStore

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

FUEL_STATUS_CHECK_INTERVAL_S = 5.0
BOX_THIS_LAP_LAPS = 1.5


class FuelEvent(CrewChiefEventModule):
    event_name = "fuel"

    def __init__(self) -> None:
        self._warned_about_to_run_out = False
        self._warned_tiers: set[int] = set()
        self._last_check_at = 0.0
        self._fuel_store = FuelUsageStore()

    def clear_state(self) -> None:
        self._warned_about_to_run_out = False
        self._warned_tiers.clear()
        self._last_check_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_fuel_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        if ctx.previous and lap_completed(ctx.previous, ctx.current):
            self._record_fuel_sample(ctx)

        now = ctx.now_monotonic
        if now - self._last_check_at >= FUEL_STATUS_CHECK_INTERVAL_S:
            self._last_check_at = now
            if msg := self._eval_fuel_levels(ctx):
                messages.append(msg)

        if msg := self._eval_about_to_run_out(ctx):
            messages.append(msg)
        if msg := self._eval_box_this_lap(ctx):
            messages.append(msg)

        return messages[:2]

    def _eval_fuel_levels(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        if ctx.current.get("in_pits"):
            return None
        if not fuel_critical_from_strategy(ctx.current, ctx.strategy, threshold=3.0):
            return None

        laps = self._fuel_laps(ctx)
        if laps >= 3.0:
            return None

        tier = 1 if laps < 1.0 else 2 if laps < 2.0 else 3
        if tier in self._warned_tiers:
            return None
        self._warned_tiers.add(tier)
        return CrewChiefMessage(
            event_id="fuel_laps_remaining",
            text=render_template("fuel_laps_remaining", {"level": tier, "laps": f"{laps:.1f}"}),
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=10000,
        )

    def _eval_about_to_run_out(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        laps = self._fuel_laps(ctx)
        sector = read_sector(ctx.current)
        if self._warned_about_to_run_out or laps >= 0.5 or sector != 0:
            return None
        self._warned_about_to_run_out = True
        return CrewChiefMessage(
            event_id="fuel_about_to_run_out",
            text=render_template("fuel_about_to_run_out", {}),
            priority=CrewChiefPriority.CRITICAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=5000,
            play_even_when_silenced=True,
        )

    def _eval_box_this_lap(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        laps = self._fuel_laps(ctx)
        if laps >= BOX_THIS_LAP_LAPS or read_sector(ctx.current) != 0:
            return None
        if not fuel_critical_from_tick(ctx.current, threshold=BOX_THIS_LAP_LAPS):
            return None
        return CrewChiefMessage(
            event_id="fuel_box_this_lap",
            text=render_template("fuel_box_this_lap", {}),
            priority=CrewChiefPriority.CRITICAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            play_even_when_silenced=True,
        )

    def _record_fuel_sample(self, ctx: CrewChiefFrameContext) -> None:
        used = ctx.current.get("fuel_used_last_lap")
        if used is None:
            fuel = ctx.strategy.get("fuel") or {}
            used = fuel.get("used_last_lap") or fuel.get("fuel_used_last_lap")
        if used is None:
            return
        game = str(ctx.session.get("game") or "LMU")
        car = str(ctx.current.get("car_name") or ctx.current.get("vehicle_name") or "unknown")
        track = str(ctx.current.get("track_name") or "unknown")
        self._fuel_store.record_sample(game, car, track, float(used))

    @staticmethod
    def _fuel_laps(ctx: CrewChiefFrameContext) -> float:
        raw = ctx.current.get("fuel_laps_remaining")
        if raw is None:
            fuel = ctx.strategy.get("fuel") or {}
            raw = fuel.get("estimated_laps_remaining")
        laps = float(raw or 99.0)
        multiplier = float(ctx.session.get("fuel_multiplier") or 1.0)
        if multiplier > 1.0:
            laps = laps / multiplier
        return laps
