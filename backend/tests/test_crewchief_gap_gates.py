from src.intelligence.crewchief_events.cc_gates import (
    gap_frequency_sectors,
    is_near_race_end,
    should_emit_gap_message,
)


def test_gap_messages_on_by_default():
    tele = {"session_type_int": 10, "in_pits": False}
    assert should_emit_gap_message(tele, {}) is True


def test_gap_messages_off_when_disabled():
    session = {"enable_gap_messages": False}
    tele = {"session_type_int": 10, "in_pits": False}
    assert should_emit_gap_message(tele, session) is False


def test_gap_suppressed_in_pits():
    session = {"enable_gap_messages": True}
    tele = {"session_type_int": 10, "in_pits": True}
    assert should_emit_gap_message(tele, session) is False


def test_frequency_five_yields_six_to_eleven_sectors():
    session = {"frequency_of_gap_ahead_reports": 5, "gap_message_randomness": 5}
    low, high = gap_frequency_sectors(session, "ahead")
    assert low == 6
    assert high == 11


def test_near_race_end_last_two_laps():
    assert is_near_race_end({"session_laps_left": 2.0}) is True
    assert is_near_race_end({"session_laps_left": 5.0}) is False
