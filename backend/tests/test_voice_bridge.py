import asyncio
from unittest.mock import MagicMock

import pytest
from src.models.messages import AlertMessage
from src.voice.bridge import VoiceBridge
from src.voice.voice_queue import VoiceQueue


def _alert(**overrides) -> AlertMessage:
    base = dict(
        event="alert",
        alert_id="a1",
        category="spotter",
        message="Coche a la izquierda",
        audio_priority="IMPORTANT",
        severity="INFO",
        ttl=2,
        dismissable=True,
        payload={"event_id": "proximity_left", "queue_class": "IMMEDIATE"},
    )
    base.update(overrides)
    return AlertMessage(**base)


@pytest.mark.asyncio
async def test_alert_enqueues_play_command_and_broadcasts_once():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)
    await bridge._enqueue_alert(_alert())
    ws_cb.assert_not_called()  # enqueue alone does not WS
    assert q.qsize() == 1


def test_send_broadcasts_ws_and_schedules_enqueue():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)

    async def _run():
        bridge.send(_alert())
        await asyncio.sleep(0.05)
        assert ws_cb.call_count == 1
        assert q.qsize() == 1

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_disabled_skips_queue_but_still_ws_on_send():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=False)
    bridge.send(_alert())
    await asyncio.sleep(0.02)
    ws_cb.assert_called_once()
    assert q.qsize() == 0
