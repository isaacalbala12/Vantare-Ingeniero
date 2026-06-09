from __future__ import annotations

from src.intelligence.crewchief_events.multiclass_utils import class_rank, is_similar_class
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

DEFAULT_SETTLE_S = 6.0
CHECK_INTERVAL_S = 4.0


class MulticlassEvent(CrewChiefEventModule):
    event_name = "multiclass"

    def __init__(self, settle_seconds: float = DEFAULT_SETTLE_S) -> None:
        self._settle_seconds = settle_seconds
        self._candidate_key: str | None = None
        self._candidate_since = 0.0
        self._last_spoken_key: str | None = None
        self._last_check_at = 0.0

    def clear_state(self) -> None:
        self._candidate_key = None
        self._candidate_since = 0.0
        self._last_spoken_key = None
        self._last_check_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_multiclass_messages", True):
            return []
        if ctx.now_monotonic - self._last_check_at < CHECK_INTERVAL_S:
            return []
        self._last_check_at = ctx.now_monotonic

        player_class = str(ctx.current.get("player_class") or "")
        player_rank = class_rank(player_class)
        best: tuple[str, str, dict] | None = None

        for comp in ctx.current.get("competitors") or []:
            if comp.get("in_pits"):
                continue
            class_name = str(comp.get("class_name") or comp.get("driver_class") or "")
            if not class_name or is_similar_class(class_name, player_class):
                continue
            gap = float(comp.get("gap_to_player") or comp.get("time_gap_to_player") or 99.0)
            rel = float(comp.get("relative_speed_ms") or 0.0)
            comp_rank = class_rank(class_name)
            idx = comp.get("driver_index")

            if comp_rank > player_rank and -3.0 < gap < 0.0 and rel > 3.0:
                leader = bool(comp.get("class_position") == 1 or comp.get("is_class_leader"))
                event_id = "multiclass_class_leader_behind" if leader else "multiclass_faster_behind"
                key = f"{event_id}:{idx}:{class_name}"
                if best is None:
                    best = (key, event_id, {"class_name": class_name})
            elif comp_rank < player_rank and 0.0 < gap < 2.0:
                key = f"multiclass_slower_ahead:{idx}:{class_name}"
                if best is None:
                    best = (key, "multiclass_slower_ahead", {"class_name": class_name})

        if not best:
            self._candidate_key = None
            return []

        key, event_id, vars_ = best
        if key != self._candidate_key:
            self._candidate_key = key
            self._candidate_since = ctx.now_monotonic
            return []
        if key == self._last_spoken_key:
            return []
        if ctx.now_monotonic - self._candidate_since < self._settle_seconds:
            return []

        self._last_spoken_key = key
        return [
            CrewChiefMessage(
                event_id=event_id,
                text=render_template(event_id, vars_),
                priority=CrewChiefPriority.IMPORTANT,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=6000,
            )
        ]
