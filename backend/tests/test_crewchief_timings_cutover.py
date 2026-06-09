from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event
from src.intelligence.triggers import GapClosedTrigger


def test_gap_battle_events_are_cc_owned():
    assert is_cc_owned_event("gap_being_pressured")
    assert is_cc_owned_event("gap_holding_us_up")


def test_gap_closed_trigger_suppressed_when_cc_owns_battle():
    trigger = GapClosedTrigger()
    tele = {"gap_ahead": 1.0, "gap_behind": 99.0, "in_pits": False, "session_type": "race", "session_type_int": 10}
    assert trigger.condition(tele, {}, {"phase": "race"}) is False
