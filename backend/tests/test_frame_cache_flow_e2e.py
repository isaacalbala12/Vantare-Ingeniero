"""E2E tests for FrameCache — verifies dedup is real and spotter frame is real.

Uses a custom FakeReader (NOT unittest.mock) to exercise the real FrameCache
code path end-to-end. The reader interface matches FrameCache's actual
contract: ``get_flat_dict()`` returns a flat dict containing
``session_running_time`` and other telemetry fields (see
``src/services/lmu_reader.py`` for the real reader).

Cobertura:
1. Dedup is real: same ``session_running_time`` → reader called once,
   second call returns cached dict
2. Different ``session_running_time`` → reader called twice, fresh data
3. Zero ``session_running_time`` bypasses cache (reader always called)
4. Spotter frame: returns dict with ``rivals``, ``session_phase``,
   ``player_in_pits`` (``in_pits``)
5. ``frame_id`` starts at 1 and increments per call
6. ``get_spotter_frame()`` lazy init (reads from reader on first call)
7. REST merge: REST data merged into flat dict
8. Missing REST data doesn't crash
"""
import sys
from types import ModuleType
from typing import Any, List, Optional

import pytest

from src.services.frame_cache import FrameCache


class FakeReader:
    """Real fake reader — records calls, returns varying data per call.

    No ``unittest.mock`` involved. This class IS the reader. It matches
    FrameCache's expected interface (``get_flat_dict()``) and tracks
    invocations for assertion.

    Args:
        return_value: Static dict returned on every call (when
            ``varying_data`` is None).
        varying_data: List of dicts returned in order. Useful when the
            test needs the reader to return distinct data per call so we
            can prove whether the result came from the reader or the
            cache.
    """

    def __init__(
        self,
        return_value: Optional[dict] = None,
        varying_data: Optional[List[dict]] = None,
    ):
        self._return_value = return_value
        self._varying_data: List[dict] = list(varying_data) if varying_data else []
        self._index = 0
        self.call_count = 0

    def get_flat_dict(self) -> dict:
        """FrameCache calls this — returns a flat telemetry dict."""
        self.call_count += 1
        if self._varying_data:
            idx = min(self._index, len(self._varying_data) - 1)
            data = self._varying_data[idx]
            self._index += 1
            return data
        return self._return_value


def _frame(et: float = 10.0, **overrides: Any) -> dict:
    """Build a realistic flat dict with all required fields.

    Defaults match the real telemetry shape: ET, session_phase, world
    coords, speed, in_pits, and one rival entry.
    """
    data: dict = {
        "session_running_time": et,
        "place": 3,
        "session_phase": 5,
        "world_x": 100.0,
        "world_z": 200.0,
        "rotation_yaw": 0.5,
        "speed_ms": 50.0,
        "in_pits": False,
        "rivals": [
            {
                "driver_raw_name": "Alice",
                "world_x": 150.0,
                "world_z": 210.0,
                "speed": 48.0,
                "in_pits": False,
            }
        ],
    }
    data.update(overrides)
    return data


def _install_mock_lmu_api(get_garage_wear_fn) -> None:
    """Inject a fake ``src.services.lmu_api`` module into ``sys.modules``.

    FrameCache imports ``get_garage_wear`` lazily inside ``_merge_rest``,
    so a per-test injection is sufficient (and avoids mocking the import
    system at collection time).
    """
    mock_lmu_api = ModuleType("src.services.lmu_api")
    mock_lmu_api.get_garage_wear = get_garage_wear_fn
    sys.modules["src.services.lmu_api"] = mock_lmu_api


def _restore_lmu_api(original) -> None:
    if original is not None:
        sys.modules["src.services.lmu_api"] = original
    else:
        sys.modules.pop("src.services.lmu_api", None)


# ──────────────────────────────────────────────────────────────
# 1. Dedup is real
# ──────────────────────────────────────────────────────────────
class TestDedupIsReal:
    def test_same_elapsed_time_reader_called_once(self):
        """Same ET → reader called ONCE, second call returns cached dict.

        If the reader were called twice, the second ``varying_data``
        entry (``speed_ms=200.0``) would surface in ``result2``. The
        assertion that ``result2["speed_ms"] == 100.0`` proves the
        cached dict was returned, and ``call_count == 1`` proves the
        reader was not invoked on the second call.
        """
        reader = FakeReader(
            varying_data=[
                _frame(et=10.0, speed_ms=100.0),
                _frame(et=10.0, speed_ms=200.0),  # would leak if reader called
            ]
        )
        cache = FrameCache(reader=reader)

        result1 = cache.read_full()
        # Pass known elapsed_time to trigger lightweight dedup — skips reader call
        result2 = cache.read_full(elapsed_time=10.0)

        # Dedup is real: reader called only once
        assert reader.call_count == 1, (
            f"Expected 1 reader call (dedup), got {reader.call_count}. "
            "FrameCache is calling the reader on every read_full() even "
            "when session_running_time is unchanged — dedup is incomplete."
        )
        # Second result is the cached first result, not the fresh reader data
        assert result1["speed_ms"] == 100.0
        assert result2["speed_ms"] == 100.0, (
            "Second call returned fresh reader data (speed_ms=200.0) "
            "instead of cached first-call data (speed_ms=100.0)."
        )

    def test_different_elapsed_time_reader_called_twice(self):
        """Different ET → reader called twice, fresh data each time."""
        reader = FakeReader(
            varying_data=[
                _frame(et=10.0, speed_ms=100.0),
                _frame(et=15.0, speed_ms=200.0),
            ]
        )
        cache = FrameCache(reader=reader)

        result1 = cache.read_full()
        result2 = cache.read_full()

        assert reader.call_count == 2
        # Fresh data on each call
        assert result1["session_running_time"] == 10.0
        assert result1["speed_ms"] == 100.0
        assert result2["session_running_time"] == 15.0
        assert result2["speed_ms"] == 200.0


