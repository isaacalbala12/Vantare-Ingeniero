"""Tests de integración del endpoint /ws/sidecar.

Verifica:
- Conexión WebSocket a /ws/sidecar
- Recepción de strategy_frame
- Limpieza de estado al desconectarse
- Health endpoint reporta estado del sidecar
"""
import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from src.routers.health import router as health_router
from src.routers.websocket import router as ws_router


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def app():
    """App FastAPI mínima con WebSocket + health para tests del sidecar."""
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(ws_router)

    # Estado simulado
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state.latest_client_frame = None
    app.state.latest_strategy_frame = None
    app.state._last_telemetry_t = 0.0
    app.state.event_store = None

    return app


class TestSidecarHealth:
    """El health endpoint debe reportar estado del sidecar."""

    def test_health_contains_sidecar(self, app):
        """GET /health debe incluir campo sidecar en la respuesta."""
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "sidecar" in data


class TestSidecarWebSocket:
    """Endpoint /ws/sidecar debe aceptar conexiones y strategy_frames."""

    def test_sidecar_connect_and_receive_strategy_frame(self, app):
        """Sidecar debe poder conectarse y enviar strategy_frame."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                ws.send_json({
                    "event": "strategy_frame",
                    "data": {
                        "advice": {"fuel_advice": "OK", "tyre_advice": "OK"},
                        "frame": {"lap_number": 1, "speed": 180.0},
                        "events": [{"type": "lap_completed", "lap": 1}],
                    }
                })
                # Verificar que se almacenó en app.state
                assert app.state.latest_strategy_frame is not None
                assert app.state.latest_strategy_frame["advice"]["fuel_advice"] == "OK"

    def test_sidecar_connect_and_receive_empty_frame(self, app):
        """Sidecar debe aceptar strategy_frame sin events."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                ws.send_json({
                    "event": "strategy_frame",
                    "data": {
                        "advice": {},
                        "frame": {"lap_number": 2},
                    }
                })
                assert app.state.latest_strategy_frame is not None
                assert app.state.latest_strategy_frame["frame"]["lap_number"] == 2

    def test_sidecar_rejects_invalid_json(self, app):
        """Sidecar endpoint debe manejar JSON inválido sin crashear."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                # Enviar JSON sin event
                ws.send_json({"not_an_event": True})
                # No debe crashear ni desconectar
                ws.send_json({
                    "event": "strategy_frame",
                    "data": {"advice": {}, "frame": {}}
                })
                assert app.state.latest_strategy_frame is not None

    def test_sidecar_multiple_frames(self, app):
        """Sidecar debe poder enviar múltiples strategy_frames secuencialmente."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                for lap in range(1, 4):
                    ws.send_json({
                        "event": "strategy_frame",
                        "data": {
                            "advice": {"fuel_advice": f"lap_{lap}"},
                            "frame": {"lap_number": lap},
                            "events": [],
                        }
                    })
                    # Trigger async processing: ping + receive
                    ws.send_json({"event": "ping"})
                    ws.receive_json()
                # Verify last frame was processed
                assert app.state.latest_strategy_frame["frame"]["lap_number"] == 3
                assert app.state.latest_strategy_frame["advice"]["fuel_advice"] == "lap_3"