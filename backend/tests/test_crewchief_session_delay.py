from src.intelligence.crewchief_events.session_delay import (
    SESSION_START_DELAY_S,
    should_delay_non_critical_message,
)
from src.intelligence.crewchief_events.types import (
    CrewChiefChannel,
    CrewChiefMessage,
    CrewChiefPriority,
)


def test_critical_messages_never_delayed():
    msg = CrewChiefMessage(
        event_id="flag_yellow",
        text="Amarilla.",
        priority=CrewChiefPriority.CRITICAL,
        channel=CrewChiefChannel.ENGINEER,
    )
    assert should_delay_non_critical_message(
        session={"session_joined_at": 100.0},
        now_monotonic=101.0,
        message=msg,
    ) is False


def test_normal_message_delayed_first_six_seconds():
    msg = CrewChiefMessage(
        event_id="lap_complete",
        text="Vuelta 1.",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
    )
    assert should_delay_non_critical_message(
        session={"session_joined_at": 100.0},
        now_monotonic=104.0,
        message=msg,
    ) is True
    assert should_delay_non_critical_message(
        session={"session_joined_at": 100.0},
        now_monotonic=100.0 + SESSION_START_DELAY_S + 0.1,
        message=msg,
    ) is False
