from src.voice.ducking import DuckingController


def test_ducking_noop_without_pycaw():
    d = DuckingController(level=0.2)
    d.duck_on()
    d.duck_off()
