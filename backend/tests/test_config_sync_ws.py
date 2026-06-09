"""Tests contrato config_update payload (engine + spotter)."""

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.spotter import SpotterService


def test_config_payload_fields_engine_and_spotter():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    spotter = SpotterService(broadcast_callback=lambda m: None)
    cfg = {
        "personalityProfileId": "formal",
        "verbosityLevel": "silent",
        "spotterClearDelayS": 0.15,
        "spotterOverlapDelayS": 2.0,
        "spotterHoldRepeatS": 3.0,
        "spotterGapFrequencyS": 60.0,
        "spotterCarLengthM": 4.5,
        "spotterMinSpeedMs": 10.0,
        "spotterRaceStartDelayS": 20.0,
        "swearyMessages": True,
        "brakingZonesMute": False,
    }
    eng.apply_runtime_config(cfg)
    eng.sweary_messages = bool(cfg["swearyMessages"])
    spotter.apply_runtime_config(cfg)
    assert eng.personality.profile_id == "formal"
    assert eng.verbosity.level.value == "silent"
    assert spotter._gap_frequency_s == 60.0
    assert spotter._car_length_m == 4.5
    assert spotter._proximity_state.hold_repeat_s == 3.0
    assert spotter._min_speed_ms == 10.0
