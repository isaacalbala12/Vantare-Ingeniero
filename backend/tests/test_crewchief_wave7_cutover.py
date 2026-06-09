from src.intelligence.engine import IntelligenceEngine


def test_commentary_batch_disabled_by_default():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    snap = eng.runtime_config_snapshot()
    assert snap.get("enableCommentaryBatch") is False


def test_enqueue_commentary_blocked_when_batch_off():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng._eval_telemetry = {"session_type": "RACE", "session_type_int": 10}
    eng._eval_session = {"phase": "RACE", "session_type_int": 10}
    assert eng.enqueue_commentary("phase_changed", "Cambio de fase", "HIGH") is False


def test_enqueue_commentary_allows_legacy_when_batch_on():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng.verbosity.set_enable_commentary_batch(True)
    eng._eval_telemetry = {"session_type": "RACE", "session_type_int": 10}
    eng._eval_session = {"phase": "RACE", "session_type_int": 10}
    assert eng.enqueue_commentary("phase_changed", "Cambio de fase", "HIGH") is True


def test_enqueue_commentary_blocks_cc_owned_when_batch_on():
    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    eng.verbosity.set_enable_commentary_batch(True)
    eng._eval_telemetry = {"session_type": "RACE", "session_type_int": 10}
    eng._eval_session = {"phase": "RACE", "session_type_int": 10}
    assert eng.enqueue_commentary("fuel", "Combustible bajo", "HIGH") is False
