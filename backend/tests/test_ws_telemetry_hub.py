from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.race.telemetry_hub import TelemetryHub
from src.routers.websocket import router as ws_router


def test_telemetry_sender_reads_hub_not_cc_on_frame():
    app = FastAPI()
    app.include_router(ws_router)
    hub = TelemetryHub()
    hub.update(snapshot={"lap": 7, "speed_ms": 60}, advice=None)
    app.state.telemetry_hub = hub
    app.state.telemetry_reader = MagicMock()
    app.state.strategy_service = None
    cc_loop = MagicMock()
    app.state.crewchief_loop = cc_loop

    with patch("src.routers.websocket.mp_encode", return_value=b"\x00\x01"):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            raw = ws.receive_bytes()
            assert raw == b"\x00\x01"
    cc_loop.on_frame.assert_not_called()
