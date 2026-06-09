from src.intelligence.crewchief_events.session_gates import (
    is_hard_part,
    is_manual_formation_lap,
    is_racing_green,
    should_suppress_race_event,
)


def test_practice_suppresses_race_event_even_with_stale_race_string():
    telemetry = {"session_type": "race"}
    session = {"session_type_int": 3}

    assert should_suppress_race_event(telemetry, session) is True


def test_race_int_allows_race_event():
    telemetry = {"session_type": "practice"}
    session = {"session_type_int": 10}

    assert should_suppress_race_event(telemetry, session) is False


def test_manual_formation_lap_blocks_race_engineer_modules():
    assert is_manual_formation_lap({"manual_formation_lap": True}, {}) is True
    assert is_manual_formation_lap({"lap_number": 0}, {"phase": "RACE"}) is True


def test_fcy_is_not_racing_green():
    assert is_racing_green({"full_course_yellow_active": True}, {"phase": "RACE"}) is False
    assert is_racing_green({"yellow_flag_active": False}, {"phase": "RACE"}) is True


def test_braking_zone_counts_as_hard_part():
    assert is_hard_part({"brake_pressure": 0.4, "speed_ms": 55.0}) is True
    assert is_hard_part({"brake_pressure": 0.0, "speed_ms": 55.0}) is False
