"""Tests para LMU REST dummy server."""

import pytest
from fastapi.testclient import TestClient

from src.debug.lmu_dummy_server import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


class TestLmuDummyServer:
    def test_weather_endpoint(self, client):
        res = client.get("/rest/sessions/weather")
        assert res.status_code == 200
        data = res.json()
        assert "RACE" in data
        assert "WNV_TEMPERATURE" in data["RACE"]["START"]

    def test_strategy_usage_endpoint(self, client):
        res = client.get("/rest/strategy/usage")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_garage_endpoint(self, client):
        res = client.get("/rest/garage/UIScreen/RepairAndRefuel")
        assert res.status_code == 200
        data = res.json()
        assert "wearables" in data
        assert "brakes" in data["wearables"]

    def test_health_endpoint(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["service"] == "lmu-dummy"
