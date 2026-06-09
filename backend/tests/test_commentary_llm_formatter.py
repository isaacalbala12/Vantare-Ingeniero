"""Tests commentary_llm_formatter."""

import pytest

from src.intelligence.commentary_llm_formatter import (
    format_batch_deterministic,
    format_commentary_batch,
    parse_llm_commentary_response,
)


def test_parse_valid_json():
    raw = '{"speak": true, "text": "P3, gap +1.2. Buen ritmo.", "priority": "NORMAL"}'
    out = parse_llm_commentary_response(raw)
    assert out.speak is True
    assert "P3" in out.text


def test_parse_json_embedded_in_text():
    raw = 'Aquí va el JSON: {"speak": true, "text": "Gap estable.", "priority": "NORMAL"} fin'
    out = parse_llm_commentary_response(raw)
    assert out.text == "Gap estable."


def test_fallback_on_deterministic():
    events = [("position_change", "Subiste a P3.", "MEDIUM")]
    out = format_batch_deterministic(events, tone="directo")
    assert "Subiste a P3." in out


@pytest.mark.asyncio
async def test_format_commentary_batch_uses_llm_when_provided():
    async def fake_llm(prompt: str) -> str:
        return '{"speak": true, "text": "Radio unificada.", "priority": "NORMAL"}'

    text = await format_commentary_batch(
        events=[("lap_complete", "Vuelta 5.", "LOW"), ("gap_update", "Gap +1s.", "LOW")],
        personality_tone="estilo radio",
        llm_complete=fake_llm,
        timeout_s=2.0,
    )
    assert text == "Radio unificada."


@pytest.mark.asyncio
async def test_format_commentary_batch_fallback_on_llm_error():
    async def bad_llm(prompt: str) -> str:
        raise RuntimeError("offline")

    text = await format_commentary_batch(
        events=[("lap_complete", "Vuelta 5.", "LOW")],
        personality_tone="estilo radio",
        llm_complete=bad_llm,
    )
    assert "Vuelta 5." in text