# ──────────────────────────────────────────────────────────────
# 2. Zero elapsed_time bypasses cache
# ──────────────────────────────────────────────────────────────
class TestZeroElapsedTimeBypass:
    def test_zero_et_always_calls_reader(self):
        """ET=0 bypasses dedup — reader called every time (ET=0 is
        ambiguous: could be 'not yet started' or 'stale')."""
        reader = FakeReader(
            varying_data=[
                _frame(et=0.0),
                _frame(et=0.0),
                _frame(et=0.0),
            ]
        )
        cache = FrameCache(reader=reader)

        cache.read_full()
        cache.read_full()
        cache.read_full()

        assert reader.call_count == 3, (
            f"ET=0 should always call reader (3 calls expected, "
            f"got {reader.call_count})"
        )


# ──────────────────────────────────────────────────────────────
# 3. Spotter frame
# ──────────────────────────────────────────────────────────────
class TestSpotterFrame:
    def test_spotter_frame_has_rivals_session_phase_player_in_pits(self):
        """``get_spotter_frame()`` returns dict with ``rivals`` list,
        ``session_phase``, and ``player_in_pits`` (key: ``in_pits``)."""
        reader = FakeReader(
            return_value=_frame(et=10.0, session_phase=5, in_pits=False)
        )
        cache = FrameCache(reader=reader)

        sf = cache.get_spotter_frame()

        # Required fields present
        assert isinstance(sf, dict)
        assert "rivals" in sf
        assert isinstance(sf["rivals"], list)
        assert "session_phase" in sf
        assert "in_pits" in sf  # player_in_pits
        # Values correct
        assert sf["session_phase"] == 5
        assert sf["in_pits"] is False
        # Rival data preserved
        assert len(sf["rivals"]) == 1
        assert sf["rivals"][0]["world_x"] == 150.0
        assert sf["rivals"][0]["world_z"] == 210.0

    def test_frame_id_starts_at_1_and_increments(self):
        """``frame_id`` starts at 1 and increments per call to
        ``get_spotter_frame()`` (1, 2, 3, ...)."""
        reader = FakeReader(
            varying_data=[
                _frame(et=10.0),
                _frame(et=20.0),
                _frame(et=30.0),
            ]
        )
        cache = FrameCache(reader=reader)

        sf1 = cache.get_spotter_frame()
        sf2 = cache.get_spotter_frame()
        sf3 = cache.get_spotter_frame()

        assert sf1["frame_id"] == 1, (
            f"First frame_id should be 1, got {sf1['frame_id']}"
        )
        assert sf2["frame_id"] == 2, (
            f"Second frame_id should be 2, got {sf2['frame_id']}"
        )
        assert sf3["frame_id"] == 3, (
            f"Third frame_id should be 3, got {sf3['frame_id']}"
        )

    def test_spotter_frame_lazy_init(self):
        """``get_spotter_frame()`` without prior ``read_full()`` — reads
        from reader first, initializes ``_spotter`` on first call."""
        reader = FakeReader(return_value=_frame(et=10.0))
        cache = FrameCache(reader=reader)

        # No frame yet
        assert cache._spotter is None
        assert reader.call_count == 0

        sf = cache.get_spotter_frame()

        # Spotter initialized
        assert cache._spotter is not None
        assert sf is cache._spotter
        # Reader was called exactly once (lazy init triggered a read)
        assert reader.call_count == 1


# ──────────────────────────────────────────────────────────────
# 4. REST merge
# ──────────────────────────────────────────────────────────────
class TestRestMerge:
    def test_rest_data_merged_into_flat_dict(self):
        """REST data (tire wear, brake wear, aero damage) is merged into
        the flat dict returned by ``read_full()``."""
        reader = FakeReader(return_value=_frame(et=10.0))
        cache = FrameCache(reader=reader)

        original = sys.modules.get("src.services.lmu_api")
        _install_mock_lmu_api(
            lambda: {
                "wearables": {
                    "tires": [0.1, 0.2, 0.3, 0.4],
                    "brakes": [0.5, 0.6, 0.7, 0.8],
                    "body": {"aero": 0.95},
                }
            }
        )
        try:
            result = cache.read_full()

            # Tire pressures updated
            assert "tyre_wear" in result
            assert result["tyre_wear"] == [0.1, 0.2, 0.3, 0.4]
            # Brake wear
            assert "brake_wear" in result
            assert result["brake_wear"] == [0.5, 0.6, 0.7, 0.8]
            # Aero damage
            assert "damage_aero" in result
            assert result["damage_aero"] == 0.95
        finally:
            _restore_lmu_api(original)

    def test_missing_rest_data_does_not_crash(self):
        """Missing REST fields (empty dict) — ``read_full()`` returns
        normally, no crash, no keys added."""
        reader = FakeReader(return_value=_frame(et=10.0))
        cache = FrameCache(reader=reader)

        original = sys.modules.get("src.services.lmu_api")
        _install_mock_lmu_api(lambda: {})  # empty
        try:
            result = cache.read_full()

            assert isinstance(result, dict)
            # Missing fields simply not added
            assert "tyre_wear" not in result
            assert "brake_wear" not in result
            assert "damage_aero" not in result
            # Base fields still present
            assert result["session_running_time"] == 10.0
        finally:
            _restore_lmu_api(original)
