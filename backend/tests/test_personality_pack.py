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


def test_sweary_profile_injects_tone_suffix():
    pack = PersonalityPack(profile_id="aggressive", sweary=True)
    suffix = pack.engineer_system_suffix().lower()
    assert pack.sweary_enabled is True
    assert "lenguaje coloquial" in suffix or "paddock" in suffix


def test_sweary_off_no_colloquial_suffix():
    pack = PersonalityPack(profile_id="standard", sweary=False)
    suffix = pack.engineer_system_suffix().lower()
    assert "lenguaje coloquial" not in suffix


def test_proactivity_low_blocks_low_priority():
    pack = PersonalityPack(proactivity="low")
    assert pack.should_emit_proactive("CRITICAL") is True
    assert pack.should_emit_proactive("HIGH") is True
    assert pack.should_emit_proactive("MEDIUM") is False
    assert pack.should_emit_proactive("LOW") is False


def test_proactivity_high_allows_low():
    pack = PersonalityPack(proactivity="high")
    assert pack.should_emit_proactive("LOW") is True


def test_tone_preview_matches_engineer_suffix():
    pack = PersonalityPack("aggressive", sweary=True)
    assert pack.tone_preview() == pack.engineer_system_suffix()
    assert "enérgico" in pack.tone_preview().lower()


def test_pearl_frequency_clamped():
    pack = PersonalityPack(pearl_frequency=2.5)
    assert pack.pearl_frequency == 1.0
    pack.apply_runtime(pearl_frequency=-0.1)
    assert pack.pearl_frequency == 0.0
