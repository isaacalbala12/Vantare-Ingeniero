import time

from src.voice.play_command import PlayCommand, play_command_from_alert


def test_play_command_from_alert_spotter_is_immediate():
    cmd = play_command_from_alert(
        text="Coche a la izquierda",
        category="spotter",
        audio_priority="IMPORTANT",
        event_id="proximity_left",
        ttl_seconds=2,
        payload={"queue_class": "IMMEDIATE"},
    )
    assert cmd.priority == "IMMEDIATE"
    assert cmd.category == "spotter"
    assert cmd.wav_cache_key == "proximity_left"
    assert cmd.expires_at > time.monotonic()


def test_expired_command_detected():
    cmd = PlayCommand(
        id="1",
        text="x",
        priority="NORMAL",
        category="engineer",
        event_id="fuel",
        ttl_ms=100,
        expires_at=time.monotonic() - 1,
    )
    assert cmd.is_expired() is True


def test_engineer_voice_response_priority():
    cmd = play_command_from_alert(
        text="Respuesta piloto",
        category="engineer",
        audio_priority="NORMAL",
        event_id="ptt_reply",
        ttl_seconds=10,
        payload={"category": "voice_response"},
    )
    assert cmd.priority == "ENGINEER"
