from src.intelligence.ptt_prompt_context import (
    build_ptt_context_for_question,
    classify_ptt_question,
)


def test_classify_casual_greeting():
    assert classify_ptt_question("Hola, ¿cómo estás?") == "casual"


def test_classify_pace_question():
    assert classify_ptt_question("¿Pues el ritmo el primero?") == "pace"


def test_casual_context_omits_tire_temps():
    data = {
        "session_type": "practice",
        "session_class": "GT3",
        "ambient_temp": 20,
        "grip": 0,
        "tyre_temps": [98, 98, 96, 95],
    }
    ctx = build_ptt_context_for_question("Hola, ¿cómo estás?", data, "")
    assert "GT3" in ctx
    assert "98" not in ctx
    assert "goma" not in ctx.lower()


def test_pace_context_includes_leader_reference():
    data = {
        "session_type": "practice",
        "session_class": "GT3",
        "ambient_temp": 20,
        "grip": 0,
        "position": 12,
        "player_best_lap": 175.2,
        "leader_best_lap": 173.0,
    }
    ctx = build_ptt_context_for_question("¿Cuál es el ritmo del primero?", data, "")
    assert "líder" in ctx.lower() or "Referencia" in ctx
    assert "98" not in ctx
