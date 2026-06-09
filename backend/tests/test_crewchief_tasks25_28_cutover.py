from src.intelligence.triggers import (
    FuelCriticalTrigger,
    PitWindowClosingTrigger,
    PitWindowOpenedTrigger,
    PushNowTrigger,
    SessionEndTrigger,
)


def test_push_now_suppressed_when_cc_owns():
    trigger = PushNowTrigger()
    tele = {"in_pits": False, "session_laps_left": 2.0, "gap_behind": 99.0}
    session = {"enable_push_now_messages": True}
    assert trigger.condition(tele, {"pit_window": {}}, session) is False


def test_session_end_suppressed_when_cc_owns():
    trigger = SessionEndTrigger()
    tele = {"lap_number": 10, "session_laps_left": 0.5, "standing_position": 3, "lap_time_best": 100.0}
    session = {"enable_session_end_messages": True}
    assert trigger.condition(tele, {}, session) is False


def test_fuel_critical_suppressed_when_cc_owns():
    trigger = FuelCriticalTrigger()
    strategy = {"fuel": {"estimated_laps_remaining": 2.0, "pit_stops_needed": 1}}
    session = {"enable_fuel_messages": True}
    assert trigger.condition({"in_pits": False}, strategy, session) is False


def test_pit_window_suppressed_when_cc_owns():
    opened = PitWindowOpenedTrigger()
    closing = PitWindowClosingTrigger()
    strategy = {"pit_window": {"pit_window_open": True, "optimal_pit_lap": 5}}
    tele = {"in_pits": False, "lap_number": 4}
    session = {"enable_pit_stop_messages": True}
    assert opened.condition(tele, strategy, session) is False
    assert closing.condition(tele, strategy, session) is False
