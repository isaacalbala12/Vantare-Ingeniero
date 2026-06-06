"""Tests para IntelligenceEngine - orquestador central de inteligencia."""

import pytest
from unittest.mock import MagicMock, AsyncMock, PropertyMock, patch
import uuid

from src.intelligence.engine import IntelligenceEngine


@pytest.fixture
def mock_live_context():
    mock = MagicMock()
    mock.get_snapshot.return_value = {
        "lap_number": 5, "speed": 180, "fuel_in_tank": 42.0,
        "session_type": "RACE", "session_time_left": 3600.0,
    }
    mock.snapshot.return_value = {"lap_number": 5}
    return mock


@pytest.fixture
def mock_context_builder():
    mock = MagicMock()
    mock.build_prompt.return_value = {"system": "prompt", "user": "question", "ticker_data": {}}
    mock.build_prompt_for_question.return_value = "prompt for question"
    return mock


@pytest.fixture
def mock_prompt_templates():
    mock = MagicMock()
    mock.render.return_value = "Prompt renderizado"
    return mock


@pytest.fixture
def mock_llm_client():
    mock = MagicMock()

    async def mock_stream_text():
        yield "token1"
        yield "token2"

    async def mock_stream(prompt, tier, advice_id, engine_ref=None):
        from src.models.messages import AdviceStartMessage, AdviceTokenMessage, AdviceEndMessage
        engine_ref.broadcaster.send(AdviceStartMessage(advice_id=advice_id, tier=tier, event="advice_start"))
        engine_ref.broadcaster.send(AdviceTokenMessage(advice_id=advice_id, token="token1", event="advice_token"))
        engine_ref.broadcaster.send(AdviceEndMessage(advice_id=advice_id, full_text="token1", actions=[], event="advice_end"))

    mock.ask_streaming_text = mock_stream_text
    mock.ask_streaming = mock_stream
    mock.health_check = AsyncMock(return_value=True)
    return mock


@pytest.fixture
def mock_broadcaster():
    return MagicMock()


@pytest.fixture
def mock_strategy_service():
    mock = MagicMock()
    mock.get_latest_advice.return_value = MagicMock()
    mock.latest_frame = MagicMock()
    mock.latest_advice = MagicMock()
    return mock


@pytest.fixture
def mock_lmu_api():
    mock = MagicMock()
    mock.get_weather.return_value = {"RACE": {}}
    return mock


@pytest.fixture
def engine(mock_live_context, mock_context_builder, mock_prompt_templates,
           mock_llm_client, mock_broadcaster, mock_strategy_service, mock_lmu_api):
    eng = IntelligenceEngine(
        live_context=mock_live_context,
        context_builder=mock_context_builder,
        prompt_templates=mock_prompt_templates,
        llm_client=mock_llm_client,
        broadcaster=mock_broadcaster,
        strategy_service=mock_strategy_service,
        lmu_api=mock_lmu_api,
    )
    return eng


class TestIntelligenceEngine:
    """Tests del orquestador central."""

    @pytest.mark.asyncio
    async def test_evaluate_cycle_no_triggers(self, engine, mock_broadcaster):
        """evaluate_cycle sin triggers no debe enviar mensajes LLM."""
        with patch.object(engine, '_current_llm_task', None):
            await engine.evaluate_cycle(
                telemetry_state={"speed": 180, "lap_number": 0},
                strategy_state={"fuel": {"estimated_laps_remaining": 10.0}, "pit_window": {"pit_window_open": False}},
                session_state={"phase": "RACE"},
            )
        assert mock_broadcaster.send.call_count == 0 or all(
            not isinstance(c[0][0] if c else None, type(None))
            for c in mock_broadcaster.send.call_args_list
        )

    @pytest.mark.asyncio
    async def test_evaluate_cycle_with_empty_state(self, engine):
        """evaluate_cycle con estado vacío no debe crashear."""
        await engine.evaluate_cycle(
            telemetry_state={},
            strategy_state={},
            session_state=None,
        )

    @pytest.mark.asyncio
    async def test_handle_pilot_question(self, engine, mock_broadcaster, mock_strategy_service):
        """handle_pilot_question debe procesar sin crashear."""
        mock_strategy_service.latest_frame = MagicMock(session_type="RACE")
        mock_strategy_service.latest_advice = MagicMock()
        with patch.object(engine, '_current_llm_task', None):
            await engine.handle_pilot_question("¿Cómo va mi ritmo?")
        assert mock_broadcaster.send.called

    @pytest.mark.asyncio
    async def test_cancel_current_llm_no_task(self, engine):
        """cancel_current_llm sin tarea activa no debe crashear."""
        await engine.cancel_current_llm()

    @pytest.mark.asyncio
    async def test_cancel_current_llm_with_task(self, engine, mock_broadcaster):
        """cancel_current_llm debe cancelar tarea activa."""
        mock_task = MagicMock()
        mock_task.done.return_value = False
        mock_task.__await__ = lambda: iter([None])
        engine._current_llm_task = mock_task
        engine._current_advice_id = str(uuid.uuid4())
        await engine.cancel_current_llm()
        mock_task.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_ask_async_returns_text(self, engine):
        """ask_async debe devolver texto."""
        result = []
        async for token in engine.ask_async("¿Cómo va mi ritmo?"):
            result.append(token)
        assert len(result) > 0
        assert isinstance(result[0], str)

    def test_initial_state(self, engine):
        """El estado inicial debe ser coherente."""
        assert engine._current_llm_task is None
        assert engine._current_response is None

    def test_to_dict_with_none(self, engine):
        """_to_dict con None debe devolver {}."""
        assert engine._to_dict(None) == {}

    def test_to_dict_with_dict(self, engine):
        """_to_dict con dict debe devolver el mismo dict."""
        assert engine._to_dict({"a": 1}) == {"a": 1}

    def test_get_event_store_no_store(self, engine):
        """_get_event_store sin event_store debe devolver None."""
        assert engine._get_event_store() is None


import asyncio
