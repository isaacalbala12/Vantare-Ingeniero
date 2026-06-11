from __future__ import annotations

from src.voice.priority import normalize_tts_text
from src.voice.spotter_cache import default_spotter_phrases


def build_text_to_cache_key_map(phrases: dict[str, str] | None = None) -> dict[str, str]:
    phrases = phrases or default_spotter_phrases()
    out: dict[str, str] = {}
    for key, text in phrases.items():
        out[normalize_tts_text(text)] = key
    return out


def resolve_wav_cache_key(
    *,
    text: str,
    category: str,
    event_id: str,
    payload: dict | None,
    text_to_key: dict[str, str] | None = None,
) -> str | None:
    payload = payload or {}
    explicit = payload.get("event_id")
    if explicit:
        return str(explicit)
    if event_id and event_id not in (
        "proximity",
        "fuel",
        "gaps",
        "damage",
        "limiter",
        "safety_car",
        "session",
        "engineer",
        "spotter",
    ):
        return event_id
    if payload.get("service") == "spotter" or category in (
        "proximity",
        "limiter",
        "fuel",
        "safety_car",
        "damage",
        "session",
        "spotter",
    ):
        mapping = text_to_key or build_text_to_cache_key_map()
        return mapping.get(normalize_tts_text(text))
    return None
