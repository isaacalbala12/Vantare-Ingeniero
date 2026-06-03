"""
Test helpers for the Vantare Ingeniero backend.

Provides:
- build_frame(): synthetic flat dict for pipeline tests
- BroadcastCapture: capture broadcast messages for assertions
- crewchief_test_harness: pytest fixture assembling mock components
"""

import time
from unittest.mock import MagicMock

import pytest

from src.services.frame_cache import FrameCache
from src.services.game_state_builder import build as build_gsd
from src.intelligence.event_engine import EventEngine
from src.intelligence.event_flags import event_flags
from src.intelligence.base_event import FakeAudioPlayer


# =========================================================================
# Frame Builder
# =========================================================================

def build_frame(**overrides) -> dict:
    """Construct a synthetic flat dict for pipeline tests.

    Defaults simulate a RACE session, lap 1, position 3,
    50% fuel, no incidents, normal conditions.

    Keys are compatible with ``game_state_builder.build()``.

    Override any field by passing it as a keyword argument.
    """
    base = {
        # Session
        "session_type": 3,               # RACE
        "session_phase": 5,              # GREEN
        "session_running_time": 120.0,
        "session_time_remaining": 3600.0,

        # Position & progress
        "place": 3,
        "lap_number": 1,
        "sector_number": 0,
        "total_laps": 0,
        "lap_distance": 500.0,

        # Driver
        "driver_name": "Test Driver",
        "best_lap_time": 0.0,
        "last_lap_time": 0.0,

        # Fuel & battery
        "fuel_left": 50.0,
        "fuel_capacity": 100.0,
        "battery_percentage": 80.0,

        # Motion
        "speed_ms": 70.0,
        "world_x": 0.0,
        "world_y": 0.0,
        "world_z": 0.0,
        "rotation_yaw": 0.0,
        "rotation_pitch": 0.0,
        "rotation_roll": 0.0,

        # Engine
        "engine_rpm": 6000.0,
        "gear": 5,
        "water_temp": 85.0,
        "oil_temp": 90.0,

        # Tyre temperatures (per-corner)
        "tyre_temp_fl": 90.0,
        "tyre_temp_fr": 92.0,
        "tyre_temp_rl": 85.0,
        "tyre_temp_rr": 87.0,

        # Tyre pressure (per-corner)
        "tyre_pressure_fl": 25.0,
        "tyre_pressure_fr": 25.5,
        "tyre_pressure_rl": 24.8,
        "tyre_pressure_rr": 24.9,

        # Tyre wear (list)
        "tyre_wear": [0.10, 0.12, 0.08, 0.09],

        # Brake temperatures (per-corner)
        "brake_temp_fl": 200.0,
        "brake_temp_fr": 210.0,
        "brake_temp_rl": 180.0,
        "brake_temp_rr": 190.0,

        # Brake wear (list)
        "brake_wear": [0.5, 0.5, 0.4, 0.4],

        # Damage
        "damage_aero": 0.0,
        "damage_body": [0.0, 0.0, 0.0, 0.0],
        "damage_suspension": [0.0, 0.0, 0.0, 0.0],

        # Flags
        "in_pits": False,
        "drs_enabled": False,

        # Opponents
        "rivals": [],
    }
    base.update(overrides)
    return base


# =========================================================================
# Broadcast Capture
# =========================================================================

class BroadcastCapture:
    """Captures messages sent via broadcast_callback for test assertions.

    Usage::

        capture = BroadcastCapture()
        some_function(broadcast_callback=capture.callback)
        assert len(capture.messages) == 1
        msg = capture.wait_for_event("crewchief_alert")
    """

    def __init__(self):
        self.messages: list = []

    def callback(self, msg):
        """Use as broadcast_callback. Stores every message."""
        self.messages.append(msg)

    def wait_for_event(self, event_type: str, timeout: float = 2.0):
        """Block until a message with ``event == event_type`` is captured.

        Returns the matching message, or *None* if the timeout expires.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            for m in self.messages:
                if hasattr(m, 'event') and m.event == event_type:
                    return m
            time.sleep(0.01)
        return None

    def clear(self):
        """Clear all captured messages."""
        self.messages.clear()


# =========================================================================
# Pytest Fixture — CrewChief Test Harness
# =========================================================================

@pytest.fixture
def crewchief_test_harness():
    """Assembles mock components for CrewChief pipeline tests.

    Returns a dict with::

        {
            "reader":          MagicMock LMUReader,
            "cache":           FrameCache wrapping *reader*,
            "engine":          EventEngine (empty, no events registered),
            "audio_player":    FakeAudioPlayer,
            "broadcast":       BroadcastCapture,
            "build_frame":     build_frame function,
            "make_gsd":        helper to call game_state_builder.build(),
        }

    Cleans ``event_flags`` after each test (via ``event_flags.reset()``).
    """
    # --- Mock LMUReader ---------------------------------------------------
    reader = MagicMock()
    reader.offline = True
    reader.shmm = None
    reader.get_flat_dict.return_value = build_frame()

    # --- FrameCache (wraps mock reader) -----------------------------------
    cache = FrameCache(reader)

    # --- Broadcast capture ------------------------------------------------
    broadcast = BroadcastCapture()

    # --- Fake audio player (no real sound) --------------------------------
    audio_player = FakeAudioPlayer()

    # --- Event engine (empty — test registers what it needs) -------------
    engine = EventEngine(ap=audio_player)

    # --- Helper: build GameStateData from frame overrides -----------------
    def make_gsd(**overrides) -> "GameStateData":
        """Build a GameStateData from build_frame() with optional overrides."""
        return build_gsd(build_frame(**overrides))

    harness = {
        "reader": reader,
        "cache": cache,
        "engine": engine,
        "audio_player": audio_player,
        "broadcast": broadcast,
        "build_frame": build_frame,
        "make_gsd": make_gsd,
    }

    yield harness

    # --- Cleanup ----------------------------------------------------------
    event_flags.reset()
    broadcast.clear()
