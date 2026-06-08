"""Tests PTT tool-first agent (Task 13A)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.llm_client import AskWithToolsResult, ParsedToolCall
from src.models.messages import AlertMessage, LLMPendingMessage


def _engine_with_mock_llm():
    sent = []
    llm = MagicMock()
    eng = IntelligenceEngine(broadcast_callback=sent.append, llm_client=llm)
    return eng, sent, llm


@pytest.mark.asyncio
async def test_ptt_speak_only_via_tool():
    eng, sent, llm = _engine_with_mock_llm()
    llm.ask_with_tools = AsyncMock(
        return_value=AskWithToolsResult(
            tool_calls=[ParsedToolCall(name="set_speak_only", arguments={"enabled": True})],
        )
    )

    await eng.handle_pilot_question("cállate un rato")

    assert eng.verbosity.speak_only_when_spoken_to is True
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert any("solo hablaré" in a.message.lower() for a in alerts)
    assert not any(isinstance(m, LLMPendingMessage) for m in sent)


@pytest.mark.asyncio
async def test_ptt_fuel_via_tool():
    eng, sent, llm = _engine_with_mock_llm()
    llm.ask_with_tools = AsyncMock(
        return_value=AskWithToolsResult(
            tool_calls=[ParsedToolCall(name="get_fuel_status", arguments={})],
        )
    )
    mock_svc = MagicMock()
    mock_svc.latest_frame = MagicMock(model_dump=lambda: {"fuel_laps_remaining": 6.5})
    mock_svc.latest_advice = MagicMock()
    eng._strategy_service = mock_svc
    eng.strategy_service = mock_svc

    await eng.handle_pilot_question("¿cuánto combustible me queda?")

    alerts = [m for m in sent if isinstance(m, AlertMessage) and m.category == "voice_response"]
    assert any("6.5" in a.message for a in alerts)
    assert not any(isinstance(m, LLMPendingMessage) for m in sent)


@pytest.mark.asyncio
async def test_ptt_open_question_skips_tool_turn():
    eng, sent, llm = _engine_with_mock_llm()
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    async def _fake_stream(_messages, tier="FAST"):
        yield "Ritmo estable, aguanta el stint."

    llm.ask_streaming_messages = _fake_stream
    llm._complete_speech_messages = AsyncMock(return_value="")

    mock_svc = MagicMock()
    mock_svc.latest_frame = MagicMock(
        session_type="RACE",
        model_dump=lambda: {"session_type": "RACE", "lap_number": 5},
    )
    mock_svc.latest_advice = MagicMock(model_dump=lambda: {"fuel": {"estimated_laps_remaining": 10.0}})
    mock_svc.get_race_summary.return_value = {}
    eng._strategy_service = mock_svc
    eng.strategy_service = mock_svc

    await eng.handle_pilot_question("¿cómo va mi ritmo en general?")
    if eng._current_llm_task is not None:
        await eng._current_llm_task

    llm.ask_with_tools.assert_not_called()
    pending = [m for m in sent if isinstance(m, LLMPendingMessage)]
    assert pending, "pregunta abierta debe emitir llm_pending"
    from src.models.messages import AdviceEndMessage

    ends = [m for m in sent if isinstance(m, AdviceEndMessage)]
    assert ends and ends[-1].full_text


@pytest.mark.asyncio
async def test_ptt_circuit_breaker_speak_only_when_llm_empty():
    eng, sent, llm = _engine_with_mock_llm()
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    await eng.handle_pilot_question("cállate hasta que te pregunte")

    assert eng.verbosity.speak_only_when_spoken_to is True
    alerts = [m for m in sent if isinstance(m, AlertMessage)]
    assert any("solo hablaré" in a.message.lower() for a in alerts)


@pytest.mark.asyncio
async def test_pilot_tool_executor_gap():
    from src.intelligence.pilot_tool_executor import PilotToolExecutor

    eng, sent, _ = _engine_with_mock_llm()
    mock_svc = MagicMock()
    mock_svc.latest_frame = MagicMock(
        model_dump=lambda: {"time_gap_car_ahead": 2.3, "time_gap_car_behind": 1.1}
    )
    eng._strategy_service = mock_svc
    eng.strategy_service = mock_svc

    result = await PilotToolExecutor().run(eng, "get_gap_status", {})
    assert result.ok is True
    assert "2.3" in (result.spoken_message or "")


@pytest.mark.asyncio
async def test_ptt_spotter_via_tool():
    from src.intelligence.spotter import SpotterService

    eng, sent, llm = _engine_with_mock_llm()
    spotter = SpotterService(broadcast_callback=sent.append)
    eng.set_spotter_service(spotter)
    llm.ask_with_tools = AsyncMock(
        return_value=AskWithToolsResult(
            tool_calls=[ParsedToolCall(name="spotter_toggle", arguments={"enabled": False})],
        )
    )

    await eng.handle_pilot_question("don't spot")

    assert spotter.enabled is False
    spotter_alerts = [
        m for m in sent if isinstance(m, AlertMessage) and m.category == "spotter"
    ]
    assert spotter_alerts


@pytest.mark.asyncio
async def test_ptt_mixed_intent_turn_two_summary():
    eng, sent, llm = _engine_with_mock_llm()
    mock_svc = MagicMock()
    mock_svc.latest_frame = MagicMock(
        model_dump=lambda: {"time_gap_car_ahead": 1.5, "session_type": "RACE"}
    )
    mock_svc.latest_advice = MagicMock()
    eng.strategy_service = mock_svc

    llm.ask_with_tools = AsyncMock(
        return_value=AskWithToolsResult(
            tool_calls=[
                ParsedToolCall(name="set_speak_only", arguments={"enabled": True}),
                ParsedToolCall(name="get_gap_status", arguments={}),
            ],
        )
    )
    llm.complete_from_messages = AsyncMock(
        return_value="Entendido, me callo. Gap delante 1.5 segundos."
    )

    await eng.handle_pilot_question("cállate y dime el gap")

    assert eng.verbosity.speak_only_when_spoken_to is True
    voice = [m for m in sent if isinstance(m, AlertMessage) and m.category == "voice_response"]
    assert any("callo" in a.message.lower() or "gap" in a.message.lower() for a in voice)
    llm.complete_from_messages.assert_awaited_once()
    assert not any(isinstance(m, LLMPendingMessage) for m in sent)


@pytest.mark.asyncio
async def test_ptt_spotter_circuit_breaker():
    from src.intelligence.spotter import SpotterService

    eng, sent, llm = _engine_with_mock_llm()
    spotter = SpotterService(broadcast_callback=sent.append)
    eng.set_spotter_service(spotter)
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    await eng.handle_pilot_question("spot")

    assert spotter.enabled is True
