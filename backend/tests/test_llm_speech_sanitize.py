from src.intelligence.llm_speech_sanitize import sanitize_llm_speech


def test_sanitize_strips_reasoning_meta():
    raw = (
        "Por favor, no digas nada.\n"
        "El usuario me pide que no diga nada, así que no genero texto.\n"
        "Wait, revisa la pregunta."
    )
    assert sanitize_llm_speech(raw) == ""


def test_sanitize_keeps_radio_answer():
    raw = "Te quedan 4 vueltas de combustible. Mantén el ritmo."
    assert sanitize_llm_speech(raw) == raw
