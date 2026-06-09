from __future__ import annotations

from .types import CrewChiefMessage, CrewChiefPriority

SESSION_START_DELAY_S = 6.0


def should_delay_non_critical_message(
    *,
    session: dict,
    now_monotonic: float,
    message: CrewChiefMessage,
) -> bool:
    if message.priority == CrewChiefPriority.CRITICAL:
        return False
    if message.play_even_when_silenced:
        return False
    joined = session.get("session_joined_at")
    if joined is None:
        return False
    elapsed = now_monotonic - float(joined)
    delay_s = float(session.get("session_start_delay_s") or SESSION_START_DELAY_S)
    return elapsed < delay_s
