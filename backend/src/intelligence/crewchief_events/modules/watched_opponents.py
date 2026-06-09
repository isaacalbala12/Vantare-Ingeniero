from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.driver_names import shorten_driver_name

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

COOLDOWN_S = 30.0


class WatchedOpponentsEvent(CrewChiefEventModule):
    event_name = "watched_opponents"

    def __init__(self) -> None:
        self._last_event_at: dict[str, float] = {}

    def clear_state(self) -> None:
        self._last_event_at.clear()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session) or not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_watched_opponent_messages", True):
            return []

        watched = {int(x) for x in (ctx.session.get("watched_driver_indices") or [])}
        if not watched:
            return []

        prev = {int(c.get("driver_index", -1)): c for c in ctx.previous.get("competitors") or []}
        messages: list[CrewChiefMessage] = []
        now = ctx.now_monotonic

        for comp in ctx.current.get("competitors") or []:
            idx = int(comp.get("driver_index", -1))
            if idx not in watched:
                continue
            before = prev.get(idx)
            if not before:
                continue
            name = shorten_driver_name(str(comp.get("driver_name") or "Rival"))
            pos = int(comp.get("standing_position") or 0)

            if not before.get("in_pits") and comp.get("in_pits"):
                if msg := self._emit(now, f"pit:{idx}", "watched_opponent_pitting", {"name": name, "position": str(pos)}):
                    messages.append(msg)
            elif before.get("in_pits") and not comp.get("in_pits"):
                if msg := self._emit(now, f"exit:{idx}", "watched_opponent_pit_exit", {"name": name, "position": str(pos)}):
                    messages.append(msg)

            prev_gap = before.get("gap_to_player")
            curr_gap = comp.get("gap_to_player")
            if prev_gap is not None and curr_gap is not None:
                delta = float(curr_gap) - float(prev_gap)
                if abs(delta) >= 1.0:
                    trend = "acercándose" if delta < 0 else "alejándose"
                    if msg := self._emit(
                        now,
                        f"gap:{idx}",
                        "watched_opponent_gap",
                        {"name": name, "trend": trend, "delta": f"{abs(delta):.1f}"},
                    ):
                        messages.append(msg)

        return messages[:2]

    def _emit(self, now: float, key: str, event_id: str, vars_: dict) -> CrewChiefMessage | None:
        last = self._last_event_at.get(key, 0.0)
        if last > 0 and now - last < COOLDOWN_S:
            return None
        self._last_event_at[key] = now
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, vars_),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=10000,
        )
