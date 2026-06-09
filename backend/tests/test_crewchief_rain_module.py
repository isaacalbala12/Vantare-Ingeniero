from src.intelligence.crewchief_events.modules.rain import RainEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_rain_start_uses_current_raining_not_forecast():
    module = RainEvent()
    ctx = CrewChiefFrameContext(
        previous={"raining": 0.0, "session_type_int": 3},
        current={"raining": 0.35, "session_type_int": 3},
        strategy={"weather_forecast": {"rain_chance": 0}},
        session={"phase": "practice", "session_type_int": 3},
        now_monotonic=1.0,
    )

    messages = module.evaluate(ctx)

    assert messages[0].event_id.startswith("rain_")
    assert "lluvia" in messages[0].text.lower() or "llovizna" in messages[0].text.lower()
