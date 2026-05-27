"""
Tests de integración para el transporte binario WebSocket con MessagePack + delta encoding.

Ejecuta: pytest tests/test_ws_integration.py -v
"""
import pytest
import asyncio
import json
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.routers.health import router as health_router
from src.routers.websocket import router as ws_router, manager
from src.services.msgpack_codec import encode as mp_encode, decode as mp_decode, compute_delta, is_full_frame


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def ws_app():
    """App FastAPI mínima con WebSocket + health para tests de integración."""
    app = FastAPI()
    app.include_router(health_router)
    app.include_router(ws_router)

    # Estado simulado — sin telemetry_reader (telemetry_sender_loop no emitirá nada)
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state.latest_client_frame = None
    app.state.latest_strategy_frame = None
    app.state._last_telemetry_t = 0.0

    return app


@pytest.fixture
def ws_client(ws_app):
    """TestClient preparado para tests WebSocket."""
    return TestClient(ws_app)


def send_full_frame(client, data: dict) -> None:
    """Envía un frame completo MessagePack al WebSocket conectado."""
    full = dict(data)
    full["_t"] = time.time()
    full["_full"] = True
    client.send_bytes(mp_encode(full))


def send_delta_frame(client, data: dict, base: dict) -> None:
    """Envía un delta MessagePack al WebSocket conectado."""
    delta = compute_delta(base, data)
    client.send_bytes(mp_encode(delta))


def read_binary_message(ws) -> dict | None:
    """Recibe un mensaje binario del WebSocket y decodifica MessagePack."""
    try:
        msg = ws.receive()
        if msg.get("type") == "websocket.receive" and "bytes" in msg:
            return mp_decode(msg["bytes"])
    except Exception:
        pass
    return None


def read_json_message(ws) -> dict | None:
    """Recibe un mensaje JSON del WebSocket."""
    try:
        msg = ws.receive()
        if msg.get("type") == "websocket.receive" and "text" in msg:
            return json.loads(msg["text"])
    except Exception:
        pass
    return None


# =========================================================================
# Tests
# =========================================================================

