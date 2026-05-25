"""
Tests unitarios para el VLLMClient (CrofAI via OpenAI SDK).

Verifica:
- health_check() con API key simulada.
- health_check() sin API key retorna False.
- ask_streaming() con mock del SDK envía advice_start/advice_token/advice_end.
- ask_streaming() maneja errores correctamente.
"""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from src.intelligence.llm_client import VLLMClient
from src.models.messages import AdviceStartMessage, AdviceTokenMessage, AdviceEndMessage


class TestVLLMClientHealthCheck:
    """Pruebas del método health_check."""

    @pytest.mark.asyncio
    async def test_health_check_returns_true_when_configured(self):
        """health_check() debe retornar True cuando la API responde."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        mock_client = MagicMock()
        mock_models = MagicMock()
        mock_model = MagicMock()
        mock_model.id = "deepseek-v4-flash"
        mock_models.data = [mock_model]
        mock_client.models.list = AsyncMock(return_value=mock_models)

        with patch.object(client, '_get_client', return_value=mock_client):
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_returns_false_without_api_key(self):
        """health_check() debe retornar False sin API key."""
        client = VLLMClient(api_key="", base_url="https://test.api/v1")
        result = await client.health_check()
        assert result is False


class TestVLLMClientAskStreaming:
    """Pruebas del método ask_streaming."""

    @pytest.mark.asyncio
    async def test_ask_streaming_sends_tokens_and_end(self):
        """ask_streaming debe enviar advice_start, tokens y advice_end."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            # Mock del streaming response
            mock_chunk_1 = MagicMock()
            mock_chunk_1.choices = [MagicMock()]
            mock_chunk_1.choices[0].delta.content = "Hola "
            mock_chunk_1.choices[0].delta.tool_calls = None
            mock_chunk_1.choices[0].delta.reasoning_content = None

            mock_chunk_2 = MagicMock()
            mock_chunk_2.choices = [MagicMock()]
            mock_chunk_2.choices[0].delta.content = "piloto."
            mock_chunk_2.choices[0].delta.tool_calls = None
            mock_chunk_2.choices[0].delta.reasoning_content = None

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = [mock_chunk_1, mock_chunk_2].__iter__()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("test prompt", "FAST", "advice-123", None)

            # Verificar mensajes
            start_msgs = [m for m in broadcast_messages if isinstance(m, AdviceStartMessage)]
            token_msgs = [m for m in broadcast_messages if isinstance(m, AdviceTokenMessage)]
            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]

            assert len(start_msgs) == 1
            assert len(token_msgs) == 2
            assert len(end_msgs) == 1
            assert token_msgs[0].token == "Hola "
            assert token_msgs[1].token == "piloto."
            assert end_msgs[0].full_text == "Hola piloto."

    @pytest.mark.asyncio
    async def test_ask_streaming_sends_error_on_exception(self):
        """ask_streaming debe enviar mensaje de error si la API falla."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("test", "FAST", "advice-456", None)

            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]
            assert len(end_msgs) >= 1
            assert "Pérdida de comunicación" in end_msgs[-1].full_text