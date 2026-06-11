"""Tests contrato config_update payload (engine + spotter)."""

from src.config import settings
from src.intelligence.engine import IntelligenceEngine
from src.intelligence.spotter import SpotterService
from src.voice.tts_routing import TtsRouting


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
    # Frontend legacy puede enviar 10 m/s; runtime cap = min(cfg, SPOTTER_MIN_SPEED_MS).
    assert spotter._min_speed_ms == min(10.0, 5.0)


def test_config_ack_includes_tts_providers():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    routing = TtsRouting()
    eng.set_tts_routing(routing)
    eng.apply_runtime_config({
        "ttsProviderEngineer": "gemini",
        "ttsProviderSpotter": "edge",
    })
    assert routing.provider_engineer == "gemini"
    assert routing.provider_spotter == "edge"
    snap = eng.runtime_config_snapshot()
    assert snap["ttsProviderEngineer"] == "gemini"
    assert snap["ttsProviderSpotter"] == "edge"


def test_config_payload_includes_personality_v2_fields():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    cfg = {
        "personalityProfileId": "aggressive",
        "verbosityLevel": "silent",
        "swearyMessages": True,
        "proactivityLevel": "low",
        "pearlFrequency": 0.25,
    }
    eng.apply_runtime_config(cfg)
    snap = eng.runtime_config_snapshot()
    assert snap["personalityProfileId"] == "aggressive"
    assert snap["verbosityLevel"] == "silent"
    assert snap["swearyMessages"] is True
    assert snap["proactivityLevel"] == "low"
    assert snap["pearlFrequency"] == 0.25
    assert eng.personality.sweary_enabled is True
    assert eng.personality.proactivity == "low"
    assert eng.personality.pearl_frequency == 0.25


def test_config_update_cannot_enable_commentary_batch_when_beta_slim():
    """BETA_SLIM bloquea re-activación de commentary batch vía config WS."""
    assert settings.BETA_SLIM is True
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng.verbosity.set_enable_commentary_batch(False)
    eng.apply_runtime_config({"enableCommentaryBatch": True})
    assert eng.verbosity.enable_commentary_batch is False
