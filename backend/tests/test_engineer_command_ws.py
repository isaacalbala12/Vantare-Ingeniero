"""Tests WebSocket engineer_command."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routers.websocket import router as ws_router, broadcast_sync
from src.intelligence.engine import IntelligenceEngine


@pytest.fixture
def engineer_ws_app():
    app = FastAPI()
    app.include_router(ws_router)
    engine = IntelligenceEngine(broadcast_callback=broadcast_sync)
    app.state.intelligence_engine = engine
    app.state.spotter_service = None
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.latest_client_frame = None
    app.state._last_telemetry_t = 0.0
    return app, engine


def _wait_config_ack(ws, *, max_messages: int = 12) -> dict | None:
    for _ in range(max_messages):
        msg = ws.receive_json()
        if msg.get("event") == "config_ack":
            return msg
    return None


def test_engineer_command_disable(engineer_ws_app):
    app, engine = engineer_ws_app
    engine.engineer_enabled = True
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "engineer_command", "data": {"action": "disable"}})
        ack = _wait_config_ack(ws)
        assert ack is not None
        assert engine.engineer_enabled is False
        assert ack["data"]["config"]["engineerEnabled"] is False


def test_engineer_command_enable(engineer_ws_app):
    app, engine = engineer_ws_app
    engine.engineer_enabled = False
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "engineer_command", "data": {"action": "enable"}})
        ack = _wait_config_ack(ws)
        assert ack is not None
        assert engine.engineer_enabled is True
        assert ack["data"]["config"]["engineerEnabled"] is True
