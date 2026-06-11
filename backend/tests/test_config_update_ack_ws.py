"""config_update debe emitir config_ack con estado real del backend."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.intelligence.engine import IntelligenceEngine
from src.intelligence.spotter import SpotterService
from src.routers.websocket import broadcast_sync, router as ws_router


@pytest.fixture
def config_ws_app():
    app = FastAPI()
    app.include_router(ws_router)
    engine = IntelligenceEngine(broadcast_callback=broadcast_sync)
    spotter = SpotterService(broadcast_callback=broadcast_sync, enabled=True)
    engine.set_spotter_service(spotter)
    app.state.intelligence_engine = engine
    app.state.spotter_service = spotter
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.latest_client_frame = None
    app.state._last_telemetry_t = 0.0
    return app, engine, spotter


def _wait_config_ack(ws, *, max_messages: int = 20) -> dict | None:
    for _ in range(max_messages):
        msg = ws.receive_json()
        if msg.get("event") == "config_ack":
            return msg
    return None


def test_config_update_emits_ack_with_spotter_enabled(config_ws_app):
    app, engine, spotter = config_ws_app
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "config_update", "data": {"spotterEnabled": False}})
        ack = _wait_config_ack(ws)
        assert ack is not None
        cfg = ack["data"]["config"]
        assert cfg["spotterEnabled"] is True
        assert spotter.enabled is True


def test_config_update_ack_reflects_engineer_toggle(config_ws_app):
    app, engine, spotter = config_ws_app
    engine.engineer_enabled = False
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "config_update", "data": {"engineerEnabled": True}})
        ack = _wait_config_ack(ws)
        assert ack is not None
        assert ack["data"]["config"]["engineerEnabled"] is True
        assert engine.engineer_enabled is True


def test_config_ack_includes_voice_backend_playback(config_ws_app):
    app, engine, _spotter = config_ws_app
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "config_update", "data": {"engineerEnabled": True}})
        ack = _wait_config_ack(ws)
        assert ack is not None
        cfg = ack["data"]["config"]
        assert "voiceBackendPlayback" in cfg
        assert isinstance(cfg["voiceBackendPlayback"], bool)
