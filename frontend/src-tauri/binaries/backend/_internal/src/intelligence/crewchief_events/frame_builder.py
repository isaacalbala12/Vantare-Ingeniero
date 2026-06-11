from __future__ import annotations

from typing import Any, Optional

from src.services.lmu_api import get_session_settings

from .lmu_context import build_lmu_session_context
from .types import CrewChiefFrameContext


def build_frame_context(
    *,
    previous: Optional[dict[str, Any]],
    current: dict[str, Any],
    strategy: dict[str, Any],
    now_monotonic: float,
) -> CrewChiefFrameContext:
    session = {
        "phase": current.get("game_phase"),
        "session_type_int": current.get("session_type_int"),
        "manual_formation_lap": current.get("on_manual_formation_lap", False),
        "session_time_left": current.get("session_time_left"),
        "yellow_flag_state": current.get("yellow_flag_state"),
        "sector_flags": current.get("sector_flags"),
        "condition_wetness": current.get("condition_wetness"),
        "start_standing_position": current.get("start_standing_position"),
    }
    session.update(build_lmu_session_context(get_session_settings()))
    session["session_joined_at"] = current.get("session_joined_at")
    session["session_start_delay_s"] = current.get("session_start_delay_s", 6.0)
    return CrewChiefFrameContext(
        previous=previous,
        current=current,
        strategy=strategy,
        session=session,
        now_monotonic=now_monotonic,
    )
