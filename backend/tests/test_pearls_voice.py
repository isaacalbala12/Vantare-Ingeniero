"""Tests contrato de voz para perlas (audio_priority 2)."""

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.pearls_of_wisdom import PearlType
from src.models.messages import AlertMessage


def test_emit_pearl_uses_audio_priority_2():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.verbosity.set_level("normal")
    eng.sweary_messages = False
    eng.pearls.reset_race()
    eng._emit_pearl(PearlType.FAST_LAP)
    assert len(sent) == 1
    alert = sent[0]
    assert isinstance(alert, AlertMessage)
    assert alert.category == "pearl"
    assert alert.audio_priority == "2"


def test_silent_verbosity_blocks_pearls():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_set_verbosity("silent")
    eng._emit_pearl(PearlType.STANDARD)
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert alerts == []
