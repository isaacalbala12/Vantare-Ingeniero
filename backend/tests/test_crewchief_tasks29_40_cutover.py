from src.intelligence.immediate_alert import proactive_event_id
from src.intelligence.proactive_monitors import ProactiveMonitorSuite
from src.intelligence.triggers import HybridDeployMapTrigger, MulticlassWarningTrigger


def test_hybrid_trigger_suppressed_when_cc_battery_on():
    trigger = HybridDeployMapTrigger()
    tele = {"battery_charge": 10.0, "battery_drain": 2.0, "battery_regen": 0.0, "in_pits": False}
    assert trigger.condition(tele, {}, {"enable_battery_messages": True}) is False


def test_multiclass_trigger_suppressed_when_cc_on():
    trigger = MulticlassWarningTrigger()
    tele = {
        "in_pits": False,
        "player_class": "GT3",
        "competitors": [{"driver_class": "Hypercar", "gap_to_player": -1.0, "in_pits": False}],
    }
    assert trigger.condition(tele, {}, {"enable_multiclass_messages": True}) is False


def test_proactive_no_tyre_monitor_after_cutover():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"lap_number": 5, "session_type": "race"},
        {"tyre_wear": {"fl": 90, "fr": 90, "rl": 90, "rr": 90}},
        {"phase": "RACE"},
    )
    assert not any(proactive_event_id(e) == "tyre_monitor" for e in events)


def test_proactive_no_drs_after_cutover():
    suite = ProactiveMonitorSuite()
    suite.evaluate({"drs_state": False, "session_type": "race"}, {}, {"phase": "RACE"})
    events = suite.evaluate({"drs_state": True, "session_type": "race"}, {}, {"phase": "RACE"})
    assert not any(proactive_event_id(e) == "drs" for e in events)
