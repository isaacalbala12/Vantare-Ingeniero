"""Tests para EventManager."""

import pytest

from src.intelligence.event_manager import EventManager
from src.services.audio_queue import AudioQueueManager
from src.models.messages import QueuedMessage, SoundType, MessagePriority


@pytest.fixture
def audio_queue():
    return AudioQueueManager()


@pytest.fixture
def event_manager(audio_queue):
    return EventManager(audio_queue)


def test_event_manager_initializes_all_events(event_manager):
    assert len(event_manager.events) == 15


def test_event_manager_trigger_all_enqueues_fuel_alert(event_manager):
    state = {
        "session_type": "Race",
        "session_phase": "Green",
        "fuel_remaining": 1.5,
        "fuel_capacity": 100.0,
        "fuel_per_lap": 3.0,
        "completed_laps": 10,
        "total_laps": 30,
        "in_pits": False,
        "session_id": "test-session",
    }
    event_manager.trigger_all(state)
    total = len(event_manager.audio_queue._immediate) + len(event_manager.audio_queue._regular)
    assert total > 0


def test_event_manager_session_change_resets_state(event_manager):
    event_manager.trigger_all({"session_type": "Race", "session_phase": "Green", "session_id": "s1"})
    event_manager.trigger_all({"session_type": "Race", "session_phase": "Green", "session_id": "s2"})
    assert event_manager._previous_state.get("session_id") == "s2"
