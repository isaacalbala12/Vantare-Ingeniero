from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

_THINK_OPEN = "<" + "think>"
_THINK_CLOSE = "<" + "/think>"


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


def test_sanitize_strips_redacted_thinking_block():
    raw = (
        "<think>El piloto pregunta por fuel. Debo ser breve.</think>\n\n"
        "Te quedan unas 4 vueltas de combustible."
    )
    assert sanitize_llm_speech(raw) == "Te quedan unas 4 vueltas de combustible."


def test_sanitize_strips_qwen_think_tags():
    raw = f"{_THINK_OPEN}Analicemos la telemetría.{_THINK_CLOSE}\nBOX esta vuelta, margen justo."
    assert sanitize_llm_speech(raw) == "BOX esta vuelta, margen justo."


def test_sanitize_picks_last_paragraph():
    raw = (
        "El usuario pregunta por neumáticos.\n\n"
        "Medio desgastados delante, aguanta dos stint más."
    )
    assert sanitize_llm_speech(raw) == "Medio desgastados delante, aguanta dos stint más."


def test_sanitize_strips_incomplete_think_during_stream():
    raw = f"{_THINK_OPEN}Todavía pensando"
    assert sanitize_llm_speech(raw) == ""


def test_sanitize_extracts_quoted_radio_from_reasoning():
    raw = (
        'El usuario pide una frase corta de radio. Algo como '
        '"Atención piloto: te quedan cuatro vueltas de combustible, planifica boxes." '
        "Sí, es corta y clara."
    )
    assert sanitize_llm_speech(raw) == (
        "Atención piloto: te quedan cuatro vueltas de combustible, planifica boxes."
    )


def test_sanitize_collapses_duplicate_quoted_versions():
    raw = (
        '"Buenos días, Alelemi. Estás en vuelta de instalación de práctica GT3, pista verde a 20°C."\n'
        '"Buenos días, Alelemi. Estás en vuelta de instalación: pista verde a 20°C, avisa cuando quieras registrar tiempos."'
    )
    result = sanitize_llm_speech(raw)
    assert "Buenos días" in result
    assert result.count("Buenos días") == 1
    assert "registrar tiempos" in result


def test_sanitize_caps_to_two_sentences():
    raw = "Primera frase. Segunda frase. Tercera frase que sobra."
    assert sanitize_llm_speech(raw) == "Primera frase. Segunda frase."


def test_sanitize_delta_incremental():
    from src.intelligence.llm_speech_sanitize import SpeechSanitizeState, sanitize_llm_speech_delta

    state = SpeechSanitizeState()
    _, d1 = sanitize_llm_speech_delta("Te quedan ", state)
    assert d1 == "Te quedan"
    _, d2 = sanitize_llm_speech_delta("Te quedan 4 vueltas.", state, finalize=True)
    assert d2.strip() == "4 vueltas."
