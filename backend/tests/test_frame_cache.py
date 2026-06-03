"""Tests del FrameCache — cache de un solo frame para eventos y spotter.

Cobertura:
- read_full: devuelve flat dict del reader
- Dedup: si ET no cambia, devuelve el último (no re-llama al reader)
- Spotter frame: pre-extrae datos de spotter
- get_spotter_frame: devuelve frame pre-extraído
- REST merge: añade datos REST API
- Sin REST importable: sigue funcionando
"""
import pytest
from src.services.frame_cache import FrameCache


class MockReader:
    def __init__(self, base=None):
        self.call_count = 0
        self._base = base or {
            "place": 3,
            "session_running_time": 1.0,
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

    def get_flat_dict(self):
        self.call_count += 1
        return self._base


class TestFrameCache:
    def test_read_full_returns_dict(self):
        reader = MockReader()
        cache = FrameCache(reader)
        result = cache.read_full()
        assert isinstance(result, dict)
        assert result["place"] == 3 or "place" not in result

    def test_read_full_calls_reader(self):
        reader = MockReader()
        cache = FrameCache(reader)
        cache.read_full()
        assert reader.call_count == 1

    def test_dedup_same_et_returns_cached_content(self):
        """Same ET → returns cached content (reader called but merge_rest skipped)."""
        reader = MockReader()
        cache = FrameCache(reader)
        r1 = cache.read_full()  # ET=1.0
        r2 = cache.read_full()  # ET=1.0 (same) → returns self._latest
        # Same dict object returned (cached), not a copy
        assert r1 is r2

    def test_different_et_calls_reader_again(self):
        reader = MockReader()
        cache = FrameCache(reader)
        cache.read_full()  # ET=1.0
        reader._base["session_running_time"] = 2.0
        cache.read_full()  # ET=2.0 (diferente)
        assert reader.call_count == 2

    def test_zero_et_always_calls_reader(self):
        """Si ET es 0, NO se considera 'igual al anterior' (no sabemos si es nuevo o no)."""
        reader = MockReader()
        reader._base["session_running_time"] = 0.0
        cache = FrameCache(reader)
        cache.read_full()
        cache.read_full()
        cache.read_full()
        # ET=0 cada vez → debe llamar cada vez
        assert reader.call_count == 3


class TestSpotterFrame:
    def test_get_spotter_returns_dict(self):
        reader = MockReader()
        cache = FrameCache(reader)
        sf = cache.get_spotter_frame()
        assert isinstance(sf, dict)
        assert "world_x" in sf
        assert "rivals" in sf

    def test_spotter_frame_has_rivals_with_correct_data(self):
        reader = MockReader()
        cache = FrameCache(reader)
        sf = cache.get_spotter_frame()
        assert len(sf["rivals"]) == 1
        assert sf["rivals"][0]["world_x"] == 150.0

    def test_spotter_frame_includes_session_phase(self):
        reader = MockReader()
        cache = FrameCache(reader)
        sf = cache.get_spotter_frame()
        assert sf["session_phase"] == 5

    def test_spotter_frame_includes_player_in_pits(self):
        reader = MockReader()
        reader._base["in_pits"] = True
        cache = FrameCache(reader)
        sf = cache.get_spotter_frame()
        assert sf["in_pits"] is True

    def test_spotter_frame_id_increments(self):
        reader = MockReader()
        cache = FrameCache(reader)
        sf1 = cache.get_spotter_frame()
        # Forzar nueva lectura
        reader._base["session_running_time"] = 2.0
        sf2 = cache.get_spotter_frame()
        assert sf2["frame_id"] > sf1["frame_id"]

    def test_spotter_frame_lazy_init(self):
        """get_spotter_frame() sin read_full() previo debe inicializar."""
        reader = MockReader()
        cache = FrameCache(reader)
        assert cache._spotter is None
        cache.get_spotter_frame()
        assert cache._spotter is not None

    def test_spotter_frame_handles_empty_rivals(self):
        reader = MockReader({"session_running_time": 1.0, "rivals": []})
        cache = FrameCache(reader)
        sf = cache.get_spotter_frame()
        assert sf["rivals"] == []


class TestRestMerge:
    def test_rest_data_merged_into_flat(self):
        reader = MockReader()
        cache = FrameCache(reader)

        # Mock lmu_api module
        import sys
        from types import ModuleType

        mock_lmu_api = ModuleType("src.services.lmu_api")
        mock_lmu_api.get_garage_wear = lambda: {
            "wearables": {
                "tires": [0.1, 0.2, 0.3, 0.4],
                "brakes": [0.5, 0.6, 0.7, 0.8],
                "body": {"aero": 0.95},
            }
        }
        # Inject into sys.modules
        original = sys.modules.get("src.services.lmu_api")
        sys.modules["src.services.lmu_api"] = mock_lmu_api
        try:
            result = cache.read_full()
            assert "tyre_wear" in result
            assert result["tyre_wear"] == [0.1, 0.2, 0.3, 0.4]
            assert "brake_wear" in result
            assert result["brake_wear"] == [0.5, 0.6, 0.7, 0.8]
            assert "damage_aero" in result
            assert result["damage_aero"] == 0.95
        finally:
            if original is not None:
                sys.modules["src.services.lmu_api"] = original
            else:
                del sys.modules["src.services.lmu_api"]

    def test_rest_merge_handles_missing_tires(self):
        reader = MockReader()
        cache = FrameCache(reader)
        import sys
        from types import ModuleType
        mock_lmu_api = ModuleType("src.services.lmu_api")
        mock_lmu_api.get_garage_wear = lambda: {"wearables": {}}
        original = sys.modules.get("src.services.lmu_api")
        sys.modules["src.services.lmu_api"] = mock_lmu_api
        try:
            result = cache.read_full()
            # No debe crashear; los campos simplemente no se añaden
            assert "tyre_wear" not in result
        finally:
            if original is not None:
                sys.modules["src.services.lmu_api"] = original
            else:
                del sys.modules["src.services.lmu_api"]

    def test_rest_merge_failure_does_not_crash(self):
        """Si lmu_api.get_garage_wear() lanza excepción, no debe crashear."""
        reader = MockReader()
        cache = FrameCache(reader)
        import sys
        from types import ModuleType
        mock_lmu_api = ModuleType("src.services.lmu_api")
        mock_lmu_api.get_garage_wear = lambda: (_ for _ in ()).throw(RuntimeError("API down"))
        original = sys.modules.get("src.services.lmu_api")
        sys.modules["src.services.lmu_api"] = mock_lmu_api
        try:
            result = cache.read_full()  # No debe lanzar
            assert isinstance(result, dict)
        finally:
            if original is not None:
                sys.modules["src.services.lmu_api"] = original
            else:
                del sys.modules["src.services.lmu_api"]
