from __future__ import annotations

import random

from src.intelligence.corner_names import format_lap_distance
from src.intelligence.crewchief_events.cc_gates import (
    gap_frequency_sectors,
    should_emit_gap_message,
)
from src.intelligence.crewchief_events.gap_trend import GapTrend, classify_gap_trend
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

MIN_GAP_S = 0.05
MAX_GAP_S = 30.0
PRESSURE_BEHIND_S = 10.0
PRESSURE_COOLDOWN_S = 60.0
HOLDING_UP_S = 30.0
CLOSE_GAP_S = 1.0


class TimingsEvent(CrewChiefEventModule):
    event_name = "timings"

    def __init__(self) -> None:
        self._last_sector: int | None = None
        self._gap_samples_ahead: list[float] = []
        self._gap_samples_behind: list[float] = []
        self._sectors_since_last_ahead = 0
        self._sectors_since_last_behind = 0
        self._sectors_until_next_ahead = 0
        self._sectors_until_next_behind = 0
        self._pressure_behind_since: float | None = None
        self._last_pressure_at: float = 0.0
        self._holding_up_since: float | None = None
        self._last_ahead_opponent_key: str | None = None
        self._rng = random.Random(42)

    def clear_state(self) -> None:
        self.__init__()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session) or not ctx.previous:
            return []
        if not should_emit_gap_message(ctx.current, ctx.session):
            return []

        sector = self._sector(ctx.current)
        sector_changed = self._last_sector is not None and sector != self._last_sector
        self._last_sector = sector

        ahead, behind = self._gaps(ctx.current)
        self._gap_samples_ahead.append(ahead)
        self._gap_samples_behind.append(behind)
        if len(self._gap_samples_ahead) > 20:
            self._gap_samples_ahead.pop(0)
        if len(self._gap_samples_behind) > 20:
            self._gap_samples_behind.pop(0)

        messages: list[CrewChiefMessage] = []

        if pressure := self._eval_pressure_behind(ctx, behind):
            messages.append(pressure)
        if holding := self._eval_holding_up(ctx, ahead):
            messages.append(holding)

        if sector_changed:
            self._sectors_since_last_ahead += 1
            self._sectors_since_last_behind += 1
            if self._sectors_since_last_ahead >= self._sectors_until_next_ahead:
                if msg := self._maybe_gap_ahead(ctx, ahead):
                    messages.append(msg)
                    self._sectors_since_last_ahead = 0
                    self._sectors_until_next_ahead = self._next_wait(ctx.session, "ahead")
            if self._sectors_since_last_behind >= self._sectors_until_next_behind:
                if msg := self._maybe_gap_behind(ctx, behind):
                    messages.append(msg)
                    self._sectors_since_last_behind = 0
                    self._sectors_until_next_behind = self._next_wait(ctx.session, "behind")

        return messages[:2]

    def _next_wait(self, session: dict, which: str) -> int:
        low, high = gap_frequency_sectors(session, which)
        return self._rng.randint(low, high)

    def _maybe_gap_ahead(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        if not (MIN_GAP_S < gap < MAX_GAP_S):
            return None
        trend = classify_gap_trend(self._gap_samples_ahead, close_threshold_s=CLOSE_GAP_S)
        if trend is None:
            return None
        event_id = {
            GapTrend.INCREASING: "gap_ahead_increasing",
            GapTrend.DECREASING: "gap_ahead_decreasing",
            GapTrend.HOLDING: "gap_ahead_holding",
            GapTrend.CLOSE: "gap_ahead_decreasing",
        }[trend]
        return self._build_gap_message(ctx, event_id, gap, validation=f"gap:ahead:{trend.value}")

    def _maybe_gap_behind(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        if not (MIN_GAP_S < gap < MAX_GAP_S):
            return None
        trend = classify_gap_trend(self._gap_samples_behind, close_threshold_s=CLOSE_GAP_S)
        if trend is None:
            return None
        event_id = {
            GapTrend.INCREASING: "gap_behind_increasing",
            GapTrend.DECREASING: "gap_behind_decreasing",
            GapTrend.HOLDING: "gap_behind_holding",
            GapTrend.CLOSE: "gap_behind_increasing",
        }[trend]
        return self._build_gap_message(ctx, event_id, gap, validation=f"gap:behind:{trend.value}")

    def _build_gap_message(
        self,
        ctx: CrewChiefFrameContext,
        event_id: str,
        gap: float,
        *,
        validation: str,
    ) -> CrewChiefMessage:
        corner = self._corner_phrase(ctx.current)
        variables: dict[str, str | bool] = {"gap": f"{gap:.1f}"}
        if corner:
            variables["with_corner"] = True
            variables["corner"] = corner
        text = render_template(event_id, variables)
        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key=validation,
        )

    def _eval_pressure_behind(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        now = ctx.now_monotonic
        if gap >= CLOSE_GAP_S:
            self._pressure_behind_since = None
            return None
        if self._pressure_behind_since is None:
            self._pressure_behind_since = now
            return None
        if now - self._pressure_behind_since < PRESSURE_BEHIND_S:
            return None
        if self._last_pressure_at > 0 and now - self._last_pressure_at < PRESSURE_COOLDOWN_S:
            return None
        self._pressure_behind_since = None
        self._last_pressure_at = now
        return CrewChiefMessage(
            event_id="gap_being_pressured",
            text=render_template("gap_being_pressured", {}),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key="gap:behind:pressure",
        )

    def _eval_holding_up(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        now = ctx.now_monotonic
        key = self._ahead_opponent_key(ctx.current)
        if key != self._last_ahead_opponent_key:
            self._holding_up_since = None
            self._last_ahead_opponent_key = key
        if gap >= 2.0 or key is None:
            self._holding_up_since = None
            return None
        if self._holding_up_since is None:
            self._holding_up_since = now
            return None
        if now - self._holding_up_since < HOLDING_UP_S:
            return None
        self._holding_up_since = None
        return CrewChiefMessage(
            event_id="gap_holding_us_up",
            text=render_template("gap_holding_us_up", {}),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key="gap:ahead:holding_up",
        )

    @staticmethod
    def _sector(telemetry: dict) -> int:
        raw = telemetry.get("sector")
        if raw is None:
            raw = telemetry.get("current_sector")
        if raw is None:
            raw = telemetry.get("mSector")
        return int(raw or 1)

    @staticmethod
    def _gaps(telemetry: dict) -> tuple[float, float]:
        ahead = telemetry.get("time_gap_car_ahead") or telemetry.get("gap_ahead") or 999.0
        behind = telemetry.get("time_gap_car_behind") or telemetry.get("gap_behind") or 999.0
        return float(ahead), float(behind)

    @staticmethod
    def _corner_phrase(telemetry: dict) -> str | None:
        track = str(telemetry.get("track_name") or "")
        dist = telemetry.get("lap_distance") or telemetry.get("distance_on_lap")
        if not track or dist is None:
            return None
        name = format_lap_distance(track, float(dist))
        if name.startswith("km "):
            return None
        return name

    @staticmethod
    def _ahead_opponent_key(telemetry: dict) -> str | None:
        my_pos = int(telemetry.get("standing_position") or 99)
        for comp in telemetry.get("competitors") or []:
            if int(comp.get("standing_position") or 99) == my_pos - 1:
                return str(comp.get("driver_index"))
        return None
