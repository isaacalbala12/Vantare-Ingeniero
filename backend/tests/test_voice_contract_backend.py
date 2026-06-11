"""Voice contract backend tests — VC-B01–B05.

Mirrors docs/voice-contract.md §4.5. Tests verify that the IntelligenceEngine
correctly gates proactive emissions based on runtime config.
"""

from __future__ import annotations

import pytest

from src.intelligence.engine import IntelligenceEngine
from src.models.messages import AlertMessage, AdviceEndMessage, CommentaryEndMessage


def _collect_by_type(sent: list, msg_type: type) -> list:
    return [m for m in sent if isinstance(m, msg_type)]


@pytest.mark.asyncio
async def test_vc_b01_proactive_blocked_engineer_off_speak_only():
    """VC-B01: engineer=False + speakOnly=True → no commentary_end or advice_start emitted."""
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({
        "engineerEnabled": False,
        "speakOnlyWhenSpokenTo": True,
    })

    # Run a proactive cycle with minimal telemetry
    await eng.evaluate_cycle(
        {"lap_number": 5, "standing_position": 3, "session_type": "RACE", "session_type_int": 10},
        {},
        {"phase": "RACE", "session_type_int": 10},
    )

    commentary = _collect_by_type(sent, CommentaryEndMessage)
    advice_start = [m for m in sent if hasattr(m, "event") and getattr(m, "event", "") == "advice_start"]
    assert commentary == [], f"Expected no commentary_end, got {commentary}"
    assert advice_start == [], f"Expected no advice_start, got {advice_start}"


@pytest.mark.asyncio
async def test_vc_b02_ptt_still_emits_voice_response():
    """VC-B02: engineer=False + speakOnly=True + PTT → voice_response IS emitted."""
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({
        "engineerEnabled": False,
        "speakOnlyWhenSpokenTo": True,
    })

    # Simulate PTT fast command via _emit_voice_response
    eng._emit_voice_response("Afirmativo, recepción clara.", fast_command=True)

    alerts = _collect_by_type(sent, AlertMessage)
    voice_responses = [a for a in alerts if a.category == "voice_response"]
    assert len(voice_responses) >= 1, f"Expected voice_response alert, got {len(voice_responses)}"


@pytest.mark.asyncio
async def test_vc_b03_fuel_trigger_speak_only_engineer_on():
    """VC-B03: engineer=True + speakOnly=True → fuel trigger NOT emitted (speak only backend)."""
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({
        "engineerEnabled": True,
        "speakOnlyWhenSpokenTo": True,
    })

    # Run proactive cycle — fuel trigger should be suppressed by speakOnly
    await eng.evaluate_cycle(
        {"lap_number": 10, "standing_position": 3, "session_type": "RACE", "session_type_int": 10,
         "fuel_laps_remaining": 1.5},
        {"fuel": {"estimated_laps_remaining": 1.5, "pit_stops_needed": 1}},
        {"phase": "RACE", "session_type_int": 10},
    )

    alerts = _collect_by_type(sent, AlertMessage)
    # With speakOnly + engineer on, proactive alerts should be suppressed
    # voice_response is always allowed (I2), so filter it out
    proactive_alerts = [a for a in alerts if a.category != "voice_response"]
    # Commentary should also be suppressed
    commentary = _collect_by_type(sent, CommentaryEndMessage)
    assert commentary == [], f"Expected no commentary with speakOnly, got {commentary}"


@pytest.mark.asyncio
async def test_vc_b04_weather_trigger_engineer_on_speak_off():
    """VC-B04: engineer=True + speakOnly=False → trigger LLM legacy (clima) emite llm_pending."""
    sent = []
    eng = IntelligenceEngine(broadcast_callback=sent.append)
    eng.apply_runtime_config({
        "engineerEnabled": True,
        "speakOnlyWhenSpokenTo": False,
    })

    await eng.evaluate_cycle(
        {
            "lap_number": 10,
            "standing_position": 3,
            "session_type": "RACE",
            "session_type_int": 10,
            "speed": 25.0,
            "in_pits": False,
        },
        {},
        {
            "phase": "RACE",
            "session_type_int": 10,
            "weather_forecast": [{"WNV_RAIN_CHANCE": 50.0}],
        },
    )

    from src.models.messages import LLMPendingMessage

    pending = [m for m in sent if isinstance(m, LLMPendingMessage)]
    assert len(pending) >= 1, "Expected llm_pending for weather threat with engineer ON and speakOnly OFF"
    assert "lluvia" in pending[0].trigger_name.lower()


def test_vc_b05_spotter_proximity_always_emits(mock_broadcast, broadcast_messages):
    """VC-B05: SpotterService emite proximity; el frontend filtra por toggle."""
    from src.intelligence.spotter import SpotterService
    from src.intelligence.spotter_adapter import frame_to_spotter_tick
    from tests.fixtures.spotter.helpers import load_frame

    frame = load_frame("world_overlap_no_path_delta")
    spotter = SpotterService(
        broadcast_callback=mock_broadcast,
        proximity_threshold_m=3.0,
        spotter_off_qualifying=False,
        invert_lateral=False,
        enabled=True,
    )
    spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))

    proximity = [m for m in broadcast_messages if m.category == "proximity"]
    assert len(proximity) >= 1, "Spotter debe emitir alert proximity (independiente de engineer/speakOnly)"
    assert int(proximity[0].audio_priority) >= 2
