"""
Tests unitarios para el endpoint /history.

Verifica:
- GET /history devuelve 200.
- La respuesta es un array (puede estar vacío).
- Con datos en el store, devuelve los registros correctos.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


@pytest.fixture
def app():
    """App FastAPI con HistoryStore simulado."""
    from fastapi import FastAPI
    from src.routers.history import router as history_router

    app = FastAPI()
    app.include_router(history_router)

    # HistoryStore con datos simulados
    from src.persistence.history_store import HistoryStore
    store = HistoryStore(auto_load=False)
    store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)
    store.record_lap(lap=2, fuel_used=3.8, fuel_remaining=92.7, lap_time=121.0)
    app.state.history_store = store
    return app


@pytest.fixture
def app_empty():
    """App FastAPI con HistoryStore vacío."""
    from fastapi import FastAPI
    from src.routers.history import router as history_router

    app = FastAPI()
    app.include_router(history_router)

    from src.persistence.history_store import HistoryStore
    app.state.history_store = HistoryStore(auto_load=False)
    return app


@pytest.fixture
def app_no_store():
    """App FastAPI sin HistoryStore en app.state."""
    from fastapi import FastAPI
    from src.routers.history import router as history_router

    app = FastAPI()
    app.include_router(history_router)
    # No asignamos history_store
    return app


class TestHistoryEndpoint:
    """Pruebas del endpoint /history."""

    def test_history_returns_200(self, app):
        """GET /history debe devolver 200."""
        with TestClient(app) as client:
            response = client.get("/history")
            assert response.status_code == 200

    def test_history_returns_array(self, app):
        """La respuesta debe ser un array."""
        with TestClient(app) as client:
            data = client.get("/history").json()
            assert isinstance(data, list)

    def test_history_with_data(self, app):
        """Con datos, debe devolver los registros ordenados."""
        with TestClient(app) as client:
            data = client.get("/history").json()
            assert len(data) == 2
            assert data[0]["lap"] == 1
            assert data[0]["consumption"] == 3.5
            assert data[1]["lap"] == 2

    def test_history_empty_returns_empty_array(self, app_empty):
        """Sin datos, debe devolver array vacío."""
        with TestClient(app_empty) as client:
            data = client.get("/history").json()
            assert data == []

    def test_history_without_store_returns_empty(self, app_no_store):
        """Sin HistoryStore en app.state, debe devolver array vacío."""
        with TestClient(app_no_store) as client:
            data = client.get("/history").json()
            assert data == []

    def test_history_record_structure(self, app):
        """Cada registro debe tener los campos esperados."""
        with TestClient(app) as client:
            data = client.get("/history").json()
            record = data[0]
            expected_fields = {"lap", "consumption", "fuelRemaining", "lapTime"}
            assert expected_fields.issubset(record.keys())

    def test_history_returns_ordered_by_lap(self, app):
        """Los registros deben estar ordenados por lap."""
        with TestClient(app) as client:
            data = client.get("/history").json()
            laps = [r["lap"] for r in data]
            assert laps == sorted(laps)
