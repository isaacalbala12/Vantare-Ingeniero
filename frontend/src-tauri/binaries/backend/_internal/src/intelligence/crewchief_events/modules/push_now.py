from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

PUSH_LAPS_LEFT = 3
PUSH_TIME_LEFT_S = 240.0


class PushNowEvent(CrewChiefEventModule):
    event_name = "push_now"

    def __init__(self) -> None:
        self._played_near_end = False

    def clear_state(self) -> None:
        self._played_near_end = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous or not is_racing_green(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_push_now_messages", True):
            return []
        if ctx.current.get("in_pits"):
            return []
        if self._played_near_end:
            return []

        laps_left = float(ctx.current.get("session_laps_left") or 999)
        time_left = float(ctx.current.get("session_time_left") or 99999)
        near_end = (0 < laps_left <= PUSH_LAPS_LEFT) or (0 < time_left <= PUSH_TIME_LEFT_S)
        if not near_end:
            return []

        event_id = self._pick_push_message(ctx)
        if not event_id:
            return []

        self._played_near_end = True
        pos = int(ctx.current.get("standing_position") or 0)
        return [
            CrewChiefMessage(
                event_id=event_id,
                text=render_template(event_id, {"position": str(pos)}),
                priority=CrewChiefPriority.NORMAL,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=10000,
            )
        ]

    def _pick_push_message(self, ctx: CrewChiefFrameContext) -> str | None:
        tele = ctx.current
        my_best = float(tele.get("lap_time_best") or 0)
        my_pos = int(tele.get("standing_position") or 99)
        laps_left = float(tele.get("session_laps_left") or 3)
        gap_ahead = float(tele.get("gap_ahead") or tele.get("time_gap_car_ahead") or 99)
        gap_behind = float(tele.get("gap_behind") or tele.get("time_gap_car_behind") or 99)

        ahead_best, behind_best = self._neighbor_bests(tele, my_pos)
        if my_best <= 0:
            return "push_to_win"

        if behind_best > 0 and behind_best < my_best:
            loss_time = (my_best - behind_best) * laps_left
            if loss_time > gap_behind:
                return "push_to_hold"

        if ahead_best > 0 and my_best < ahead_best:
            catch_time = (ahead_best - my_best) * laps_left
            if catch_time > gap_ahead and my_pos <= 4:
                return "push_to_win"

        return "push_to_win"

    @staticmethod
    def _neighbor_bests(tele: dict, my_pos: int) -> tuple[float, float]:
        ahead_best = 0.0
        behind_best = 0.0
        for comp in tele.get("competitors") or []:
            pos = int(comp.get("standing_position") or 0)
            best = float(comp.get("lap_time_best") or 0)
            if best <= 0:
                continue
            if pos == my_pos - 1:
                ahead_best = best
            elif pos == my_pos + 1:
                behind_best = best
        return ahead_best, behind_best
