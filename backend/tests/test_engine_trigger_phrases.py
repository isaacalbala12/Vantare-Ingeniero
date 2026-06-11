"""Integración phrase_key → AlertMessage en IntelligenceEngine."""

from __future__ import annotations

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.triggers import FuelCriticalTrigger
from src.models.messages import AlertMessage


def test_deterministic_trigger_emits_phrase_alert():
    alerts: list[AlertMessage] = []

    def capture(msg):
        if isinstance(msg, AlertMessage):
            alerts.append(msg)

    eng = IntelligenceEngine(broadcast_callback=capture)
    eng.personality.set_profile("aggressive")
    trigger = FuelCriticalTrigger()
    eng._emit_trigger_alert(trigger)

    assert len(alerts) == 1
    text = alerts[0].message.lower()
    assert "atención:" not in text
    assert "boxes" in text or "vueltas" in text or "gasolina" in text


def test_runtime_config_snapshot_includes_tts_providers():
    from src.voice.tts_routing import TtsRouting

    eng = IntelligenceEngine(broadcast_callback=lambda m: None)
    routing = TtsRouting(provider_engineer="gemini", provider_spotter="edge")
    eng.set_tts_routing(routing)
    snap = eng.runtime_config_snapshot()
    assert snap["ttsProviderEngineer"] == "gemini"
    assert snap["ttsProviderSpotter"] == "edge"
