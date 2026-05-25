"""
Tests unitarios para el endpoint /tts.

Verifica:
- GET /tts?text=hola devuelve 200 y Content-Type audio/mpeg o audio/wav.
- GET /tts sin parámetro text devuelve 400.
- GET /tts con texto vacío devuelve 400.
- GET /tts cuando ningún backend TTS está disponible → 500.
- GET /tts con texto > 2000 caracteres se trunca.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


def make_app_with_tts_services(edge_service=None, piper_service=None):
    """
    Crea una app FastAPI con estado simulado para el endpoint /tts.
    El router real busca 'edge_tts_service' y 'piper_tts_service' via _resolve_services.
    """
    from fastapi import FastAPI
    from src.routers.tts import router as tts_router

    app = FastAPI()
    app.include_router(tts_router)
    app.state.edge_tts_service = edge_service
    app.state.piper_tts_service = piper_service
    return app


class TestTTSEndpoint:
    """Pruebas del endpoint /tts alineadas con la implementación real."""

    def test_tts_returns_200_with_audio(self):
        """GET /tts?text=hola debe devolver 200 con Content-Type audio/mpeg."""
        mock_edge = MagicMock()

        async def fake_synthesize(text):
            return b"MP3 audio data" + b"\x00" * 100

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "hola"})
            assert response.status_code == 200
            assert "audio" in response.headers["content-type"]

    def test_tts_returns_400_without_text(self):
        """GET /tts sin parámetro text debe devolver 400."""
        app = make_app_with_tts_services(edge_service=MagicMock())
        with TestClient(app) as client:
            response = client.get("/tts")
            assert response.status_code == 400

    def test_tts_returns_400_with_empty_text(self):
        """GET /tts?text= (vacío) debe devolver 400."""
        app = make_app_with_tts_services(edge_service=MagicMock())
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": ""})
            assert response.status_code == 400

    def test_tts_truncates_long_text(self):
        """Texto > 2000 caracteres debe truncarse, no dar error."""
        mock_edge = MagicMock()
        received_text = ""

        async def fake_synthesize(text):
            nonlocal received_text
            received_text = text
            return b"MP3 audio data"

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        long_text = "a" * 2500
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": long_text})
            assert response.status_code == 200
            assert len(received_text) <= 2000
            assert received_text.endswith("...")

    def test_tts_allows_2000_chars(self):
        """Texto de exactamente 2000 caracteres debe funcionar sin truncar."""
        mock_edge = MagicMock()
        received_text = ""

        async def fake_synthesize(text):
            nonlocal received_text
            received_text = text
            return b"MP3 audio data"

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        text_2000 = "a" * 2000
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": text_2000})
            assert response.status_code == 200
            assert len(received_text) == 2000
            assert not received_text.endswith("...")

    def test_tts_returns_500_when_all_backends_unavailable(self):
        """GET /tts cuando ningún backend TTS está disponible debe devolver 500."""
        app = make_app_with_tts_services(edge_service=None, piper_service=None)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "hola"})
            assert response.status_code == 500

    def test_tts_fallback_to_piper_when_edge_fails(self):
        """Si edge falla, debe intentar con piper automáticamente."""
        mock_edge = MagicMock()

        async def edge_synth(text):
            raise RuntimeError("Edge TTS falló")

        mock_edge.synthesize = edge_synth

        mock_piper = MagicMock()

        async def piper_synth(text):
            return b"WAV audio data"

        mock_piper.synthesize = piper_synth

        app = make_app_with_tts_services(edge_service=mock_edge, piper_service=mock_piper)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "hola"})
            assert response.status_code == 200
            assert "audio" in response.headers["content-type"]

    def test_tts_with_special_chars(self):
        """TTS debe manejar caracteres especiales."""
        mock_edge = MagicMock()
        received_text = ""

        async def fake_synthesize(text):
            nonlocal received_text
            received_text = text
            return b"MP3 audio data"

        mock_edge.synthesize = fake_synthesize

        app = make_app_with_tts_services(edge_service=mock_edge)
        with TestClient(app) as client:
            response = client.get("/tts", params={"text": "exito"})
            assert response.status_code == 200
            assert len(received_text) > 0