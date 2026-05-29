"""Tests para EventAdapter."""

import time

from src.intelligence.event_adapter import EventAdapter
from src.services.audio_queue import AudioQueueManager
from src.models.messages import AlertMessage, QueuedMessage, SoundType, MessagePriority
from src.intelligence.events.fuel import FuelEvent


def test_adapter_converts_alert_to_queued():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    alert = AlertMessage(
        event="estimate_1_lap",
        alert_id="test-id",
        category="fuel",
        message="Queda 1 vuelta.",
        audio_priority="HIGH",
        severity="HIGH",
        ttl=30,
        dismissable=True,
        payload={},
    )
    adapter.process_event_output(event, [alert])
    assert len(mgr._immediate) == 1
    msg = mgr._immediate[0][2]
    assert msg.sound_type == SoundType.IMPORTANT
    assert msg.priority == MessagePriority.HIGH
    assert msg.text == "Queda 1 vuelta."


def test_adapter_registers_validators():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    adapter.adapt_event(event)
    assert "estimate_1_lap" in mgr._validators


def test_adapter_priority_mapping_semantic():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    for audio_prio, (expected_st, expected_prio) in {
        "CRITICAL": (SoundType.CRITICAL, MessagePriority.CRITICAL),
        "HIGH": (SoundType.IMPORTANT, MessagePriority.HIGH),
        "MEDIUM": (SoundType.REGULAR, MessagePriority.MEDIUM),
        "LOW": (SoundType.REGULAR, MessagePriority.LOW),
    }.items():
        alert = AlertMessage(
            event="test", alert_id="t", category="test", message="test",
            audio_priority=audio_prio, severity="INFO", ttl=10, dismissable=True, payload={}
        )
        q = adapter._alert_to_queued(alert)
        assert q.sound_type == expected_st, f"Semantic {audio_prio}: expected SoundType.{expected_st.name}"
        assert q.priority == expected_prio, f"Semantic {audio_prio}: expected MessagePriority.{expected_prio.name}"


def test_adapter_priority_mapping_integer_string():
    """FIX: spotter.py and position.py use integer strings '1'..'4' for audio_priority."""
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    for audio_prio, (expected_st, expected_prio) in {
        "4": (SoundType.CRITICAL, MessagePriority.CRITICAL),
        "3": (SoundType.IMPORTANT, MessagePriority.HIGH),
        "2": (SoundType.REGULAR, MessagePriority.MEDIUM),
        "1": (SoundType.REGULAR, MessagePriority.LOW),
    }.items():
        alert = AlertMessage(
            event="test", alert_id="t", category="test", message="test",
            audio_priority=audio_prio, severity="INFO", ttl=10, dismissable=True, payload={}
        )
        q = adapter._alert_to_queued(alert)
        assert q.sound_type == expected_st, f"Int-string {audio_prio}: expected SoundType.{expected_st.name}"
        assert q.priority == expected_prio, f"Int-string {audio_prio}: expected MessagePriority.{expected_prio.name}"


def test_adapter_priority_unknown_defaults():
    mgr = AudioQueueManager()
    adapter = EventAdapter(mgr)
    event = FuelEvent()
    alert = AlertMessage(
        event="test", alert_id="t", category="test", message="test",
        audio_priority="UNKNOWN", severity="INFO", ttl=10, dismissable=True, payload={}
    )
    q = adapter._alert_to_queued(alert)
    assert q.sound_type == SoundType.REGULAR
    assert q.priority == MessagePriority.MEDIUM
