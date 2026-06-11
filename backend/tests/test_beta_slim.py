from pathlib import Path

from src.config import settings


def test_beta_slim_defaults():
    assert settings.BETA_SLIM is True
    assert settings.ENABLE_CHROMA_RAG is False
    assert settings.ENABLE_MQTT is False
    assert settings.ENABLE_COMMENTARY_BATCH is False
    assert settings.WHISPER_PRELOAD.lower() == "off"


def test_main_lifespan_slim_gates_present():
    """Contrato: main.py debe saltar RAG/MQTT/Whisper cuando BETA_SLIM."""
    main_py = Path(__file__).resolve().parents[1] / "src" / "main.py"
    text = main_py.read_text(encoding="utf-8")
    assert "if settings.ENABLE_CHROMA_RAG and not settings.BETA_SLIM:" in text
    assert "EventStore skipped (BETA_SLIM or RAG disabled)" in text
    assert "if settings.MQTT_ENABLED and settings.ENABLE_MQTT and not settings.BETA_SLIM:" in text
    assert 'if settings.WHISPER_PRELOAD.lower() == "startup" and not settings.BETA_SLIM:' in text
    assert "if settings.BETA_SLIM or not settings.ENABLE_COMMENTARY_BATCH:" in text


def test_mqtt_disabled_under_beta_slim():
    from src.services.mqtt_service import MqttService

    svc = MqttService()
    assert svc.enabled is False


def test_main_slim_uses_commentary_batch_setter():
    main_py = Path(__file__).resolve().parents[1] / "src" / "main.py"
    text = main_py.read_text(encoding="utf-8")
    assert "set_enable_commentary_batch(False)" in text
    assert ".enable_commentary_batch = False" not in text
    from src.intelligence.engine import IntelligenceEngine

    engine = IntelligenceEngine(broadcast_callback=lambda _msg: None)
    engine.verbosity.set_enable_commentary_batch(False)
    engine.apply_runtime_config({"enableCommentaryBatch": True})
    assert engine.verbosity.enable_commentary_batch is False
