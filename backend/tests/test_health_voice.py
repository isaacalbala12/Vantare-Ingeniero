import time
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.race.telemetry_hub import TelemetryHub
from src.routers.health import router as health_router
from src.voice.voice_queue import VoiceQueue


@patch("src.routers.health.native_telemetry_enabled", return_value=False)
def test_health_includes_race_and_voice_sections(_mock_native):
    app = FastAPI()
    app.include_router(health_router)
    hub = TelemetryHub()
    hub.update(snapshot={"lap": 1}, advice=None)
    hub.record_tick_time(time.monotonic())
    app.state.telemetry_hub = hub
    app.state.voice_queue = VoiceQueue()
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.latest_client_frame = None
    app.state.spotter_service = None

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "race_loop" in body
    assert body["race_loop"]["tick_count"] >= 1
    assert "voice" in body
    assert "backend_playback" in body["voice"]
    assert "queue_size" in body["voice"]
    assert "player" in body["voice"]