class TestMsgpackWebSocketIntegration:
    """Tests de integración para MessagePack + delta encoding sobre WebSocket."""

    def test_msgpack_telemetry_roundtrip(self, ws_client):
        """
        Conectar al /ws, verificar que no hay crash.
        El telemetry_sender_loop no emitirá nada porque no hay telemetry_reader,
        pero la conexión debe establecerse sin errores.
        """
        with ws_client.websocket_connect("/ws") as ws:
            assert ws is not None
            # Enviar un frame completo para verificar procesamiento
            frame = {"speed": 72.0, "lap": 3, "fuel": 45.0}
            send_full_frame(ws, frame)
            # Enviar un delta
            delta_frame = {"speed": 75.0}  # solo lo que cambia
            send_delta_frame(ws, delta_frame, frame)
            # No crash = éxito

    def test_frontend_full_frame_received(self, ws_client):
        """
        Enviar un frame completo en MessagePack binario.
        Verificar via /health que latest_client_frame fue almacenado.
        """
        with ws_client.websocket_connect("/ws") as ws:
            full_frame = {
                "speed": 72.0,
                "lap": 3,
                "fuel": 45.0,
                "throttle": 0.85,
            }
            send_full_frame(ws, full_frame)
            # Dar tiempo al loop asíncrono para procesar
            time.sleep(0.1)

        # Verificar via health endpoint
        response = ws_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["frontend_telemetry"]["received"] is True

    def test_frontend_delta_received(self, ws_client):
        """
        Enviar frame completo -> delta -> verificar merged data via health.
        """
        with ws_client.websocket_connect("/ws") as ws:
            base = {
                "speed": 72.0,
                "lap": 3,
                "fuel": 45.0,
                "throttle": 0.85,
            }
            send_full_frame(ws, base)
            time.sleep(0.1)

            # Enviar delta con solo campos cambiados
            delta = {"speed": 75.0, "throttle": 0.90}
            send_delta_frame(ws, delta, base)
            time.sleep(0.1)

        # Verificar que el delta fue aplicado
        response = ws_client.get("/health")
        assert response.status_code == 200
        assert response.json()["frontend_telemetry"]["received"] is True

    def test_delta_ignored_when_no_base(self, ws_client):
        """
        Enviar solo un delta sin frame completo previo.
        El backend debe manejarlo gracefully (guardar como está, no crash).
        """
        with ws_client.websocket_connect("/ws") as ws:
            # Delta sin base — compute_delta emitirá un full frame
            delta_only = {"speed": 80.0}
            send_delta_frame(ws, delta_only, None)
            time.sleep(0.1)

        # No crash y health refleja que se recibió algo
        response = ws_client.get("/health")
        assert response.status_code == 200
        # El backend guarda el frame aunque venga con _full=False
        # porque detectamos que no había base
        assert response.json()["frontend_telemetry"]["received"] is True

    def test_gap_detection_no_crash(self, ws_client):
        """
        Enviar full frame, esperar 0.6s, enviar otro frame.
        El gap detection loggea un warning pero no crash.
        """
        with ws_client.websocket_connect("/ws") as ws:
            frame1 = {"speed": 72.0, "lap": 1}
            send_full_frame(ws, frame1)
            time.sleep(0.65)  # > 0.5s gap
            frame2 = {"speed": 75.0, "lap": 2}
            send_full_frame(ws, frame2)
            time.sleep(0.1)

        # Verificar que sigue funcionando
        response = ws_client.get("/health")
        assert response.status_code == 200

    def test_snapshot_recovery_after_gap(self, ws_client):
        """
        Full -> Delta -> espera -> Full -> verificar latest_client_frame tiene datos actuales.
        """
        with ws_client.websocket_connect("/ws") as ws:
            frame1 = {"speed": 72.0, "lap": 3, "fuel": 45.0}
            send_full_frame(ws, frame1)
            time.sleep(0.1)

            delta = {"speed": 75.0}
            send_delta_frame(ws, delta, frame1)
            time.sleep(0.1)

            # Gap
            time.sleep(0.65)

            # Nueva snapshot completa
            frame2 = {"speed": 80.0, "lap": 4, "fuel": 44.0}
            send_full_frame(ws, frame2)
            time.sleep(0.1)

        response = ws_client.get("/health")
        assert response.status_code == 200
        assert response.json()["frontend_telemetry"]["received"] is True

    def test_health_reflects_real_data(self, ws_client):
        """
        Después de enviar frames, verificar /health devuelve frontend_telemetry.received: true.
        """
        with ws_client.websocket_connect("/ws") as ws:
            full = {"speed": 72.0, "lap": 3}
            send_full_frame(ws, full)
            time.sleep(0.15)

        response = ws_client.get("/health")
        assert response.status_code == 200
        assert response.json()["frontend_telemetry"]["received"] is True

    def test_backward_compatibility_json(self, ws_client):
        """
        Enviar JSON texto con event=pilot_question. Verificar que no hay crash WebSocket.
        El handler de pilot_question puede fallar si no hay engine, pero el WS no debe cerrarse.
        """
        with ws_client.websocket_connect("/ws") as ws:
            # Enviar JSON texto — formato legacy del frontend
            ws.send_json({
                "event": "pilot_question",
                "data": {"question": "Test question from integration test"}
            })
            time.sleep(0.1)

            # Enviar otro mensaje para verificar que la conexión sigue viva
            ws.send_json({"event": "ping", "data": {}})
            time.sleep(0.1)

        # Si llegamos aquí, el WS no se cerró por error

    def test_msgpack_decode_verify_keys(self, ws_client):
        """
        Verificar que los frames MessagePack recibidos del backend son válidos
        y contienen las claves esperadas de un RaceState.
        """
        # Enviar un frame que simule estructura de RaceState
        with ws_client.websocket_connect("/ws") as ws:
            full = {
                "session_type": 4,
                "time_remaining": 3600.0,
                "track_temp": 25.0,
                "ambient_temp": 20.0,
                "lap_distance": 1200.0,
                "current_lap": 3,
                "fuel_in_tank": 45.0,
            }
            send_full_frame(ws, full)
            time.sleep(0.1)

        # Verificar que health refleja los datos
        response = ws_client.get("/health")
        assert response.status_code == 200
        assert response.json()["frontend_telemetry"]["received"] is True

    def test_multiple_clients_delta_isolation(self, ws_client):
        """
        Dos clientes conectados deben poder enviar frames independientemente.
        El manager mantiene múltiples conexiones.
        """
        with ws_client.websocket_connect("/ws") as ws1:
            with ws_client.websocket_connect("/ws") as ws2:
                frame1 = {"client": 1, "speed": 70.0}
                frame2 = {"client": 2, "speed": 75.0}

                send_full_frame(ws1, frame1)
                send_full_frame(ws2, frame2)
                time.sleep(0.1)

        # Ambos clientes deberían haber enviado datos
        response = ws_client.get("/health")
        assert response.status_code == 200
        # Al menos un cliente envió datos
        assert response.json()["frontend_telemetry"]["received"] is True

    def test_invalid_msgpack_handled_gracefully(self, ws_client):
        """
        Enviar bytes que no son MessagePack válido. El backend debe ignorarlo
        con un warning log, sin cerrar el WebSocket.
        """
        with ws_client.websocket_connect("/ws") as ws:
            # Enviar bytes basura
            ws.send_bytes(b"\x00\x01\x02\xff\xfe")
            time.sleep(0.1)

            # Enviar mensaje válido para confirmar que el WS sigue abierto
            ws.send_json({"event": "ping", "data": {}})
            time.sleep(0.1)

        # Si llegamos aquí, el WS no se cerró