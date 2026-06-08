"""Tests apply_runtime_config en IntelligenceEngine."""

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.spotter import SpotterService
from src.models.messages import ConfigAckMessage


def test_apply_runtime_config_updates_personality_and_verbosity():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng.apply_runtime_config({
        "personalityProfileId": "aggressive",
        "verbosityLevel": "detailed",
    })
    assert eng.personality.profile_id == "aggressive"
    assert eng.verbosity.level.value == "detailed"


def test_apply_runtime_config_ignores_unknown_keys():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    before = eng.personality.profile_id
    eng.apply_runtime_config({"unknownKey": True})
    assert eng.personality.profile_id == before
    assert not any(isinstance(m, ConfigAckMessage) for m in sent)


def test_apply_runtime_config_braking_zones_mute():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng.apply_runtime_config({"brakingZonesMute": True})
    assert eng.verbosity.should_mute_for_braking(0.2) is True


def test_runtime_config_snapshot_includes_spotter():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    spotter = SpotterService(broadcast_callback=lambda m: None)
    spotter.apply_runtime_config({"spotterCarLengthM": 5.1, "spotterGapFrequencyS": 42.0})
    eng.set_spotter_service(spotter)
    snap = eng.runtime_config_snapshot()
    assert snap["spotterCarLengthM"] == 5.1
    assert snap["spotterGapFrequencyS"] == 42.0


def test_runtime_config_snapshot_and_ack_via_broadcast():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({"verbosityLevel": "silent", "brakingZonesMute": True})
    eng.broadcast_config_ack()
    snap = eng.runtime_config_snapshot()
    assert snap["verbosityLevel"] == "silent"
    assert snap["brakingZonesMute"] is True
    assert any(isinstance(m, ConfigAckMessage) for m in sent)


def test_apply_runtime_config_speak_only_when_spoken_to():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng.apply_runtime_config({"speakOnlyWhenSpokenTo": True})
    assert eng.verbosity.speak_only_when_spoken_to is True
    snap = eng.runtime_config_snapshot()
    assert snap["speakOnlyWhenSpokenTo"] is True
