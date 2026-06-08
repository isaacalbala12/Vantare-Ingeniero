from src.intelligence.crewchief_events.vehicle_thresholds import (
    avg_tyre_wear,
    max_brake_wear,
    tyre_temp_level,
)


def test_tyre_temp_level_hot_and_cooking():
    assert tyre_temp_level({"tyre_temp_fl": 110.0}) == ("fl", "hot")
    assert tyre_temp_level({"tyre_temp_fl": 125.0, "tyre_temp_fr": 100.0}) == ("fl", "cooking")


def test_avg_tyre_wear_from_strategy():
    strategy = {"tyre_wear": {"fl": 70, "fr": 80, "rl": 76, "rr": 74}}
    assert avg_tyre_wear({}, strategy) == 75.0


def test_max_brake_wear():
    strategy = {"brake_wear": {"fl": 60, "fr": 82, "rl": 55, "rr": 50}}
    assert max_brake_wear({}, strategy) == 82.0
