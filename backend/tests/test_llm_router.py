"""Tests unitarios para el router /ask (routers/llm.py).

Verifica:
- POST /ask con IntelligenceEngine disponible devuelve respuesta
- POST /ask sin IntelligenceEngine devuelve 503
- POST /ask con chat_history se formatea correctamente
- POST /ask con respuesta vacía usa fallback
"""
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI


def make_app_with_engine(mock_engine=None):
    """Crea una app FastAPI con IntelligenceEngine mockeado (o None)."""
    from src.routers.llm import router as llm_router

    app = FastAPI()
    app.include_router(llm_router)
    app.state.intelligence_engine = mock_engine
    return app


class MockEngine:
    """Mock de IntelligenceEngine.ask_async que devuelve tokens."""
    def __init__(self, tokens: list[str] = None):
        self.tokens = tokens or ["respuesta ", "del ", "ingeniero"]

    async def ask_async(self, question: str, chat_history: list = None):
        for token in self.tokens:
            yield token


class TestAskEndpoint:
    """Pruebas del endpoint POST /ask."""

    def test_ask_returns_text(self):
        """POST /ask debe devolver texto plano con la respuesta."""
        engine = MockEngine(["respuesta de prueba"])
        app = make_app_with_engine(engine)

        with TestClient(app) as client:
            response = client.post("/ask", json={"question": "¿cómo va la carrera?"})
            assert response.status_code == 200
            assert response.text == "respuesta de prueba"
            assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_ask_without_engine_returns_503(self):
        """POST /ask sin IntelligenceEngine debe devolver 503."""
        app = make_app_with_engine(mock_engine=None)
        del app.state.intelligence_engine  # Eliminar del estado

        with TestClient(app) as client:
            response = client.post("/ask", json={"question": "test"})
            assert response.status_code == 503
            assert "IntelligenceEngine" in response.text

    def test_ask_with_chat_history(self):
        """POST /ask con chat_history debe formatearlo correctamente."""
        received_history = []

        class TrackingEngine:
            async def ask_async(self, question, chat_history=None):
                nonlocal received_history
                received_history = chat_history or []
                yield "ok"

        engine = TrackingEngine()
        app = make_app_with_engine(engine)

        with TestClient(app) as client:
            response = client.post("/ask", json={
                "question": "¿qué tal?",
                "chat_history": [
                    {"role": "user", "content": "hola"},
                    {"role": "assistant", "content": "adiós"}
                ]
            })
            assert response.status_code == 200

        assert len(received_history) == 2
        assert received_history[0] == {"role": "user", "content": "hola"}
        assert received_history[1] == {"role": "assistant", "content": "adiós"}

    def test_ask_with_empty_chat_history(self):
        """POST /ask con chat_history vacío no debe romperse."""
        app = make_app_with_engine(MockEngine(["ok"]))

        with TestClient(app) as client:
            response = client.post("/ask", json={
                "question": "test",
                "chat_history": []
            })
            assert response.status_code == 200

    def test_ask_without_chat_history(self):
        """POST /ask sin chat_history debe funcionar."""
        app = make_app_with_engine(MockEngine(["respuesta"]))

        with TestClient(app) as client:
            response = client.post("/ask", json={"question": "test"})
            assert response.status_code == 200

    def test_ask_with_empty_response_fallback(self):
        """POST /ask con respuesta vacía debe usar mensaje de fallback."""
        engine = MockEngine([""])
        app = make_app_with_engine(engine)

        with TestClient(app) as client:
            response = client.post("/ask", json={"question": "test"})
            assert response.status_code == 200
            assert "No he podido generar" in response.text

    def test_ask_multiple_tokens_concatenated(self):
        """POST /ask debe concatenar múltiples tokens del async generator."""
        engine = MockEngine(["uno ", "dos ", "tres"])
        app = make_app_with_engine(engine)

        with TestClient(app) as client:
            response = client.post("/ask", json={"question": "test"})
            assert response.status_code == 200
            assert response.text == "uno dos tres"

    def test_ask_returns_422_without_question(self):
        """POST /ask sin campo 'question' debe devolver 422."""
        app = make_app_with_engine(MockEngine(["ok"]))

        with TestClient(app) as client:
            response = client.post("/ask", json={})
            assert response.status_code == 422

    def test_ask_returns_422_with_wrong_type(self):
        """POST /ask con question numérica debe devolver 422."""
        app = make_app_with_engine(MockEngine(["ok"]))

        with TestClient(app) as client:
            response = client.post("/ask", json={"question": 123})
            assert response.status_code == 422
