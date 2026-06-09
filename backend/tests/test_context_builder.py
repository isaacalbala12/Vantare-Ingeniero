from src.intelligence.context_builder import build_prompt, _build_ticker_data
from src.intelligence import prompt_templates


def test_build_ticker_data_has_fields():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3, "gap_ahead": 2.1, "gap_behind": 1.5, "phase": "RACE"}
    data = _build_ticker_data(snapshot)
    assert "position" in data
    assert "lap" in data
    assert "fuel" in data
    assert "tyre_wear" in data  # lista [fl, fr, rl, rr]
    assert "brake_wear" in data  # lista [fl, fr, rl, rr]


def test_build_prompt_with_ticker():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3}
    telemetry = {"competitors": [], "session_type": "race", "session_time_left": 3600}
    result = build_prompt(snapshot, "test", None, prompt_templates, telemetry_frame=telemetry)
    assert "DRV:P" in result


def test_build_prompt_legacy():
    snapshot = {"lap": 5, "fuel_in_tank": 42.0, "place": 3}
    result = build_prompt(snapshot, "test", None, prompt_templates)
    # Modo legacy: usa SYSTEM_PROMPT_BASIC + no contiene ticker
    assert "Le Mans Ultimate" in result or "ingeniero" in result
    assert "DRV:P" not in result


import asyncio
import time
from unittest.mock import MagicMock

import pytest

from src.intelligence import prompt_templates
from src.intelligence.context_builder import prefetch_rag_context


@pytest.mark.asyncio
async def test_prefetch_rag_context_does_not_block_event_loop():
    store = MagicMock()

    def slow_query(frame, top_k=5):
        time.sleep(0.12)
        return [{"lap": 1, "type": "lap_completed", "text": "lap 1 done"}]

    store.query = slow_query
    snapshot = {"lap_number": 2, "fuel_in_tank": 50.0}

    tick_done = asyncio.Event()

    async def heartbeat():
        await asyncio.sleep(0.05)
        tick_done.set()

    heartbeat_task = asyncio.create_task(heartbeat())
    rag_task = asyncio.create_task(prefetch_rag_context(snapshot, store, top_k=1))

    await asyncio.wait_for(tick_done.wait(), timeout=0.1)
    result = await rag_task

    assert result is not None
    assert "RECORDATORIO HISTÓRICO" in result
    heartbeat_task.cancel()
