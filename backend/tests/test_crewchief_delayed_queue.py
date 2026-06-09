from __future__ import annotations

from src.intelligence.crewchief_events.delayed_queue import DelayedMessageQueue
from src.intelligence.crewchief_events.types import (
    CrewChiefChannel,
    CrewChiefMessage,
    CrewChiefPriority,
)


def make_gap_message(gap_ahead: float = 1.2) -> CrewChiefMessage:
    return CrewChiefMessage(
        event_id="gap_ahead_decreasing",
        text=f"Gap {gap_ahead:.1f}.",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
        ttl_ms=8000,
        validation_key="gap:ahead",
    )


def test_gap_message_delayed_during_hard_part_then_validates():
    q = DelayedMessageQueue()
    msg = make_gap_message(gap_ahead=1.2)
    q.set_hard_part_active(True)
    assert q.enqueue(msg, now=0.0) is True
    assert q.ready(now=1.0) == []
    q.set_hard_part_active(False)
    ready = q.ready(now=2.0)
    assert ready
    assert ready[0].text.startswith("Gap")


def test_immediate_messages_are_not_delayed():
    q = DelayedMessageQueue()
    msg = CrewChiefMessage(
        event_id="penalty_pit_now",
        text="Entra a boxes ahora.",
        priority=CrewChiefPriority.CRITICAL,
        channel=CrewChiefChannel.ENGINEER,
    )
    assert q.enqueue(msg, now=0.0, hard_part_active=True) is False


def test_gap_message_invalidated_if_gap_widens():
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    q = DelayedMessageQueue()
    msg = make_gap_message(gap_ahead=1.2)
    q.enqueue(msg, now=0.0, hard_part_active=True)
    q.set_hard_part_active(False)
    ctx = CrewChiefFrameContext(
        previous={"time_gap_car_ahead": 2.0},
        current={"time_gap_car_ahead": 2.0},
        strategy={},
        session={"phase": "race"},
        now_monotonic=2.0,
    )
    assert q.ready(now=2.0, ctx=ctx) == []


def test_expired_delayed_message_is_dropped():
    q = DelayedMessageQueue()
    msg = make_gap_message()
    q.enqueue(msg, now=0.0, hard_part_active=True)
    q.set_hard_part_active(False)
    assert q.ready(now=20.0) == []


def test_gap_ahead_decreasing_still_valid_after_delay():
    from src.intelligence.crewchief_events.delayed_queue import is_message_still_valid
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    msg = CrewChiefMessage(
        event_id="gap_ahead_decreasing",
        text="Gap 1.2",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
        validation_key="gap:ahead:decreasing",
    )
    ctx = CrewChiefFrameContext(
        previous={"time_gap_car_ahead": 2.0},
        current={"time_gap_car_ahead": 1.2},
        strategy={},
        session={},
        now_monotonic=2.0,
    )
    assert is_message_still_valid(msg, ctx) is True


def test_gap_ahead_decreasing_invalid_if_gap_widens():
    from src.intelligence.crewchief_events.delayed_queue import is_message_still_valid
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    msg = CrewChiefMessage(
        event_id="gap_ahead_decreasing",
        text="Gap 1.2",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
        validation_key="gap:ahead:decreasing",
    )
    ctx = CrewChiefFrameContext(
        previous={"time_gap_car_ahead": 1.2},
        current={"time_gap_car_ahead": 2.5},
        strategy={},
        session={},
        now_monotonic=2.0,
    )
    assert is_message_still_valid(msg, ctx) is False
