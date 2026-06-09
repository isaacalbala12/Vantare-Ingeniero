"""Integration: evaluate_cycle — post Task 48 sin emisores legacy proactive."""

import asyncio

import pytest

from src.intelligence.engine import IntelligenceEngine
from src.models.messages import AlertMessage, CommentaryEndMessage


@pytest.mark.asyncio
async def test_evaluate_cycle_no_legacy_race_start_alert():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({"verbosityLevel": "normal"})
    await eng.evaluate_cycle(
        {"lap_number": 1, "standing_position": 5, "session_type": "RACE", "session_type_int": 10},
        {},
        {"phase": "RACE", "session_type_int": 10},
    )
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert not any("Salida" in a.message or "vamos" in a.message.lower() for a in alerts)


@pytest.mark.asyncio
async def test_evaluate_cycle_no_commentary_batch_by_default():
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({"verbosityLevel": "normal"})
    eng.commentary._debounce_s = 0.05
    eng.commentary._max_wait_s = 0.08
    eng.commentary._llm_complete = None
    await eng.evaluate_cycle(
        {"lap_number": 3, "standing_position": 5, "lap_time_previous": 90.0, "session_type": "RACE", "session_type_int": 10},
        {},
        {"phase": "RACE", "session_type_int": 10},
    )
    await asyncio.sleep(0.15)
    commentary = [m for m in sent if isinstance(m, CommentaryEndMessage)]
    assert commentary == []
