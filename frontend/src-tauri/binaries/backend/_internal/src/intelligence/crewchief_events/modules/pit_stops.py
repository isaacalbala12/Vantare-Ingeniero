from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.phrase_picker import trigger_phrase_for_session
from src.intelligence.pit_prediction import (
    count_pit_context,
    estimate_position_after_pit_stop,
    format_pit_exit_prediction,
)

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

PIT_PREDICTION_INTERVAL_DETAILED_S = 180.0
PIT_PREDICTION_MIN_LAP_DETAILED = 5
PIT_PREDICTION_FUEL_NORMAL_LAPS = 3.0


class PitStopsEvent(CrewChiefEventModule):
    event_name = "pit_stops"

    def __init__(self) -> None:
        self._window_was_open = False
        self._window_closing_played = False
        self._last_prediction_at = 0.0

    def clear_state(self) -> None:
        self._window_was_open = False
        self._window_closing_played = False
        self._last_prediction_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_pit_stop_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        messages.extend(self._eval_window(ctx))
        messages.extend(self._eval_player_pits(ctx))
        if len(messages) < 2:
            if pred := self._eval_prediction(ctx):
                messages.append(pred)
        return messages[:2]

    def _eval_window(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        pw = ctx.strategy.get("pit_window") or {}
        open_now = bool(pw.get("pit_window_open")) and not ctx.current.get("in_pits")
        messages: list[CrewChiefMessage] = []

        if open_now and not self._window_was_open:
            open_lap = int(pw.get("optimal_pit_lap") or ctx.current.get("lap_number") or 0)
            close_lap = int(pw.get("window_close_lap") or open_lap + 5)
            fallback = render_template(
                "pit_window_open",
                {"open_lap": str(open_lap), "close_lap": str(close_lap)},
            )
            messages.append(
                CrewChiefMessage(
                    event_id="pit_window_open",
                    text=trigger_phrase_for_session(ctx.session, "pit_window_opened", fallback),
                    priority=CrewChiefPriority.IMPORTANT,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=12000,
                )
            )

        if not open_now:
            self._window_closing_played = False

        if open_now and not self._window_closing_played:
            current_lap = int(ctx.current.get("lap_number") or 0)
            optimal = int(pw.get("optimal_pit_lap") or current_lap)
            close_lap = int(pw.get("window_close_lap") or optimal + 5)
            laps_left = close_lap - current_lap
            if 0 <= laps_left <= 2:
                self._window_closing_played = True
                messages.append(
                    CrewChiefMessage(
                        event_id="pit_window_closing",
                        text=render_template("pit_window_closing", {"laps": str(max(laps_left, 1))}),
                        priority=CrewChiefPriority.IMPORTANT,
                        channel=CrewChiefChannel.ENGINEER,
                        ttl_ms=10000,
                    )
                )

        self._window_was_open = open_now
        return messages

    def _eval_player_pits(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        in_pits = bool(ctx.current.get("in_pits"))
        was = bool(ctx.previous.get("in_pits"))
        out: list[CrewChiefMessage] = []
        if in_pits and not was:
            out.append(
                CrewChiefMessage(
                    event_id="pit_entry",
                    text=render_template("pit_entry", {}),
                    priority=CrewChiefPriority.NORMAL,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=8000,
                )
            )
        if was and not in_pits:
            pos = int(ctx.current.get("standing_position") or 0)
            out.append(
                CrewChiefMessage(
                    event_id="pit_exit",
                    text=render_template("pit_exit", {"position": str(pos)}),
                    priority=CrewChiefPriority.NORMAL,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=8000,
                )
            )
        return out

    def _eval_prediction(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        if not is_racing_green(ctx.current, ctx.session):
            return None
        if ctx.current.get("in_pits"):
            return None
        if not self._should_emit_prediction(ctx):
            return None

        competitors = ctx.current.get("competitors") or []
        pos = int(ctx.current.get("standing_position") or 0)
        ahead, behind = count_pit_context(competitors)
        est = estimate_position_after_pit_stop(pos, ahead, behind)
        pit_open = bool((ctx.strategy.get("pit_window") or {}).get("pit_window_open"))
        text = format_pit_exit_prediction(pos, est, pit_open)
        if not text:
            return None

        self._last_prediction_at = ctx.now_monotonic
        return CrewChiefMessage(
            event_id="pit_stop_prediction",
            text=render_template("pit_stop_prediction", {"message": text}),
            priority=CrewChiefPriority.LOW,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=15000,
        )

    def _should_emit_prediction(self, ctx: CrewChiefFrameContext) -> bool:
        if ctx.session.get("pit_prediction_requested"):
            return True

        level = str(ctx.session.get("verbosity_level") or "normal").lower()
        now = ctx.now_monotonic
        lap = int(ctx.current.get("lap_number") or 0)
        fuel_laps = float(
            ctx.current.get("fuel_laps_remaining")
            or (ctx.strategy.get("fuel") or {}).get("estimated_laps_remaining")
            or 99.0
        )

        if level == "detailed":
            if lap < PIT_PREDICTION_MIN_LAP_DETAILED:
                return False
            return now - self._last_prediction_at >= PIT_PREDICTION_INTERVAL_DETAILED_S

        return fuel_laps < PIT_PREDICTION_FUEL_NORMAL_LAPS
