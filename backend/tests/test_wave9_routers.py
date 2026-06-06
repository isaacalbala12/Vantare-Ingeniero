"""Tests de routers Wave 9 (profiles, version, traces)."""

import tempfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.persistence.profile_store import ProfileStore
from src.persistence.trace_store import TraceStore
from src.routers.profiles import router as profiles_router
from src.routers.traces import router as traces_router
from src.routers.version import router as version_router


@pytest.fixture
def app(monkeypatch):
    profile_tmp = tempfile.mkdtemp()
    trace_tmp = tempfile.mkdtemp()
    monkeypatch.setattr("src.persistence.profile_store.PROFILES_DIR", profile_tmp)
    monkeypatch.setattr("src.persistence.trace_store.TRACES_DIR", trace_tmp)

    app = FastAPI()
    app.include_router(profiles_router)
    app.include_router(version_router)
    app.include_router(traces_router)
    app.state.profile_store = ProfileStore()
    app.state.trace_store = TraceStore()
    app.state.trace_playback_task = None
    app.state.trace_playback_active = False
    app.state.latest_client_frame = None
    return app


class TestWave9Routers:
    def test_version_endpoint(self, app):
        with TestClient(app) as client:
            res = client.get("/version")
            assert res.status_code == 200
            data = res.json()
            assert "version" in data

    def test_profile_crud(self, app):
        with TestClient(app) as client:
            cfg = {"serverPort": 8010, "vllmIP": "127.0.0.1"}
            assert client.put("/profiles/endurance", json={"config": cfg}).status_code == 200
            listed = client.get("/profiles").json()["profiles"]
            assert "endurance" in listed
            loaded = client.get("/profiles/endurance").json()["config"]
            assert loaded["serverPort"] == 8010
            assert client.delete("/profiles/endurance").status_code == 200

    def test_trace_record_flow(self, app):
        with TestClient(app) as client:
            start = client.post("/traces/start", json={"trace_id": "demo"})
            assert start.status_code == 200
            store: TraceStore = app.state.trace_store
            store.append_frame({"lap_number": 1})
            stop = client.post("/traces/stop")
            assert stop.json()["trace_id"] == "demo"
            traces = client.get("/traces").json()["traces"]
            assert any(t["id"] == "demo" for t in traces)
