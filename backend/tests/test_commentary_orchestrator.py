"""Tests CommentaryOrchestrator y contrato commentary_end."""

from __future__ import annotations

import pytest

from src.intelligence.commentary_orchestrator import CommentaryOrchestrator
from src.intelligence.personality_pack import PersonalityPack
from src.intelligence.verbosity_controller import VerbosityController
from src.models.messages import CommentaryEndMessage


@pytest.mark.asyncio
async def test_flush_emits_commentary_end():
    sent = []

    orch = CommentaryOrchestrator(
        broadcast_callback=sent.append,
        verbosity=VerbosityController("normal"),
        personality=PersonalityPack("standard"),
        debounce_s=0.01,
    )
    assert orch.enqueue("position_change", "Subiste a P3.", priority="MEDIUM")
    msg = await orch.flush()
    assert msg is not None
    assert isinstance(msg, CommentaryEndMessage)
    assert msg.event == "commentary_end"
    assert msg.full_text == "Subiste a P3."
    assert msg.category == "commentary"
    assert "position_change" in msg.source_events
    assert len(sent) == 1
    assert sent[0].commentary_id == msg.commentary_id


@pytest.mark.asyncio
async def test_silent_verbosity_filters_low_priority():
    sent = []
    orch = CommentaryOrchestrator(
        broadcast_callback=sent.append,
        verbosity=VerbosityController("silent"),
        debounce_s=0.01,
    )
    assert orch.enqueue("gap_update", "Gap +1.2s", priority="LOW") is False
    msg = await orch.flush()
    assert msg is None
    assert sent == []


@pytest.mark.asyncio
async def test_batch_joins_multiple_summaries():
    sent = []
    orch = CommentaryOrchestrator(
        broadcast_callback=sent.append,
        verbosity=VerbosityController("detailed"),
        debounce_s=0.01,
        llm_complete=None,
    )
    orch.enqueue("lap_complete", "Vuelta 12 completada.")
    orch.enqueue("gap_update", "Gap adelante +0.8s.")
    msg = await orch.flush()
    assert msg is not None
    assert "Vuelta 12 completada." in msg.full_text
    assert "+0.8s." in msg.full_text
    assert len(msg.source_events) == 2


@pytest.mark.asyncio
async def test_flush_uses_llm_formatter_when_configured():
    sent = []

    async def fake_llm(prompt: str) -> str:
        return '{"speak": true, "text": "Mensaje radio LLM.", "priority": "NORMAL"}'

    orch = CommentaryOrchestrator(
        broadcast_callback=sent.append,
        llm_complete=fake_llm,
        debounce_s=0.01,
    )
    orch.enqueue("position_change", "Subiste a P3.")
    msg = await orch.flush()
    assert msg is not None
    assert msg.full_text == "Mensaje radio LLM."
