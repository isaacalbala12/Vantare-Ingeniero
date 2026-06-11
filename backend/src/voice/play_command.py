from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Literal

from src.voice.cache_keys import resolve_wav_cache_key
from src.voice.priority import map_alert_to_play_priority

Priority = Literal["IMMEDIATE", "NORMAL", "ENGINEER"]


@dataclass(frozen=True)
class PlayCommand:
    id: str
    text: str
    priority: Priority
    category: str
    event_id: str
    ttl_ms: int
    expires_at: float
    wav_cache_key: str | None = None
    validation_key: str | None = None

    def is_expired(self, now: float | None = None) -> bool:
        t = time.monotonic() if now is None else now
        return t > self.expires_at


def play_command_from_alert(
    *,
    text: str,
    category: str,
    audio_priority: str,
    event_id: str,
    ttl_seconds: int,
    payload: dict | None = None,
) -> PlayCommand:
    ttl_ms = max(1000, int(ttl_seconds * 1000))
    priority = map_alert_to_play_priority(text=text, audio_priority=audio_priority, payload=payload)
    cache_key = resolve_wav_cache_key(text=text, category=category, event_id=event_id, payload=payload)
    return PlayCommand(
        id=str(uuid.uuid4()),
        text=text.strip(),
        priority=priority,
        category=category,
        event_id=event_id,
        ttl_ms=ttl_ms,
        expires_at=time.monotonic() + ttl_ms / 1000.0,
        wav_cache_key=cache_key,
        validation_key=(payload or {}).get("validation_key"),
    )
