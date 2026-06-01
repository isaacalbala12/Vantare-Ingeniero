"""Constantes de los mensajes del spotter y sus rutas de audio."""

# Mensajes del spotter (sin LLM)
CAR_LEFT = "spotter/car_left"
CAR_RIGHT = "spotter/car_right"
CLEAR_LEFT = "spotter/clear_left"
CLEAR_RIGHT = "spotter/clear_right"
CLEAR_ALL_ROUND = "spotter/clear_all_round"
THREE_WIDE = "spotter/in_the_middle"  # "three wide" en el código original
STILL_THERE = "spotter/still_there"
THREE_WIDE_ON_LEFT = "spotter/three_wide_on_left"
THREE_WIDE_ON_RIGHT = "spotter/three_wide_on_right"

# Mapa para SpotterVoice enum-like
ALL_MESSAGES = {
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, STILL_THERE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT,
}
