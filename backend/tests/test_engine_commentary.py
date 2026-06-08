"""Engine expone apply_set_verbosity y commentary API."""

import pytest

from src.intelligence.engine import IntelligenceEngine


@pytest.fixture
def engine():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    return eng, sent


def test_apply_set_verbosity(engine):
    eng, _ = engine
    msg = eng.apply_set_verbosity("silent")
    assert "silencioso" in msg.lower()
    assert eng.verbosity.level.value == "silent"


@pytest.mark.asyncio
async def test_enqueue_commentary_delegates(engine):
    eng, sent = engine
    eng.apply_engineer_toggle(True, emit_alert=False)
    eng.verbosity.set_enable_commentary_batch(True)
    ok = eng.enqueue_commentary("phase_changed", "Cambio de fase en pista.")
    assert ok is True
    msg = await eng.commentary.flush()
    assert msg is not None
    assert len(sent) >= 1
