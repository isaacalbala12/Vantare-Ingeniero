import pytest
from src.voice.priority import classify_tts_priority
from tests.fixtures.audio_trigger_matrix import SPOTTER_AUDIO_ROWS


@pytest.mark.parametrize("row", SPOTTER_AUDIO_ROWS, ids=lambda r: r.id)
def test_spotter_matrix_matches_frontend_expectation(row):
    if row.expect_tts_priority == "N/A":
        return
    got = classify_tts_priority(
        row.sample_message,
        {
            "category": row.category,
            "severity": row.severity,
            "audio_priority": row.audio_priority,
        },
    )
    assert got == row.expect_tts_priority


def test_proximity_audio_priority_2_is_immediate():
    assert classify_tts_priority("Coche a la derecha", {"category": "proximity", "audio_priority": "2"}) == "IMMEDIATE"


def test_gaps_low_priority_is_normal():
    assert classify_tts_priority("Coche a 0.3s delante", {"category": "gaps", "audio_priority": "1"}) == "NORMAL"


def test_map_alert_engineer_voice_response():
    from src.voice.play_command import play_command_from_alert

    cmd = play_command_from_alert(
        text="Respuesta",
        category="engineer",
        audio_priority="NORMAL",
        event_id="ptt",
        ttl_seconds=10,
        payload={"category": "voice_response"},
    )
    assert cmd.priority == "ENGINEER"


def test_map_alert_uses_classifier_not_only_strings():
    from src.voice.play_command import play_command_from_alert

    cmd = play_command_from_alert(
        text="Coche a la izquierda",
        category="proximity",
        audio_priority="2",
        event_id="proximity",
        ttl_seconds=2,
        payload={"category": "proximity"},
    )
    assert cmd.priority == "IMMEDIATE"
