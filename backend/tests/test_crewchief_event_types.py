from src.intelligence.crewchief_events.types import (
    CrewChiefChannel,
    CrewChiefFrameContext,
    CrewChiefMessage,
    CrewChiefPriority,
)


def test_crewchief_message_defaults_are_safe_for_normal_engineer_event():
    msg = CrewChiefMessage(
        event_id="lap_complete",
        text="Vuelta 3. Tiempo 92.4.",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
    )

    assert msg.event_id == "lap_complete"
    assert msg.ttl_ms == 10000
    assert msg.play_even_when_silenced is False
    assert msg.immediate is False
    assert msg.payload == {}


def test_critical_spotter_message_is_immediate_and_short_lived():
    msg = CrewChiefMessage(
        event_id="car_left",
        text="Coche a la izquierda.",
        priority=CrewChiefPriority.CRITICAL,
        channel=CrewChiefChannel.SPOTTER,
        ttl_ms=1000,
        play_even_when_silenced=True,
    )

    assert msg.immediate is True
    assert msg.ttl_ms == 1000
    assert msg.play_even_when_silenced is True


def test_frame_context_exposes_previous_and_current_data():
    ctx = CrewChiefFrameContext(
        previous={"standing_position": 4},
        current={"standing_position": 3},
        strategy={"pit_window_open": False},
        session={"phase": "RACE"},
        now_monotonic=10.0,
    )

    assert ctx.previous_position == 4
    assert ctx.current_position == 3
