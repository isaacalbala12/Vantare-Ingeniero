from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import (
    lap_completed,
    normalize_display_sector,
    read_sector,
)
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

FAST_LAP_TOLERANCE_S = 0.05
SECTOR_FAST_DELTA_S = 0.15
SECTOR_SLOW_DELTA_S = 0.25
CONSISTENCY_LAP_COUNT = 5
CONSISTENCY_MIN_LAP_GAP = 3


class LapTimesEvent(CrewChiefEventModule):
    event_name = "lap_times"

    def __init__(self) -> None:
        self._lap_times: list[float] = []
        self._sector_entered_at: float = 0.0
        self._last_sector_raw: int | None = None
        self._best_sector_duration: dict[int, float] = {}
        self._last_consistency_at_lap: int = 0

    def clear_state(self) -> None:
        self.__init__()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_lap_time_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        messages.extend(self._eval_sector_timing(ctx))
        if lap_completed(ctx.previous, ctx.current):
            messages.extend(self._eval_lap_complete(ctx))
        return messages[:2]

    def _eval_lap_complete(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session):
            return []
        if ctx.current.get("in_pits"):
            return []

        curr = ctx.current
        lap_time = float(curr.get("lap_time_previous") or 0)
        best = float(curr.get("lap_time_best") or 0)
        lap_valid = curr.get("lap_valid", True)
        out: list[CrewChiefMessage] = []

        if lap_valid is False:
            out.append(self._msg("lap_invalid", {}, CrewChiefPriority.NORMAL))
            return out

        if lap_time > 0:
            self._lap_times.append(lap_time)
            if len(self._lap_times) > 20:
                self._lap_times.pop(0)

        if lap_time > 0 and best > 0 and lap_time <= best + FAST_LAP_TOLERANCE_S:
            out.append(
                self._msg(
                    "lap_personal_best",
                    {"time": f"{lap_time:.3f}"},
                    CrewChiefPriority.IMPORTANT,
                )
            )

        lap_num = int(curr.get("lap_number") or curr.get("completed_laps") or 0)
        if (
            len(self._lap_times) >= CONSISTENCY_LAP_COUNT
            and lap_num - self._last_consistency_at_lap >= CONSISTENCY_MIN_LAP_GAP
        ):
            trend = self._consistency_trend()
            if trend:
                self._last_consistency_at_lap = lap_num
                out.append(self._msg(trend, {}, CrewChiefPriority.LOW))

        return out[:2]

    def _eval_sector_timing(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session):
            return []
        if ctx.current.get("in_pits"):
            return []

        raw = read_sector(ctx.current)
        now = ctx.now_monotonic
        if self._last_sector_raw is None:
            self._last_sector_raw = raw
            self._sector_entered_at = now
            return []

        if raw == self._last_sector_raw:
            return []

        elapsed = now - self._sector_entered_at
        display = normalize_display_sector(self._last_sector_raw)
        best = self._best_sector_duration.get(display)
        msg: CrewChiefMessage | None = None
        if best is None or elapsed < best - SECTOR_FAST_DELTA_S:
            if best is not None:
                delta = best - elapsed
                msg = self._msg(
                    "sector_personal_best",
                    {"sector": str(display), "delta": f"{delta:.1f}s"},
                    CrewChiefPriority.NORMAL,
                )
            self._best_sector_duration[display] = elapsed
        elif best is not None and elapsed > best + SECTOR_SLOW_DELTA_S:
            delta = elapsed - best
            msg = self._msg(
                "sector_off_pace",
                {"sector": str(display), "delta": f"{delta:.1f}s"},
                CrewChiefPriority.LOW,
            )

        self._last_sector_raw = raw
        self._sector_entered_at = now
        return [msg] if msg else []

    def _consistency_trend(self) -> str | None:
        recent = self._lap_times[-CONSISTENCY_LAP_COUNT:]
        first_half = sum(recent[:2]) / 2
        second_half = sum(recent[-2:]) / 2
        spread = max(recent) - min(recent)
        if spread < 0.4:
            return "lap_consistency_stable"
        if second_half < first_half - 0.2:
            return "lap_consistency_improving"
        if second_half > first_half + 0.2:
            return "lap_consistency_worsening"
        return None

    @staticmethod
    def _msg(event_id: str, variables: dict, priority: CrewChiefPriority) -> CrewChiefMessage:
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, variables),
            priority=priority,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
        )
