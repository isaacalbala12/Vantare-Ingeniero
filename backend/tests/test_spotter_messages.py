"""Tests de spotter_messages — constantes de los mensajes del spotter.

Cobertura:
- Unicidad de constantes
- Cobertura del set ALL_MESSAGES
- Estructura: todos los mensajes apuntan a 'spotter/' (ruta de audio)
- Ninguna constante es None o vacía
"""
from src.intelligence.spotter_messages import (
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT,
    ALL_MESSAGES,
)


class TestMessageConstants:
    def test_all_nine_constants_exist(self):
        """Las 9 constantes del spotter existen y son strings no vacías."""
        for msg in (CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
                    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT):
            assert msg is not None
            assert isinstance(msg, str)
            assert len(msg) > 0

    def test_constants_unique(self):
        """Cada mensaje tiene un valor único."""
        constants = (CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
                     THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT)
        assert len(set(constants)) == 9

    def test_all_constants_in_all_messages_set(self):
        assert CAR_LEFT in ALL_MESSAGES
        assert CAR_RIGHT in ALL_MESSAGES
        assert CLEAR_LEFT in ALL_MESSAGES
        assert CLEAR_RIGHT in ALL_MESSAGES
        assert CLEAR_ALL_ROUND in ALL_MESSAGES
        assert THREE_WIDE in ALL_MESSAGES
        assert STILL_THERE in ALL_MESSAGES
        assert THREE_WIDE_ON_LEFT in ALL_MESSAGES
        assert THREE_WIDE_ON_RIGHT in ALL_MESSAGES

    def test_all_messages_set_size(self):
        """ALL_MESSAGES tiene exactamente 9 mensajes."""
        assert len(ALL_MESSAGES) == 9

    def test_all_messages_start_with_spotter(self):
        """Todos los mensajes apuntan a la categoría 'spotter/' (ruta de audio)."""
        for msg in ALL_MESSAGES:
            assert msg.startswith("spotter/"), f"{msg} no empieza con spotter/"

    def test_no_trailing_slash(self):
        for msg in ALL_MESSAGES:
            assert not msg.endswith("/"), f"{msg} no debe terminar con /"

    def test_all_messages_have_filename(self):
        """Cada mensaje tiene un nombre de archivo después de 'spotter/'."""
        for msg in ALL_MESSAGES:
            parts = msg.split("/")
            assert len(parts) == 2
            assert parts[0] == "spotter"
            assert len(parts[1]) > 0
            assert parts[1].islower() or "_" in parts[1]  # algún formato de nombre


class TestMessageSemantics:
    """Verifica que los nombres describen correctamente su función."""

    def test_clear_messages_have_clear_keyword(self):
        assert "clear" in CLEAR_LEFT
        assert "clear" in CLEAR_RIGHT
        assert "clear" in CLEAR_ALL_ROUND

    def test_car_messages_have_car_keyword(self):
        assert "car" in CAR_LEFT
        assert "car" in CAR_RIGHT

    def test_three_wide_in_middle(self):
        """THREE_WIDE apunta a 'in_the_middle' (nombre del archivo de audio)."""
        assert THREE_WIDE == "spotter/in_the_middle"

    def test_still_there_message(self):
        assert "still" in STILL_THERE
