"""Tests para tool monitor_competitor en LLM client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared_strategy.models import CompetitorTrackerState, CompetitorPace
from src.intelligence.engine import IntelligenceEngine
from src.intelligence.llm_client import VLLMClient
from src.models.messages import AdviceEndMessage


class TestApplyMonitorCompetitor:
    def test_start_monitoring(self):
        engine = IntelligenceEngine(broadcaster=MagicMock(), llm_client=MagicMock())
        svc = MagicMock()
        svc.state.competitors = CompetitorTrackerState()
        engine.strategy_service = svc

        msg = engine.apply_monitor_competitor("start", 7)
        assert "Monitorizando rival 7" in msg
        assert 7 in svc.state.competitors.monitored

    def test_stop_monitoring(self):
        engine = IntelligenceEngine(broadcaster=MagicMock(), llm_client=MagicMock())
        svc = MagicMock()
        svc.state.competitors = CompetitorTrackerState(monitored=[7])
        engine.strategy_service = svc

        msg = engine.apply_monitor_competitor("stop", 7)
        assert "Dejé de monitorizar" in msg
        assert 7 not in svc.state.competitors.monitored


@pytest.mark.asyncio
async def test_llm_client_processes_monitor_competitor():
    engine = MagicMock()
    engine.get_competitors_list.return_value = [
        CompetitorPace(
            driver_index=1,
            driver_name="Rival",
            driver_class="GT3",
            standing_position=2,
            class_position=1,
            gap_to_player=1.0,
            best_lap=100.0,
            average_lap=101.0,
            estimated_stint_length=30,
            num_pit_stops=0,
            in_pits=False,
        )
    ]
    engine.apply_monitor_competitor.return_value = "Monitorizando rival 1."

    broadcast_messages = []

    with patch("src.intelligence.llm_client.send", side_effect=lambda m: broadcast_messages.append(m)):
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        mock_tool_chunk = MagicMock()
        mock_tool_chunk.choices = [MagicMock()]
        mock_tool_chunk.choices[0].delta.content = None
        mock_tool_chunk.choices[0].delta.reasoning_content = None

        mock_tool_call = MagicMock()
        mock_tool_call.function.name = "monitor_competitor"
        mock_tool_call.index = 0
        mock_tool_call.function.arguments = '{"action":"start","driver_index":1}'
        mock_tool_chunk.choices[0].delta.tool_calls = [mock_tool_call]

        mock_stream = AsyncMock()
        mock_stream.__aiter__.return_value = [mock_tool_chunk].__iter__()

        mock_client = MagicMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

        with patch.object(client, "_get_client", return_value=mock_client):
            await client.ask_streaming("test", "FAST", "adv-1", engine_ref=engine)

    engine.apply_monitor_competitor.assert_called_once_with("start", 1)
    end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]
    assert end_msgs
    assert "[MONITOR]" in end_msgs[-1].full_text
