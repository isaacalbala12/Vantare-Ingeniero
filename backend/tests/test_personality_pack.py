"""Tests PersonalityPack."""

from src.intelligence.personality_pack import PersonalityPack, DEFAULT_PROFILE_ID


def test_default_profile_is_standard():
    pack = PersonalityPack()
    assert pack.profile_id == DEFAULT_PROFILE_ID
    assert pack.get().label == "Estándar"


def test_invalid_profile_falls_back_to_standard():
    pack = PersonalityPack("unknown")
    assert pack.profile_id == "standard"


def test_aggressive_has_distinct_tone():
    pack = PersonalityPack("aggressive")
    assert "enérgico" in pack.engineer_system_suffix().lower()


def test_dual_voices_per_profile():
    formal = PersonalityPack("formal")
    assert formal.tts_voice_engineer() != formal.tts_voice_spotter()


def test_spotter_phrase_by_profile():
    aggressive = PersonalityPack("aggressive")
    msg = aggressive.spotter_phrase("hold_line", side="derecha")
    assert any(w in msg for w in ("Aguanta", "desvíes", "viene"))
    assert "derecha" in msg


def test_spotter_phrase_supports_pipe_variants():
    pack = PersonalityPack("standard")
    msg = pack.spotter_phrase("clear_left")
    assert msg
    assert any(w in msg.lower() for w in ("despejado", "libre", "clear"))
