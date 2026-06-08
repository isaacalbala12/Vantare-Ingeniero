"""E2E PTT pipeline: pilot_question → llm_pending → advice_* (mocked LLM)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.llm_client import AskWithToolsResult
from src.models.messages import AdviceEndMessage, AdviceStartMessage, AdviceTokenMessage, LLMPendingMessage


def _engine_with_sent():
    sent = []
    llm = MagicMock()
    eng = IntelligenceEngine(broadcast_callback=sent.append, llm_client=llm)
    mock_svc = MagicMock()
    mock_svc.latest_frame = MagicMock(
        session_type="RACE",
        model_dump=lambda: {"session_type": "RACE", "lap_number": 5, "fuel_laps_remaining": 10.0},
    )
    mock_svc.latest_advice = MagicMock(model_dump=lambda: {"fuel": {"estimated_laps_remaining": 10.0}})
    mock_svc.get_race_summary.return_value = {}
    eng._strategy_service = mock_svc
    eng.strategy_service = mock_svc
    return eng, sent, llm


@pytest.mark.asyncio
async def test_open_question_emits_full_advice_sequence():
    eng, sent, llm = _engine_with_sent()
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    async def _stream(_messages, tier="FAST"):
        yield "Ritmo "
        yield "estable."

    llm.ask_streaming_messages = _stream
    llm._complete_speech_messages = AsyncMock(return_value="")

    await eng.handle_pilot_question("como va mi ritmo en pista")
    if eng._current_llm_task is not None:
        await eng._current_llm_task

    events = [getattr(m, "event", None) for m in sent]
    assert "llm_pending" in events
    assert "advice_start" in events
    assert "advice_token" in events
    ends = [m for m in sent if isinstance(m, AdviceEndMessage)]
    assert ends and ends[-1].full_text.strip()


@pytest.mark.asyncio
async def test_stream_empty_uses_complete_text_fallback():
    eng, sent, llm = _engine_with_sent()
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    async def _empty_stream(_messages, tier="FAST"):
        if False:
            yield ""

    llm.ask_streaming_messages = _empty_stream
    llm._complete_speech_messages = AsyncMock(return_value="Respuesta de respaldo del ingeniero.")

    await eng.handle_pilot_question("explicame la estrategia de boxes")
    if eng._current_llm_task is not None:
        await eng._current_llm_task

    ends = [m for m in sent if isinstance(m, AdviceEndMessage)]
    assert ends[-1].full_text == "Respuesta de respaldo del ingeniero."


@pytest.mark.asyncio
async def test_stream_and_complete_empty_use_hard_fallback():
    eng, sent, llm = _engine_with_sent()
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    async def _empty_stream(_messages, tier="FAST"):
        if False:
            yield ""

    llm.ask_streaming_messages = _empty_stream
    llm._complete_speech_messages = AsyncMock(return_value="")

    await eng.handle_pilot_question("como va mi ritmo")
    if eng._current_llm_task is not None:
        await eng._current_llm_task

    ends = [m for m in sent if isinstance(m, AdviceEndMessage)]
    assert "Repite la pregunta" in ends[-1].full_text


@pytest.mark.asyncio
async def test_fuel_fast_path_no_llm_pending():
    eng, sent, llm = _engine_with_sent()
    llm.ask_with_tools = AsyncMock()

    await eng.handle_pilot_question("cuantas vueltas de combustible me quedan")

    llm.ask_with_tools.assert_not_called()
    assert not any(isinstance(m, LLMPendingMessage) for m in sent)


@pytest.mark.asyncio
async def test_empty_question_is_ignored():
    eng, sent, llm = _engine_with_sent()
    llm.ask_with_tools = AsyncMock()

    await eng.handle_pilot_question(" ")
    await eng.handle_pilot_question("")

    llm.ask_with_tools.assert_not_called()
    assert sent == []


@pytest.mark.asyncio
async def test_barge_in_cancels_inflight_stream():
    eng, sent, llm = _engine_with_sent()
    llm.ask_with_tools = AsyncMock(return_value=AskWithToolsResult(content="", tool_calls=[]))

    async def _slow_stream(_messages, tier="FAST"):
        yield "parcial"
        import asyncio

        await asyncio.sleep(10)

    llm.ask_streaming_messages = _slow_stream

    await eng.handle_pilot_question("como va mi ritmo")
    task = eng._current_llm_task
    assert task is not None

    await eng.cancel_current_llm()
    assert task.done()

    async def _fast_stream(_messages, tier="FAST"):
        yield "Nueva respuesta."

    llm.ask_streaming_messages = _fast_stream
    await eng.handle_pilot_question("explicame la estrategia de boxes")
    if eng._current_llm_task is not None:
        await eng._current_llm_task

    ends = [m for m in sent if isinstance(m, AdviceEndMessage)]
    assert any("Nueva respuesta" in e.full_text for e in ends)
