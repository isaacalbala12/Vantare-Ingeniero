"""Tests avanzados para VLLMClient — flujos no cubiertos por test_llm_async.py.

Verifica:
- ask_streaming_text (generador HTTP para /ask endpoint)
- _get_client caching
- health_check con modelo no encontrado
- ask_streaming con reasoning_content
- ask_streaming con choices vacíos
- ask_streaming con tool_calls
- ask_streaming cancelado (CancelledError)
"""
import pytest
import json
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from src.intelligence.llm_client import VLLMClient
from src.models.messages import AdviceStartMessage, AdviceTokenMessage, AdviceEndMessage


class AsyncStreamContextManager:
    """Wrapper to make a mock response work as an async context manager."""

    def __init__(self, mock_response):
        self.mock_response = mock_response

    async def __aenter__(self):
        return self.mock_response

    async def __aexit__(self, *args):
        return None


def make_async_iter(items):
    """Create a mock async iterator that yields items.
    
    NOTE: __aiter__ must be MagicMock (not AsyncMock) because async for
    calls __aiter__() synchronously and expects an async iterator back.
    AsyncMock.__aiter__() returns a coroutine, breaking the protocol.
    """
    mock_iter = AsyncMock()
    mock_iter.__aiter__ = MagicMock(return_value=mock_iter)
    mock_iter.__anext__ = AsyncMock(side_effect=list(items) + [StopAsyncIteration()])
    return mock_iter


