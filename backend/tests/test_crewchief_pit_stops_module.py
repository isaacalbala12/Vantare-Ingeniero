from src.intelligence.crewchief_events.modules.pit_stops import PitStopsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict, *, strategy: dict | None = None, session: dict | None = None, now: float = 1.0):
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy=strategy or {},
        session=session or {"phase": "race", "enable_pit_stop_messages": True, "verbosity_level": "normal"},
        now_monotonic=now,
    )


def test_pit_window_open_edge():
    module = PitStopsEvent()
    messages = module.evaluate(
        _ctx(
            {"in_pits": False, "lap_number": 5},
            {"in_pits": False, "lap_number": 5},
            strategy={"pit_window": {"pit_window_open": True, "optimal_pit_lap": 5, "window_close_lap": 10}},
        )
    )
    assert any(m.event_id == "pit_window_open" for m in messages)


def test_pit_entry_exit():
    module = PitStopsEvent()
    entry = module.evaluate(_ctx({"in_pits": False}, {"in_pits": True}))
    exit_msg = module.evaluate(_ctx({"in_pits": True}, {"in_pits": False, "standing_position": 4}))
    assert any(m.event_id == "pit_entry" for m in entry)
    assert any(m.event_id == "pit_exit" for m in exit_msg)


def test_prediction_on_demand():
    module = PitStopsEvent()
    messages = module.evaluate(
        _ctx(
            {"in_pits": False, "lap_number": 3, "session_type_int": 10},
            {
                "in_pits": False,
                "lap_number": 3,
                "standing_position": 2,
                "session_type_int": 10,
                "competitors": [],
                "fuel_laps_remaining": 10.0,
            },
            session={"phase": "race", "pit_prediction_requested": True, "enable_pit_stop_messages": True},
        )
    )
    assert any(m.event_id == "pit_stop_prediction" for m in messages)


def test_normal_verbosity_only_when_fuel_low():
    module = PitStopsEvent()
    low_fuel = module.evaluate(
        _ctx(
            {"in_pits": False, "lap_number": 8, "session_type_int": 10},
            {
                "in_pits": False,
                "lap_number": 8,
                "standing_position": 1,
                "session_type_int": 10,
                "competitors": [],
                "fuel_laps_remaining": 2.5,
            },
            session={"verbosity_level": "normal", "enable_pit_stop_messages": True},
            now=200.0,
        )
    )
    ok_fuel = module.evaluate(
        _ctx(
            {"in_pits": False, "lap_number": 8, "session_type_int": 10},
            {
                "in_pits": False,
                "lap_number": 8,
                "standing_position": 1,
                "session_type_int": 10,
                "competitors": [],
                "fuel_laps_remaining": 8.0,
            },
            session={"verbosity_level": "normal", "enable_pit_stop_messages": True},
            now=400.0,
        )
    )
    assert any(m.event_id == "pit_stop_prediction" for m in low_fuel)
    assert not any(m.event_id == "pit_stop_prediction" for m in ok_fuel)
