"""
Tests unitarios para el endpoint /health.

Verifica:
- GET /health devuelve 200.
- La respuesta contiene shared_memory, lmu_api, llm.
- La respuesta contiene el campo websocket (opcional).
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


@pytest.fixture
def app():
    """App FastAPI con estado simulado para el endpoint /health."""
    from fastapi import FastAPI
    from src.routers.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)

    # Simular telemetry_reader
    mock_reader = MagicMock()
    mock_reader.offline = True
    mock_state = MagicMock()
    mock_state.player.current_lap = 3
    mock_reader.get_state.return_value = mock_state
    app.state.telemetry_reader = mock_reader

    app.state.strategy_service = MagicMock()
    return app


class TestHealthEndpoint:
    """Pruebas del endpoint /health."""

    def test_health_returns_200(self, app):
        """GET /health debe devolver 200."""
        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200

    def test_health_contains_status(self, app):
        """La respuesta debe contener el campo 'status'."""
        with TestClient(app) as client:
            data = client.get("/health").json()
            assert "status" in data
            assert data["status"] == "ok"

    def test_health_contains_shared_memory(self, app):
        """La respuesta debe contener shared_memory con status y offline_mode."""
        with TestClient(app) as client:
            data = client.get("/health").json()
            assert "shared_memory" in data
            sm = data["shared_memory"]
            assert "status" in sm
            assert "offline_mode" in sm
            assert "last_lap" in sm
            assert sm["last_lap"] == 3

    def test_health_contains_lmu_api(self, app):
        """La respuesta debe contener lmu_api con status y cache."""
        with TestClient(app) as client:
            data = client.get("/health").json()
            assert "lmu_api" in data
            assert "status" in data["lmu_api"]
            assert "cache" in data["lmu_api"]

    def test_health_contains_llm(self, app):
        """La respuesta debe contener llm con configured y model."""
        with TestClient(app) as client:
            data = client.get("/health").json()
            assert "llm" in data
            assert "configured" in data["llm"]
            assert "model" in data["llm"]

    def test_health_response_structure(self, app):
        """Verifica la estructura completa de la respuesta."""
        with TestClient(app) as client:
            data = client.get("/health").json()
            # Debe tener estos 4 campos raíz
            expected_keys = {"status", "shared_memory", "lmu_api", "llm"}
            assert expected_keys.issubset(data.keys())
