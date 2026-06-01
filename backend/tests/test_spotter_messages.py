from src.intelligence.spotter_messages import (
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT,
    ALL_MESSAGES,
)


def test_message_constants_unique():
    """Cada mensaje tiene un valor único."""
    assert len({CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
                THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT}) == 9


def test_all_messages_includes_all():
    assert CAR_LEFT in ALL_MESSAGES
    assert CAR_RIGHT in ALL_MESSAGES
    assert STILL_THERE in ALL_MESSAGES
    assert THREE_WIDE in ALL_MESSAGES
    assert len(ALL_MESSAGES) == 9


def test_messages_start_with_spotter():
    """Todos los mensajes apuntan a la categoría 'spotter/'."""
    for msg in ALL_MESSAGES:
        assert msg.startswith("spotter/"), f"{msg} no empieza con spotter/"
