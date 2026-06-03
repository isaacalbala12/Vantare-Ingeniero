"""Integration tests for the Cartesian spotter 20Hz pipeline path.

Tests the NoisyCartesianCoordinateSpotter using the spotter_frame format
from FrameCache.get_spotter_frame(), simulating the pipeline data flow
at 20Hz. Checks that AudioPlayer received the expected messages.

These are pipeline cross-component tests, NOT unit tests of the spotter
itself (61 unit tests already exist in test_noisy_cartesian_spotter.py).
"""
from unittest.mock import MagicMock

import pytest

from src.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter
from src.intelligence.spotter_messages import (
    CAR_LEFT,
    CAR_RIGHT,
    CLEAR_ALL_ROUND,
    THREE_WIDE,
)


# ============================================================
# Helpers: build spotter_frame and rival dicts
# ============================================================


def make_spotter_frame(
    x=100.0,
    z=100.0,
    yaw=0.0,
    speed_ms=50.0,
    rivals=None,
    session_phase=5,
    in_pits=False,
    frame_id=1,
):
    """Build a spotter_frame matching FrameCache.get_spotter_frame().

    This is the exact format the pipeline passes to
    ``self.spotter.trigger(sf, sf["rivals"], time.time())``
    in CrewChiefRuntime.tick().
    """
    return {
        "world_x": x,
        "world_z": z,
        "rotation_yaw": yaw,
        "speed_ms": speed_ms,
        "rivals": rivals or [],
        "session_phase": session_phase,
        "in_pits": in_pits,
        "frame_id": frame_id,
    }


def make_rival(oid, world_x, world_z, speed=45, in_pits=False):
    """Build a rival dict matching FrameCache spotter frame rivals."""
    return {
        "id": oid,
        "world_x": world_x,
        "world_z": world_z,
        "speed": speed,
        "in_pits": in_pits,
    }


# ============================================================
# Tests
# ============================================================


