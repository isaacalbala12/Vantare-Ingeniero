"""WS ingress PTT: pilot_question + barge_in."""

import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.intelligence.engine import IntelligenceEngine
from src.routers.health import router as health_router
from src.routers.websocket import router as ws_router


@pytest.fixture
def ptt_ws_app():
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(ws_router)

    sent = []
    llm = MagicMock()
    engine = IntelligenceEngine(broadcast_callback=sent.append, llm_client=llm)

    async def _stream(_messages, tier="FAST"):
        yield "Respuesta WS."

    llm.ask_streaming_messages = _stream
    llm._complete_speech_messages = AsyncMock(return_value="")
    llm.ask_with_tools = AsyncMock(
        return_value=__import__(
            "src.intelligence.llm_client", fromlist=["AskWithToolsResult"]
        ).AskWithToolsResult(content="", tool_calls=[])
    )

    mock_svc = MagicMock()
    mock_svc.latest_frame = MagicMock(
        model_dump=lambda: {"session_type": "RACE", "lap_number": 3},
    )
    mock_svc.latest_advice = MagicMock(model_dump=lambda: {})
    mock_svc.get_race_summary.return_value = {}
    engine._strategy_service = mock_svc
    engine.strategy_service = mock_svc

    app.state.telemetry_reader = None
    app.state.strategy_service = mock_svc
    app.state.intelligence_engine = engine
    app.state.spotter_service = None
    app.state.latest_client_frame = None
    app.state._last_telemetry_t = 0.0
    app.state.event_store = None
    app.state._ptt_sent = sent
    app.state._ptt_engine = engine

    return app


def test_pilot_question_ws_does_not_crash(ptt_ws_app):
    client = TestClient(ptt_ws_app)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(
            json.dumps(
                {"event": "pilot_question", "data": {"question": "como va mi ritmo en pista"}},
            ),
        )
        time.sleep(0.5)
        ws.send_text(json.dumps({"event": "pilot_ptt_barge_in", "data": {}}))
        time.sleep(0.2)


def test_pilot_question_empty_ignored(ptt_ws_app):
    client = TestClient(ptt_ws_app)
    sent = ptt_ws_app.state._ptt_sent
    before = len(sent)
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"event": "pilot_question", "data": {"question": " "}}))
        time.sleep(0.5)
    assert len(sent) == before
