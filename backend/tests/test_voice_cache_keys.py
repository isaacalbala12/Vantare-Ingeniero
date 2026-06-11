from src.voice.cache_keys import build_text_to_cache_key_map, resolve_wav_cache_key
from src.voice.play_command import play_command_from_alert


def test_cc_event_id_from_payload():
    key = resolve_wav_cache_key(
        text="Hold line",
        category="spotter",
        event_id="hold_line_left",
        payload={"event_id": "hold_line_left"},
    )
    assert key == "hold_line_left"


def test_proximity_resolves_by_normalized_text():
    mapping = build_text_to_cache_key_map()
    key = resolve_wav_cache_key(
        text="Coche a la izquierda",
        category="proximity",
        event_id="proximity",
        payload={"category": "proximity", "service": "spotter"},
        text_to_key=mapping,
    )
    assert key is not None
    assert "left" in key or key.startswith("proximity")


def test_play_command_sets_cache_key_for_proximity():
    cmd = play_command_from_alert(
        text="Coche a la derecha",
        category="proximity",
        audio_priority="2",
        event_id="proximity",
        ttl_seconds=2,
        payload={"category": "proximity", "service": "spotter"},
    )
    assert cmd.wav_cache_key is not None


def test_limiter_legacy_text_resolves_cache_key():
    from src.voice.cache_keys import build_text_to_cache_key_map, resolve_wav_cache_key

    m = build_text_to_cache_key_map()
    key = resolve_wav_cache_key(
        text="Activa el limiter de boxes.",
        category="limiter",
        event_id="limiter",
        payload={"service": "spotter", "category": "limiter"},
        text_to_key=m,
    )
    assert key is not None


def test_trailing_period_still_matches():
    m = build_text_to_cache_key_map()
    key = resolve_wav_cache_key(
        text="Coche a la izquierda.",
        category="proximity",
        event_id="proximity",
        payload={"service": "spotter"},
        text_to_key=m,
    )
    assert key == "proximity_left"


def test_unknown_dynamic_text_no_cache_key():
    key = resolve_wav_cache_key(
        text="Coche a 0.3s delante",
        category="gaps",
        event_id="gaps",
        payload={},
        text_to_key={},
    )
    assert key is None
