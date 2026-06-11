"""VoiceBridge debe encolar alertas desde contexto sync (sin event loop)."""

import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock

from src.models.messages import AlertMessage
from src.voice.bridge import VoiceBridge
from src.voice.voice_queue import VoiceQueue


def _alert() -> AlertMessage:
    return AlertMessage(
        event="alert",
        alert_id="sync-1",
        category="spotter",
        message="Coche a la derecha",
        audio_priority="IMPORTANT",
        severity="INFO",
        ttl=2,
        dismissable=True,
        payload={"event_id": "proximity_right", "queue_class": "IMMEDIATE"},
    )


def test_voice_bridge_send_from_sync_thread_enqueues():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)

    def _send_from_thread():
        bridge.send(_alert())

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(_send_from_thread).result()

    deadline = time.monotonic() + 1.0
    while q.qsize() < 1 and time.monotonic() < deadline:
        time.sleep(0.02)

    assert ws_cb.call_count == 1
    assert q.qsize() >= 1