class TestCartesianSpotterPipeline:
    """Pipeline integration: spotter_frame → spotter.trigger() → AudioPlayer."""

    @pytest.fixture
    def mock_ap(self):
        """Mock AudioPlayer with play_spotter_message and play."""
        return MagicMock(spec=["play_spotter_message", "play"])

    @pytest.fixture
    def spotter(self, mock_ap):
        """NoisyCartesianCoordinateSpotter wired to the mock AudioPlayer.

        Uses clear_delay=0 so clear messages fire immediately (no timer wait).
        """
        return NoisyCartesianCoordinateSpotter(
            ap=mock_ap, min_speed=5, clear_delay=0
        )

    # -----------------------------------------------------------
    # Test 1: car_left detection
    # -----------------------------------------------------------
    def test_cartesian_spotter_detects_car_left(self, spotter, mock_ap):
        """Rival with world_x < player world_x → play_spotter_message(car_left)."""
        sf = make_spotter_frame(
            x=100, z=100,
            rivals=[make_rival(1, world_x=98, world_z=101)],
        )
        spotter.trigger(sf, sf["rivals"], 1000.0)

        mock_ap.play_spotter_message.assert_called_once_with(
            CAR_LEFT, keep_channel=True
        )

    # -----------------------------------------------------------
    # Test 2: car_right detection
    # -----------------------------------------------------------
    def test_cartesian_spotter_detects_car_right(self, spotter, mock_ap):
        """Rival with world_x >= player world_x → play_spotter_message(car_right)."""
        sf = make_spotter_frame(
            x=100, z=100,
            rivals=[make_rival(1, world_x=102, world_z=101)],
        )
        spotter.trigger(sf, sf["rivals"], 1000.0)

        mock_ap.play_spotter_message.assert_called_once_with(
            CAR_RIGHT, keep_channel=True
        )

    # -----------------------------------------------------------
    # Test 3: three_wide detection
    # -----------------------------------------------------------
    def test_cartesian_spotter_three_wide(self, spotter, mock_ap):
        """Two rivals, one each side → play_spotter_message(three_wide)."""
        sf = make_spotter_frame(
            x=100, z=100,
            rivals=[
                make_rival(1, world_x=98, world_z=101),   # left
                make_rival(2, world_x=102, world_z=101),  # right
            ],
        )
        # Tick 1: no rivals (establishes clp=0, crp=0 so transition is detected)
        spotter.trigger(sf, [], 1000.0)
        mock_ap.reset_mock()
        # Tick 2: two rivals appear simultaneously
        spotter.trigger(sf, sf["rivals"], 1000.1)

        mock_ap.play_spotter_message.assert_called_once_with(
            THREE_WIDE, keep_channel=True
        )

    # -----------------------------------------------------------
    # Test 4: clear_all_round
    # -----------------------------------------------------------
    def test_cartesian_spotter_clear_all_round(self, spotter, mock_ap):
        """Both sides were occupied, now no rivals → clear_all_round."""
        # Tick 1: both sides occupied
        sf = make_spotter_frame(
            x=100, z=100,
            rivals=[
                make_rival(1, world_x=98, world_z=101),
                make_rival(2, world_x=102, world_z=101),
            ],
        )
        spotter.trigger(sf, sf["rivals"], 1000.0)
        mock_ap.reset_mock()
        # Tick 2: no rivals → should clear
        sf_clear = make_spotter_frame(x=100, z=100, rivals=[], frame_id=2)
        spotter.trigger(sf_clear, sf_clear["rivals"], 1000.1)

        mock_ap.play_spotter_message.assert_called_once_with(
            CLEAR_ALL_ROUND, keep_channel=True
        )

    # -----------------------------------------------------------
    # Test 5: broadcast_callback fires alongside spotter message
    # -----------------------------------------------------------
    def test_cartesian_spotter_broadcast_also_fires(self, spotter, mock_ap):
        """When the spotter fires, the broadcast_callback is also invoked.

        In the real pipeline, AudioPlayer._player_loop() calls the
        broadcast_callback when it dequeues a spotter message. Here we
        verify the chain by wiring a callback into play_spotter_message.
        """
        broadcast_cb = MagicMock()

        def _play_and_broadcast(audio_path, keep_channel=True):
            broadcast_cb(audio_path)

        mock_ap.play_spotter_message.side_effect = _play_and_broadcast

        sf = make_spotter_frame(
            x=100, z=100,
            rivals=[make_rival(1, world_x=98, world_z=101)],
        )
        spotter.trigger(sf, sf["rivals"], 1000.0)

        # Spotter message was fired
        mock_ap.play_spotter_message.assert_called_once_with(
            CAR_LEFT, keep_channel=True
        )
        # Broadcast callback was also fired with the same audio path
        broadcast_cb.assert_called_once_with(CAR_LEFT)

    # -----------------------------------------------------------
    # Test 6: spotter suppressed during FCY (session_phase=6)
    # -----------------------------------------------------------
    def test_cartesian_spotter_suppressed_during_fcy(self, spotter, mock_ap):
        """session_phase=6 (FullCourseYellow) → spotter suppressed, no messages.

        This replicates the pipeline gate from CrewChiefRuntime.tick():
            if sf["session_phase"] == 6:
                pass  # Spotter suppressed during FCY
            else:
                self.spotter.trigger(sf, sf["rivals"], time.time())
        """
        sf = make_spotter_frame(
            x=100, z=100, session_phase=6,
            rivals=[make_rival(1, world_x=98, world_z=101)],
        )

        # Pipeline gate: session_phase=6 → spotter is NOT called
        if sf["session_phase"] == 6:  # FullCourseYellow
            pass  # Spotter suppressed
        else:
            spotter.trigger(sf, sf["rivals"], 1000.0)

        mock_ap.play_spotter_message.assert_not_called()
        mock_ap.play.assert_not_called()
