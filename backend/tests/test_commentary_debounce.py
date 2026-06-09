"""Tests debounce real del CommentaryOrchestrator (sin flush manual)."""

from __future__ import annotations

import asyncio

import pytest

from src.intelligence.commentary_orchestrator import CommentaryOrchestrator
from src.models.messages import CommentaryEndMessage


@pytest.mark.asyncio
async def test_max_wait_forces_flush_under_continuous_enqueue():
    sent = []

    orch = CommentaryOrchestrator(
        broadcast_callback=sent.append,
        debounce_s=3.0,
        max_wait_s=0.08,
        llm_complete=None,
    )
    for _ in range(5):
        orch.enqueue("tyre_monitor", "Desgaste alto.", priority="MEDIUM")
        await asyncio.sleep(0.02)
    await asyncio.sleep(0.15)
    assert len(sent) >= 1
    assert all(isinstance(m, CommentaryEndMessage) for m in sent)


@pytest.mark.asyncio
async def test_enqueue_dedups_same_event_id():
    orch = CommentaryOrchestrator(debounce_s=0.01, max_wait_s=0.05)
    orch.enqueue("fuel", "Primera")
    orch.enqueue("fuel", "Segunda")
    assert orch.pending_count() == 1
    msg = await orch.flush()
    assert msg is not None
    assert msg.full_text == "Segunda"


@pytest.mark.asyncio
async def test_debounce_schedules_automatic_flush():
    sent = []
    orch = CommentaryOrchestrator(
        broadcast_callback=sent.append,
        debounce_s=0.05,
        max_wait_s=0.2,
    )
    orch.enqueue("race_start", "¡Salida!")
    await asyncio.sleep(0.12)
    assert len(sent) == 1