class TestVLLMClientGetClient:
    """Pruebas del método _get_client."""

    def test_get_client_creates_and_caches(self):
        """_get_client debe crear el cliente en primera llamada y cachearlo."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")
        assert client._client is None

        c1 = client._get_client()
        assert client._client is not None
        assert c1 is client._client

        c2 = client._get_client()
        assert c2 is c1  # Misma instancia cacheada

    def test_get_client_without_api_key(self):
        """_get_client debe funcionar incluso sin API key (el SDK lo maneja)."""
        client = VLLMClient(api_key="", base_url="https://test.api/v1")
        c = client._get_client()
        assert c is not None


class TestVLLMClientHealthCheckAdvanced:
    """Pruebas adicionales de health_check."""

    @pytest.mark.asyncio
    async def test_health_check_model_not_found_warning(self):
        """health_check debe retornar True aunque el modelo no esté en la lista."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1", model="unknown-model")

        mock_models = MagicMock()
        mock_model = MagicMock()
        mock_model.id = "other-model"
        mock_models.data = [mock_model]

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(return_value=mock_models)

        with patch.object(client, '_get_client', return_value=mock_client):
            result = await client.health_check()
            assert result is True  # True porque la API respondió

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """health_check debe retornar False si hay error de conexión."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        mock_client = MagicMock()
        mock_client.models.list = AsyncMock(side_effect=ConnectionError("Connection refused"))

        with patch.object(client, '_get_client', return_value=mock_client):
            result = await client.health_check()
            assert result is False


class TestVLLMClientAskStreamingAdvanced:
    """Pruebas adicionales de ask_streaming."""

    @pytest.mark.asyncio
    async def test_ask_streaming_reasoning_content(self):
        """ask_streaming debe procesar reasoning_content (modelos Qwen/vLLM)."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            mock_chunk = MagicMock()
            mock_chunk.choices = [MagicMock()]
            mock_chunk.choices[0].delta.content = None
            mock_chunk.choices[0].delta.reasoning_content = "Thinking step 1..."
            mock_chunk.choices[0].delta.tool_calls = None

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = [mock_chunk].__iter__()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("prompt", "FAST", "advice-reason", None)

            token_msgs = [m for m in broadcast_messages if isinstance(m, AdviceTokenMessage)]
            assert len(token_msgs) == 1
            assert token_msgs[0].token == "Thinking step 1..."

    @pytest.mark.asyncio
    async def test_ask_streaming_empty_choices_skipped(self):
        """ask_streaming debe saltar chunks sin choices."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            mock_chunk_empty = MagicMock()
            mock_chunk_empty.choices = []  # Sin choices

            mock_chunk_valid = MagicMock()
            mock_chunk_valid.choices = [MagicMock()]
            mock_chunk_valid.choices[0].delta.content = "valid"
            mock_chunk_valid.choices[0].delta.tool_calls = None
            mock_chunk_valid.choices[0].delta.reasoning_content = None

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = [mock_chunk_empty, mock_chunk_valid].__iter__()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("prompt", "FAST", "advice-empty", None)

            token_msgs = [m for m in broadcast_messages if isinstance(m, AdviceTokenMessage)]
            assert len(token_msgs) == 1
            assert token_msgs[0].token == "valid"

    @pytest.mark.asyncio
    async def test_ask_streaming_tool_calls(self):
        """ask_streaming debe procesar tool_calls para acciones UI."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            # Chunk con tool call
            mock_tool_chunk = MagicMock()
            mock_tool_chunk.choices = [MagicMock()]
            mock_tool_chunk.choices[0].delta.content = None
            mock_tool_chunk.choices[0].delta.reasoning_content = None

            mock_tool_call = MagicMock()
            mock_tool_call.function.name = "show_alert"
            mock_tool_call.index = 0
            mock_tool_call.function.arguments = '{"target": "fuel_panel", "action": "flash", "duration_ms": 2000}'
            mock_tool_chunk.choices[0].delta.tool_calls = [mock_tool_call]

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = [mock_tool_chunk].__iter__()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("prompt", "FAST", "advice-tool", None)

            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]
            assert len(end_msgs) >= 1
            assert len(end_msgs[-1].actions) >= 1
            assert end_msgs[-1].actions[0].action_type == "fuel_panel_flash"

    @pytest.mark.asyncio
    async def test_ask_streaming_bad_tool_call_args(self):
        """ask_streaming debe ignorar tool calls con argumentos inválidos sin fallar."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            mock_tool_chunk = MagicMock()
            mock_tool_chunk.choices = [MagicMock()]
            mock_tool_chunk.choices[0].delta.content = "response"
            mock_tool_chunk.choices[0].delta.reasoning_content = None

            mock_tool_call = MagicMock()
            mock_tool_call.function.name = "bad_action"
            mock_tool_call.index = 0
            mock_tool_call.function.arguments = "invalid json{{{"
            mock_tool_chunk.choices[0].delta.tool_calls = [mock_tool_call]

            mock_stream = AsyncMock()
            mock_stream.__aiter__.return_value = [mock_tool_chunk].__iter__()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                # No debe lanzar excepción
                await client.ask_streaming("prompt", "FAST", "advice-badtool", None)

            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]
            assert len(end_msgs) >= 1
            assert end_msgs[-1].full_text == "response"

    @pytest.mark.asyncio
    async def test_ask_streaming_cancelled(self):
        """ask_streaming debe manejar CancelledError y enviar mensaje de interrupción."""
        broadcast_messages = []
        def mock_broadcast(msg):
            broadcast_messages.append(msg)

        with patch("src.intelligence.llm_client.send", mock_broadcast):
            client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

            mock_stream = AsyncMock()
            mock_stream.__aiter__.side_effect = asyncio.CancelledError()

            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

            with patch.object(client, '_get_client', return_value=mock_client):
                await client.ask_streaming("prompt", "FAST", "advice-cancel", None)

            end_msgs = [m for m in broadcast_messages if isinstance(m, AdviceEndMessage)]
            assert len(end_msgs) >= 1
            assert "interrumpida" in end_msgs[-1].full_text


class TestVLLMClientAskStreamingText:
    """Pruebas del método ask_streaming_text (generador HTTP para /ask)."""

    def _make_mock_client(self, mock_response):
        """Crear un client MagicMock con el protocolo async context manager."""
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.stream = MagicMock(return_value=AsyncStreamContextManager(mock_response))
        return client

    def _make_sse_mock_response(self, sse_lines, status_code=200, raise_error=None):
        """Crear un mock_response que soporte aiter_lines como async iterator."""
        mock_resp = AsyncMock()
        mock_resp.status_code = status_code
        mock_resp.__aenter__.return_value = mock_resp
        mock_resp.raise_for_status = MagicMock(side_effect=raise_error)
        # aiter_lines debe ser MagicMock (no AsyncMock) porque async for no await
        mock_resp.aiter_lines = MagicMock(return_value=make_async_iter(sse_lines))
        return mock_resp

    @pytest.mark.asyncio
    async def test_ask_streaming_text_returns_tokens(self):
        """ask_streaming_text debe devolver tokens generados desde SSE."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"Hola "}}]}',
            'data: {"choices":[{"delta":{"content":"mundo"}}]}',
            'data: [DONE]',
        ]
        mock_response = self._make_sse_mock_response(sse_lines)
        mock_httpx_client = self._make_mock_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            tokens = []
            async for token in client.ask_streaming_text("test prompt"):
                tokens.append(token)

        assert tokens == ["Hola ", "mundo"]

    @pytest.mark.asyncio
    async def test_ask_streaming_text_skips_reasoning(self):
        """ask_streaming_text debe descartar reasoning_content."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        sse_lines = [
            'data: {"choices":[{"delta":{"reasoning_content":"thinking..."}}]}',
            'data: {"choices":[{"delta":{"content":"respuesta final"}}]}',
            'data: [DONE]',
        ]
        mock_response = self._make_sse_mock_response(sse_lines)
        mock_httpx_client = self._make_mock_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            tokens = []
            async for token in client.ask_streaming_text("test"):
                tokens.append(token)

        assert tokens == ["respuesta final"]

    @pytest.mark.asyncio
    async def test_ask_streaming_text_handles_error(self):
        """ask_streaming_text debe capturar errores HTTP y finalizar."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        mock_response = self._make_sse_mock_response([], status_code=500,
                                                      raise_error=Exception("HTTP 500"))
        mock_httpx_client = self._make_mock_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            tokens = []
            async for token in client.ask_streaming_text("test"):
                tokens.append(token)

        assert tokens == []  # Error capturado, sin tokens

    @pytest.mark.asyncio
    async def test_ask_streaming_text_bad_json_in_stream(self):
        """ask_streaming_text debe ignorar líneas con JSON inválido."""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        sse_lines = [
            'data: {invalid json!!!}',
            'data: {"choices":[{"delta":{"content":"ok"}}]}',
            'data: [DONE]',
        ]
        mock_response = self._make_sse_mock_response(sse_lines)
        mock_httpx_client = self._make_mock_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            tokens = []
            async for token in client.ask_streaming_text("test"):
                tokens.append(token)

        assert tokens == ["ok"]

    @pytest.mark.asyncio
    async def test_ask_streaming_text_skips_think_tags(self):
        """ask_streaming_text debe limpiar etiquetas <think>.</think>"""
        client = VLLMClient(api_key="test-key", base_url="https://test.api/v1")

        sse_lines = [
            'data: {"choices":[{"delta":{"content":"<think>"}}]}',
            'data: {"choices":[{"delta":{"content":"</think>"}}]}',
            'data: {"choices":[{"delta":{"content":"respuesta"}}]}',
            'data: [DONE]',
        ]
        mock_response = self._make_sse_mock_response(sse_lines)
        mock_httpx_client = self._make_mock_client(mock_response)

        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            tokens = []
            async for token in client.ask_streaming_text("test"):
                tokens.append(token)

        assert tokens == ["respuesta"]
