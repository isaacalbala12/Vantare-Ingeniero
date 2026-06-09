from src.intelligence.spotter import SpotterService


def test_spotter_skips_gap_alerts_when_cc_gap_messages_enabled():
    spotter = SpotterService()
    spotter.apply_runtime_config({"enableGapMessages": True})
    tick = {"gap_ahead": 0.3, "gap_behind": 99.0, "session_type": "race", "speed_ms": 30.0}
    assert spotter._eval_gaps(tick) == []
