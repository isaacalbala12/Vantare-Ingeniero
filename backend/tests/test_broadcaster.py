"""Tests unitarios para el módulo transport/broadcaster.py.

Verifica:
- send() con broadcast_sync funcionando
- send() cuando broadcast_sync lanza excepción
- send() con diferentes tipos de mensaje
"""
import pytest
from unittest.mock import patch, MagicMock
from src.transport.broadcaster import send


class FakeMessage:
    """Mensaje ficticio para pruebas."""
    def __init__(self, text: str):
        self.text = text


class TestBroadcasterSend:
    """Pruebas de la función send."""

    def test_send_calls_broadcast_sync(self):
        """send() debe llamar a broadcast_sync con el mensaje."""
        mock_broadcast = MagicMock()
        message = FakeMessage("test message")

        with patch("src.transport.broadcaster.broadcast_sync", mock_broadcast):
            send(message)

        mock_broadcast.assert_called_once_with(message)

    def test_send_handles_exception(self):
        """send() debe capturar excepciones de broadcast_sync sin propagarlas."""
        mock_broadcast = MagicMock()
        mock_broadcast.side_effect = RuntimeError("Broadcast failed")
        message = FakeMessage("error message")

        with patch("src.transport.broadcaster.broadcast_sync", mock_broadcast):
            # No debe propagar la excepción
            send(message)

        mock_broadcast.assert_called_once_with(message)

    def test_send_multiple_messages(self):
        """send() debe funcionar correctamente con múltiples mensajes."""
        mock_broadcast = MagicMock()
        messages = [FakeMessage(f"msg_{i}") for i in range(5)]

        with patch("src.transport.broadcaster.broadcast_sync", mock_broadcast):
            for msg in messages:
                send(msg)

        assert mock_broadcast.call_count == 5
        for i, msg in enumerate(messages):
            assert mock_broadcast.call_args_list[i][0][0] == msg

    def test_send_with_none(self):
        """send() debe manejar mensajes None."""
        mock_broadcast = MagicMock()
        
        with patch("src.transport.broadcaster.broadcast_sync", mock_broadcast):
            try:
                send(None)
            except Exception:
                pass  # Depende de la implementación de broadcast_sync

        mock_broadcast.assert_called_once_with(None)

    def test_send_with_different_message_types(self):
        """send() debe manejar distintos tipos de mensajes."""
        mock_broadcast = MagicMock()
        messages = [
            "string message",
            42,
            {"key": "value"},
            ["list"],
            None,
        ]

        with patch("src.transport.broadcaster.broadcast_sync", mock_broadcast):
            for msg in messages:
                send(msg)

        assert mock_broadcast.call_count == len(messages)
