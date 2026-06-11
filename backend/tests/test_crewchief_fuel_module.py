from src.intelligence.crewchief_events.modules.fuel import FuelEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_sector_three_about_to_run_out_message():
    module = FuelEvent()
    ctx = CrewChiefFrameContext(
        previous={"fuel_laps_remaining": 0.7, "session_type": "race"},
        current={"fuel_laps_remaining": 0.4, "sector": 0, "session_type": "race"},
        strategy={},
        session={"phase": "RACE"},
        now_monotonic=10.0,
    )

    messages = module.evaluate(ctx)

    assert messages[0].event_id == "fuel_about_to_run_out"
    text = messages[0].text.lower()
    assert any(w in text for w in ("combustible", "gasolina", "vueltas", "boxes", "parada"))
    assert messages[0].play_even_when_silenced is True


def test_fuel_laps_remaining_tier():
    module = FuelEvent()
    ctx = CrewChiefFrameContext(
        previous={"fuel_laps_remaining": 2.5, "session_type": "race"},
        current={"fuel_laps_remaining": 2.5, "in_pits": False, "session_type": "race"},
        strategy={"fuel": {"estimated_laps_remaining": 2.5, "pit_stops_needed": 1}},
        session={"phase": "RACE", "enable_fuel_messages": True},
        now_monotonic=10.0,
    )
    messages = module.evaluate(ctx)
    assert any(
        m.event_id == "fuel_laps_remaining"
        and any(w in m.text.lower() for w in ("combustible", "gasolina", "vueltas", "boxes", "parada"))
        for m in messages
    )


def test_fuel_box_this_lap_in_sector_three():
    module = FuelEvent()
    ctx = CrewChiefFrameContext(
        previous={"fuel_laps_remaining": 1.2, "sector": 1, "session_type": "race"},
        current={
            "fuel_laps_remaining": 1.0,
            "sector": 0,
            "session_type": "race",
            "pit_stops_needed": 1,
        },
        strategy={},
        session={"phase": "RACE", "enable_fuel_messages": True},
        now_monotonic=10.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "fuel_box_this_lap" for m in messages)
