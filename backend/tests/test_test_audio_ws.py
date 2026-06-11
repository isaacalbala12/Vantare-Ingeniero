import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.routers.websocket import router as ws_router
from src.voice.voice_queue import VoiceQueue


@pytest.mark.asyncio
async def test_test_audio_enqueues_play_command():
    app = FastAPI()
    app.include_router(ws_router)
    q = VoiceQueue()
    app.state.voice_queue = q
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.latest_client_frame = None
    app.state._last_telemetry_t = 0.0

    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "test_audio"})
        await asyncio.sleep(0.05)
    assert q.qsize() >= 1
