"""Stepfun PTT tool parsing and sanitizer guards."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.intelligence.llm_client import VLLMClient
from src.intelligence.llm_speech_sanitize import sanitize_llm_speech


def test_parse_stepfun_tool_xml_maps_fuel_alias():
    raw = (
        '<tool_call>\n<function=consultar_estado_combustible>\n'
        "<parameter=tipo_consulta>\nvueltas_restantes\n</parameter>\n"
        "</function>\n</tool_call>"
    )
    parsed = VLLMClient._parse_stepfun_tool_markup(raw)
    assert parsed is not None
    assert parsed.name == "get_fuel_status"


def test_sanitize_rejects_ticker_line():
    assert sanitize_llm_speech("DRV:P3|L5|F:42L") == ""


def test_sanitize_strips_tool_call_markup():
    raw = '<tool_call><function=get_fuel_status></function></tool_call>'
    assert sanitize_llm_speech(raw) == ""


def test_extract_message_speech_prefers_content():
    msg = MagicMock(content="Ritmo estable.", reasoning_content="El piloto pregunta por ritmo.")
    assert VLLMClient._extract_message_speech(msg) == "Ritmo estable."


def test_extract_message_speech_falls_back_to_reasoning():
    msg = MagicMock(content="", reasoning_content='Algo como "Ritmo estable en pista."')
    assert "Ritmo estable" in VLLMClient._extract_message_speech(msg)


def test_stepfun_extra_body_disables_thinking():
    client = VLLMClient(api_key="k", base_url="https://api.stepfun.ai/step_plan/v1")
    assert client._stepfun_extra_body() == {"thinking": {"type": "off"}}


def test_stepfun_extra_body_absent_for_other_providers():
    client = VLLMClient(api_key="k", base_url="https://api.openai.com/v1")
    assert client._stepfun_extra_body() is None


@pytest.mark.asyncio
async def test_ask_streaming_messages_reasoning_fallback():
    client = VLLMClient(api_key="k", base_url="https://api.stepfun.ai/step_plan/v1")

    mock_chunk = MagicMock()
    mock_chunk.choices = [MagicMock()]
    mock_chunk.choices[0].delta.content = None
    mock_chunk.choices[0].delta.reasoning_content = (
        'El piloto saluda. Respuesta radio: "Todo bien en boxes, concéntrate en pista."'
    )

    mock_stream = AsyncMock()
    mock_stream.__aiter__ = MagicMock(return_value=mock_stream)
    mock_stream.__anext__ = AsyncMock(side_effect=[mock_chunk, StopAsyncIteration()])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_stream)

    with patch.object(client, "_get_client", return_value=mock_client):
        tokens = [t async for t in client.ask_streaming_messages([{"role": "user", "content": "hola"}])]

    assert tokens
    assert "boxes" in "".join(tokens).lower() or "pista" in "".join(tokens).lower()
    create_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert create_kwargs.get("extra_body") == {"thinking": {"type": "off"}}


@pytest.mark.asyncio
async def test_complete_from_messages_uses_reasoning_when_content_empty():
    client = VLLMClient(api_key="k", base_url="https://api.stepfun.ai/step_plan/v1")

    mock_message = MagicMock(content="", reasoning_content="Te quedan 4 vueltas de combustible.")
    mock_choice = MagicMock(message=mock_message)
    mock_response = MagicMock(choices=[mock_choice])

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    with patch.object(client, "_get_client", return_value=mock_client):
        result = await client.complete_from_messages([{"role": "user", "content": "fuel?"}])

    assert "4 vueltas" in result
