from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

STINT_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (900, "driver_swap_15_min"),
    (600, "driver_swap_10_min"),
    (300, "driver_swap_5_min"),
    (120, "driver_swap_2_min"),
)


class DriverSwapsEvent(CrewChiefEventModule):
    event_name = "driver_swaps"

    def __init__(self) -> None:
        self._last_driver = ""
        self._fired_stint: set[str] = set()

    def clear_state(self) -> None:
        self._last_driver = ""
        self._fired_stint = set()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_driver_swap_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        name = str(ctx.current.get("driver_name") or "").strip()
        if name:
            if self._last_driver and name != self._last_driver:
                text = render_template("driver_swap_detected", {"driver": name})
                messages.append(
                    CrewChiefMessage(
                        event_id="driver_swap_detected",
                        text=text,
                        priority=CrewChiefPriority.IMPORTANT,
                        channel=CrewChiefChannel.ENGINEER,
                    )
                )
            self._last_driver = name

        remaining_raw = ctx.current.get("driver_stint_seconds_remaining")
        if remaining_raw is not None:
            remaining = int(remaining_raw)
            prev_remaining = int(
                (ctx.previous or {}).get("driver_stint_seconds_remaining") or remaining + 1
            )
            for threshold, event_id in STINT_THRESHOLDS:
                if event_id in self._fired_stint:
                    continue
                if prev_remaining > threshold >= remaining:
                    self._fired_stint.add(event_id)
                    text = render_template(event_id, {})
                    messages.append(
                        CrewChiefMessage(
                            event_id=event_id,
                            text=text,
                            priority=CrewChiefPriority.IMPORTANT,
                            channel=CrewChiefChannel.ENGINEER,
                        )
                    )

            best_lap = float(ctx.current.get("lap_time_best") or 0)
            if (
                best_lap > 0
                and remaining < best_lap + 30
                and "driver_swap_pit_this_lap" not in self._fired_stint
            ):
                self._fired_stint.add("driver_swap_pit_this_lap")
                text = render_template("driver_swap_pit_this_lap", {})
                messages.append(
                    CrewChiefMessage(
                        event_id="driver_swap_pit_this_lap",
                        text=text,
                        priority=CrewChiefPriority.IMPORTANT,
                        channel=CrewChiefChannel.ENGINEER,
                    )
                )

        return messages[:1]
