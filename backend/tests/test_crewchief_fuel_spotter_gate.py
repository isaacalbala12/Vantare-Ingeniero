from src.intelligence.spotter import SpotterService


def test_spotter_skips_fuel_when_cc_fuel_messages_enabled():
    spotter = SpotterService()
    tick = {
        "fuel_laps_remaining": 0.5,
        "estimated_laps_remaining": 0.5,
        "pit_stops_needed": 1,
        "session_type": "race",
    }
    assert spotter._eval_fuel_critical(tick) == []
