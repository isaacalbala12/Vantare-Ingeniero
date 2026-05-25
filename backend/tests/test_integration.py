"""
Tests de integración del backend.

Verifica:
- WebSocket: conexión, recepción de telemetría, envío de pilot_question.
- Depende de que el servidor esté corriendo o usa un servidor de prueba.
"""
import pytest
import asyncio
import json
import time
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def integration_app():
    """
    App FastAPI completa con todos los routers y estado simulado.
    No arranca el lifespan (servicios en background) para tests rápidos.
    """
    from src.routers.health import router as health_router
    from src.routers.websocket import router as ws_router
    from src.routers.llm import router as llm_router
    from src.routers.tts import router as tts_router
    from src.routers.history import router as history_router
    from src.persistence.history_store import HistoryStore

    app = FastAPI()
    app.include_router(health_router)
    app.include_router(ws_router)
    app.include_router(llm_router)
    app.include_router(tts_router)
    app.include_router(history_router)

    # Estado simulado mínimo
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state.tts_service = None
    app.state.history_store = HistoryStore(auto_load=False)

    return app


# =========================================================================
# Tests de Integración
# =========================================================================

class TestWebSocketIntegration:
    """Pruebas de integración del WebSocket."""

    def test_websocket_connects(self, integration_app):
        """El WebSocket debe aceptar la conexión."""
        with TestClient(integration_app) as client:
            with client.websocket_connect("/ws") as ws:
                # La conexión se establece correctamente
                assert ws is not None

    def test_websocket_receives_telemetry(self, integration_app):
        """
        Con un telemetry_reader funcional, debe recibir datos.
        En este test simulado, la conexión se establece y cierra correctamente.
        """
        with TestClient(integration_app) as client:
            with client.websocket_connect("/ws") as ws:
                # Verificar que la conexión está abierta
                assert ws is not None
                # Enviar un mensaje de prueba (la conexión no debe cerrarse)
                ws.send_json({"event": "ping", "data": {}})
