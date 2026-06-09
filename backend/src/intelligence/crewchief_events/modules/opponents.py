from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.driver_names import shorten_driver_name

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

COOLDOWN_S = 45.0


class OpponentsEvent(CrewChiefEventModule):
    event_name = "opponents"

    def __init__(self) -> None:
        self._last_event_at: dict[str, float] = {}

    def clear_state(self) -> None:
        self._last_event_at.clear()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session) or not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_opponent_messages", True):
            return []

        my_pos = int(ctx.current.get("standing_position") or 0)
        prev = {str(c.get("driver_index")): c for c in ctx.previous.get("competitors") or []}
        messages: list[CrewChiefMessage] = []
        now = ctx.now_monotonic

        for comp in ctx.current.get("competitors") or []:
            key = str(comp.get("driver_index"))
            before = prev.get(key)
            if not before:
                continue
            comp_pos = int(comp.get("standing_position") or 0)
            if abs(comp_pos - my_pos) > 1:
                continue
            name = shorten_driver_name(str(comp.get("driver_name") or "Rival"))

            if not before.get("in_pits") and comp.get("in_pits"):
                if msg := self._emit(
                    now,
                    f"pit:{key}",
                    "opponent_pitting",
                    {"name": name, "position": str(comp_pos)},
                ):
                    messages.append(msg)
            elif before.get("in_pits") and not comp.get("in_pits"):
                if msg := self._emit(
                    now,
                    f"exit:{key}",
                    "opponent_pit_exit",
                    {"name": name, "position": str(comp_pos)},
                ):
                    messages.append(msg)

            prev_pos = int(before.get("standing_position") or 0)
            if prev_pos and comp_pos != prev_pos and abs(comp_pos - my_pos) <= 1:
                if msg := self._emit(
                    now,
                    f"pos:{key}",
                    "opponent_position_change",
                    {"name": name, "from": str(prev_pos), "to": str(comp_pos)},
                ):
                    messages.append(msg)

        return messages[:2]

    def _emit(self, now: float, cooldown_key: str, event_id: str, vars_: dict) -> CrewChiefMessage | None:
        last = self._last_event_at.get(cooldown_key, 0.0)
        if last > 0 and now - last < COOLDOWN_S:
            return None
        self._last_event_at[cooldown_key] = now
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, vars_),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
        )
