import pytest
from src.services.frame_cache import FrameCache


class MockReader:
    def __init__(self):
        self._call_count = 0

    def get_flat_dict(self):
        self._call_count += 1
        return {
            "session_running_time": float(self._call_count),
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
            "place": 3,
            "lap_number": 5,
        }


def test_read_full_returns_dict():
    cache = FrameCache(MockReader())
    result = cache.read_full()
    assert isinstance(result, dict)
    assert result["place"] == 3


def test_get_spotter_frame():
    cache = FrameCache(MockReader())
    sf = cache.get_spotter_frame()
    assert "world_x" in sf
    assert "rivals" in sf
    assert sf["session_phase"] == 5


def test_spotter_frame_rivals():
    cache = FrameCache(MockReader())
    sf = cache.get_spotter_frame()
    assert len(sf["rivals"]) == 1
    assert sf["rivals"][0]["world_x"] == 150.0


def test_frame_id_increments():
    cache = FrameCache(MockReader())
    sf1 = cache.get_spotter_frame()
    sf2 = cache.get_spotter_frame()
    assert sf2["_frame_id"] >= sf1["_frame_id"]
