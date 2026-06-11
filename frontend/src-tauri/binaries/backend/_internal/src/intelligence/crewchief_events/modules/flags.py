from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.flags_monitor import (
    FlagEvent,
    FlagEventType,
    detect_flag_transitions,
    snapshot_from_telemetry,
)
from src.intelligence.phrase_picker import trigger_phrase_for_session

from ..base import CrewChiefEventModule
from ..cc_gates import flag_on_cooldown, should_emit_flag_event
from ..session_gates import should_suppress_race_event
from ..types import (
    CrewChiefChannel,
    CrewChiefFrameContext,
    CrewChiefMessage,
    CrewChiefPriority,
)

_FLAG_TEMPLATE: dict[FlagEventType, tuple[str, dict]] = {
    FlagEventType.FCY_PITS_CLOSED: ("fcy_pits_closed", {}),
    FlagEventType.FCY: ("fcy_pits_closed", {"safety_car": False}),
    FlagEventType.SAFETY_CAR: ("flags_safety_car", {}),
    FlagEventType.FCY_PITS_OPEN: ("fcy_pits_open", {}),
    FlagEventType.FCY_LAST_LAP: ("fcy_last_lap", {}),
    FlagEventType.FCY_RESUME: ("fcy_prepare_green", {}),
    FlagEventType.GREEN: ("fcy_green", {}),
    FlagEventType.YELLOW: ("flags_yellow", {}),
    FlagEventType.BLUE: ("flags_blue", {}),
    FlagEventType.RED: ("flags_red", {}),
}


def _flag_text(event: FlagEvent, session: dict) -> str:
    if event.event_type == FlagEventType.FCY:
        phrase = trigger_phrase_for_session(session, "fcy_active", "")
        if phrase:
            return phrase
    if event.event_type == FlagEventType.GREEN and "retirada" in event.message.lower():
        return render_template("flags_blue_cleared")
    if event.event_type == FlagEventType.RED and "terminada" in event.message.lower():
        return render_template("flags_session_over")
    template_id, variables = _FLAG_TEMPLATE.get(event.event_type, ("", {}))
    if template_id:
        text = render_template(template_id, variables)
        if text:
            return text
    return event.message


def _priority_from_flag(rank: int) -> CrewChiefPriority:
    if rank >= 4:
        return CrewChiefPriority.CRITICAL
    if rank >= 3:
        return CrewChiefPriority.IMPORTANT
    return CrewChiefPriority.NORMAL


def _message_from_flag_event(event: FlagEvent, session: dict) -> CrewChiefMessage:
    priority = _priority_from_flag(event.priority)
    return CrewChiefMessage(
        event_id=f"flags_{event.event_type.value}",
        text=_flag_text(event, session),
        priority=priority,
        channel=CrewChiefChannel.ENGINEER,
        ttl_ms=5000 if priority == CrewChiefPriority.CRITICAL else 8000,
        play_even_when_silenced=priority.rank >= CrewChiefPriority.IMPORTANT.rank,
        validation_key=f"flags:{event.event_type.value}",
    )


class FlagsEvent(CrewChiefEventModule):
    event_name = "flags"

    def __init__(self) -> None:
        self._last_flag_played_at: dict[FlagEventType, float] = {}

    def clear_state(self) -> None:
        self._last_flag_played_at.clear()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []

        prev_snap = (
            snapshot_from_telemetry(ctx.previous) if ctx.previous is not None else None
        )
        curr_snap = snapshot_from_telemetry(ctx.current)
        in_pits = bool(ctx.current.get("in_pits") or ctx.current.get("in_garage"))
        now = ctx.now_monotonic

        messages: list[CrewChiefMessage] = []
        for event in detect_flag_transitions(prev_snap, curr_snap):
            if not should_emit_flag_event(
                event.event_type,
                telemetry=ctx.current,
                session=ctx.session,
                in_pits=in_pits,
            ):
                continue
            if flag_on_cooldown(event.event_type, now, self._last_flag_played_at):
                continue
            self._last_flag_played_at[event.event_type] = now
            messages.append(_message_from_flag_event(event, ctx.session))
        return messages
