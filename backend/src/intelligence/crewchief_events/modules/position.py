from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.driver_names import shorten_driver_name

from ..base import CrewChiefEventModule
from ..session_gates import is_racing_green, should_suppress_race_event
from ..types import (
    CrewChiefChannel,
    CrewChiefFrameContext,
    CrewChiefMessage,
    CrewChiefPriority,
)

MIN_OVERTAKE_GAP_S = 0.15
OVERTAKE_COOLDOWN_S = 20.0
MAX_BEING_OVERTAKEN_PER_SESSION = 60
RACE_START_QUALITY_MIN_LAP = 2


class PositionEvent(CrewChiefEventModule):
    event_name = "position"

    def __init__(self) -> None:
        self._last_opponent_ahead_key: str | None = None
        self._last_key_behind: str | None = None
        self._gap_samples_ahead: list[float] = []
        self._last_overtake_at = 0.0
        self._last_being_overtaken_at = 0.0
        self._overtake_complaints = 0
        self._race_start_quality_announced = False
        self._grid_side_announced = False
        self._last_position_reminder_at = 0.0

    def clear_state(self) -> None:
        self._last_opponent_ahead_key = None
        self._last_key_behind = None
        self._gap_samples_ahead = []
        self._last_overtake_at = 0.0
        self._last_being_overtaken_at = 0.0
        self._overtake_complaints = 0
        self._race_start_quality_announced = False
        self._grid_side_announced = False
        self._last_position_reminder_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []

        messages: list[CrewChiefMessage] = []
        grid_side = self._eval_grid_side_announcement(ctx)
        if grid_side:
            messages.append(grid_side)
        start_quality = self._eval_race_start_quality(ctx)
        if start_quality:
            messages.append(start_quality)

        if not is_racing_green(ctx.current, ctx.session):
            return messages

        messages.extend(self._eval_overtakes(ctx))
        messages.extend(self._eval_standing_change(ctx))
        reminder = self._eval_position_reminder(ctx)
        if reminder:
            messages.append(reminder)
        return messages

    def _eval_grid_side_announcement(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        if self._grid_side_announced:
            return None
        grid_side = ctx.current.get("grid_side")
        if not grid_side:
            return None
        lap = int(ctx.current.get("lap_number") or 0)
        if lap > 1:
            return None
        self._grid_side_announced = True
        text = render_template("race_start_grid_side", {"side": str(grid_side)})
        return CrewChiefMessage(
            event_id="race_start_grid_side",
            text=text,
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key=f"grid_side:{grid_side}",
        )

    def _eval_race_start_quality(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        if self._race_start_quality_announced:
            return None
        start_pos = ctx.current.get("start_standing_position")
        if start_pos is None:
            return None
        lap = int(ctx.current.get("lap_number") or 0)
        if lap < RACE_START_QUALITY_MIN_LAP:
            return None
        current = ctx.current.get("standing_position")
        if current is None:
            return None
        current_pos = int(current)
        if current_pos <= 0:
            return None

        start_pos_int = int(start_pos)
        delta = start_pos_int - current_pos
        self._race_start_quality_announced = True
        if delta >= 3:
            text = render_template("race_start_good", {"gain": delta})
            event_id = "race_start_good"
        elif delta >= 1:
            text = render_template("race_start_good", {"gain": delta})
            event_id = "race_start_good"
        elif delta <= -5:
            text = render_template("race_start_bad", {"lost": abs(delta), "terrible": True})
            event_id = "race_start_bad"
        elif delta <= -3:
            text = render_template("race_start_bad", {"lost": abs(delta)})
            event_id = "race_start_bad"
        else:
            return None

        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key=f"race_start:{start_pos_int}",
        )

    def _eval_standing_change(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        previous = ctx.previous_position
        current = ctx.current_position
        if previous is None or current is None or previous == current:
            return []

        if current < previous:
            opponent = ctx.current.get("last_overtake_driver") or ctx.current.get("driver_ahead_name")
            if opponent:
                text = render_template(
                    "position_overtake",
                    {"with_driver": True, "driver_name": shorten_driver_name(str(opponent))},
                )
            else:
                text = render_template("position_overtake", {"with_position": True, "position": current})
            event_id = "overtake_position_gain"
        else:
            opponent = ctx.current.get("last_overtake_driver") or ctx.current.get("driver_behind_name")
            if opponent:
                text = render_template(
                    "position_lost",
                    {"with_driver": True, "driver_name": shorten_driver_name(str(opponent))},
                )
            else:
                text = render_template("position_lost", {"with_position": True, "position": current})
            event_id = "position_loss"

        return [
            CrewChiefMessage(
                event_id=event_id,
                text=text,
                priority=CrewChiefPriority.IMPORTANT,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=5000,
                validation_key=f"position:{current}",
            )
        ]

    def _eval_overtakes(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        tick = ctx.current
        now = ctx.now_monotonic
        if bool(tick.get("in_pits") or tick.get("in_garage")):
            return []
        if bool(
            tick.get("yellow_flag_active")
            or tick.get("full_course_yellow_active")
            or tick.get("safety_car_active")
        ):
            return []

        competitors = [
            c if isinstance(c, dict) else c.model_dump()
            for c in (tick.get("competitors") or [])
            if isinstance(c, dict) or hasattr(c, "model_dump")
        ]
        if not competitors:
            return []

        my_position = int(tick.get("standing_position", 1) or 1)
        comp_ahead = min(
            (
                c
                for c in competitors
                if int(c.get("standing_position", 99)) < my_position and not c.get("in_pits", False)
            ),
            key=lambda c: abs(int(c.get("standing_position", 99)) - my_position),
            default=None,
        )
        comp_behind = min(
            (
                c
                for c in competitors
                if int(c.get("standing_position", 99)) > my_position and not c.get("in_pits", False)
            ),
            key=lambda c: abs(int(c.get("standing_position", 99)) - my_position),
            default=None,
        )
        current_key_ahead = str(comp_ahead.get("driver_index", -1)) if comp_ahead else None
        current_key_behind = str(comp_behind.get("driver_index", -1)) if comp_behind else None

        gap_ahead, _ = self._gap_from_telemetry(tick)
        self._gap_samples_ahead.append(gap_ahead)
        if len(self._gap_samples_ahead) > 100:
            self._gap_samples_ahead.pop(0)

        messages: list[CrewChiefMessage] = []

        if (
            current_key_ahead != self._last_opponent_ahead_key
            and self._last_opponent_ahead_key is not None
            and current_key_ahead is not None
            and (now - self._last_overtake_at) >= OVERTAKE_COOLDOWN_S
        ):
            if comp_behind and str(comp_behind.get("driver_index", -1)) == self._last_opponent_ahead_key:
                if comp_ahead and not comp_ahead.get("in_pits", False):
                    recent = self._gap_samples_ahead[-20:]
                    gap_mean = sum(recent) / max(1, len(recent))
                    if gap_mean > MIN_OVERTAKE_GAP_S:
                        name = shorten_driver_name(str(comp_ahead.get("driver_name", "")))
                        text = (
                            render_template(
                                "position_overtake",
                                {"with_driver": True, "driver_name": name},
                            )
                            if name
                            else render_template("position_overtake")
                        )
                        messages.append(
                            CrewChiefMessage(
                                event_id="overtake",
                                text=text,
                                priority=CrewChiefPriority.IMPORTANT,
                                channel=CrewChiefChannel.ENGINEER,
                                ttl_ms=5000,
                                validation_key=f"overtake:{my_position}",
                            )
                        )
                        self._last_overtake_at = now

        if (
            current_key_behind != self._last_key_behind
            and self._last_key_behind is not None
            and current_key_behind is not None
            and (now - self._last_being_overtaken_at) >= OVERTAKE_COOLDOWN_S
        ):
            if comp_ahead and str(comp_ahead.get("driver_index", -1)) == self._last_key_behind:
                if self._overtake_complaints < MAX_BEING_OVERTAKEN_PER_SESSION:
                    name = shorten_driver_name(str(comp_behind.get("driver_name", ""))) if comp_behind else ""
                    text = (
                        render_template(
                            "position_lost",
                            {"with_driver": True, "driver_name": name},
                        )
                        if name
                        else render_template("position_lost")
                    )
                    messages.append(
                        CrewChiefMessage(
                            event_id="being_overtaken",
                            text=text,
                            priority=CrewChiefPriority.IMPORTANT,
                            channel=CrewChiefChannel.ENGINEER,
                            ttl_ms=5000,
                            validation_key=f"overtaken:{my_position}",
                        )
                    )
                    self._last_being_overtaken_at = now
                    self._overtake_complaints += 1

        self._last_opponent_ahead_key = current_key_ahead
        self._last_key_behind = current_key_behind
        return messages

    def _eval_position_reminder(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        if ctx.session.get("verbosity_level") != "detailed":
            return None
        now = ctx.now_monotonic
        if now - self._last_position_reminder_at < 120.0:
            return None
        pos = ctx.current_position
        if pos is None:
            return None
        sector = int(
            ctx.current.get("sector")
            if ctx.current.get("sector") is not None
            else ctx.current.get("mSector")
            if ctx.current.get("mSector") is not None
            else 1
        )
        if sector != 1:
            return None
        self._last_position_reminder_at = now
        return CrewChiefMessage(
            event_id="position_reminder",
            text=f"Posición P{pos}.",
            priority=CrewChiefPriority.LOW,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=6000,
            validation_key=f"position_reminder:{pos}",
        )

    @staticmethod
    def _gap_from_telemetry(telemetry: dict) -> tuple[float, float]:
        ahead = telemetry.get("gap_ahead")
        if ahead is None:
            ahead = telemetry.get("time_gap_car_ahead") or telemetry.get("time_gap_place_ahead")
        behind = telemetry.get("gap_behind")
        if behind is None:
            behind = telemetry.get("time_gap_car_behind") or telemetry.get("time_gap_place_behind")
        return float(ahead or 99.0), float(behind or 99.0)
