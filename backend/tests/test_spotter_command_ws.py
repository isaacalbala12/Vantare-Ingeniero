"""Tests WebSocket spotter_command."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.routers.websocket import router as ws_router
from src.intelligence.spotter import SpotterService


@pytest.fixture
def spotter_ws_app():
    app = FastAPI()
    app.include_router(ws_router)
    spotter = SpotterService()
    app.state.spotter_service = spotter
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.intelligence_engine = None
    app.state.latest_client_frame = None
    app.state.latest_strategy_frame = None
    app.state._last_telemetry_t = 0.0
    return app, spotter


def test_spotter_command_disable(spotter_ws_app):
    app, spotter = spotter_ws_app
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "spotter_command", "data": {"action": "disable"}})
        msg = ws.receive_json()
        assert msg["event"] == "alert"
        assert spotter.enabled is False
        assert "desactivado" in msg["data"]["message"].lower()
