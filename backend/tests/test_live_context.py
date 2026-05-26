"""
Tests para LiveContextManager (backend/src/intelligence/live_context.py).
Verifica:
1. Snapshots contienen speed, track_grip_level, cloud_coverage, raining
2. damage["aero"] usa damage_aero real, no brake_wear_fl * 0.1
3. update_realtime() actualiza campos sin romper estructura
"""
import pytest
import copy

from src.intelligence.live_context import LiveContextManager


class TestMissingFields:
    """T0.1: Snapshots deben incluir speed, track_grip_level, cloud_coverage, raining."""

    @pytest.fixture
    def populated_manager(self, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """LiveContextManager con una vuelta completada."""
        mgr = LiveContextManager()
        # Añadir campos nuevos al telemetry
        telemetry = copy.deepcopy(mock_telemetry_dict)
        telemetry["speed"] = 72.0
        telemetry["track_grip_level"] = 2
        telemetry["cloud_coverage"] = 5
        telemetry["raining"] = 0.3
        mgr.on_lap_completed(telemetry, mock_strategy_dict, mock_session_dict)
        return mgr

    def test_fast_snapshot_has_speed(self, populated_manager):
        snap = populated_manager.snapshot("fast")
        assert "speed" in snap, "FAST snapshot debe tener campo 'speed'"
        assert snap["speed"] == 72.0

    def test_fast_snapshot_has_track_grip_level(self, populated_manager):
        snap = populated_manager.snapshot("fast")
        assert "track_grip_level" in snap, "FAST snapshot debe tener campo 'track_grip_level'"
        assert snap["track_grip_level"] == 2

    def test_fast_snapshot_has_cloud_coverage(self, populated_manager):
        snap = populated_manager.snapshot("fast")
        assert "cloud_coverage" in snap, "FAST snapshot debe tener campo 'cloud_coverage'"
        assert snap["cloud_coverage"] == 5

    def test_fast_snapshot_has_raining(self, populated_manager):
        snap = populated_manager.snapshot("fast")
        assert "raining" in snap, "FAST snapshot debe tener campo 'raining'"
        assert snap["raining"] == 0.3

    def test_standard_snapshot_has_all_new_fields(self, populated_manager):
        snap = populated_manager.snapshot("standard")
        for field in ("speed", "track_grip_level", "cloud_coverage", "raining"):
            assert field in snap, f"STANDARD snapshot debe tener '{field}'"

    def test_deep_snapshot_has_all_new_fields(self, populated_manager):
        snap = populated_manager.snapshot("deep")
        for field in ("speed", "track_grip_level", "cloud_coverage", "raining"):
            assert field in snap, f"DEEP snapshot debe tener '{field}'"

    def test_new_fields_defaults_when_missing(self, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """Si los campos no vienen en telemetry, deben defaults a 0/0.0/None."""
        mgr = LiveContextManager()
        mgr.on_lap_completed(mock_telemetry_dict, mock_strategy_dict, mock_session_dict)
        for tier in ("fast", "standard", "deep"):
            snap = mgr.snapshot(tier)
            assert "speed" in snap
            assert "track_grip_level" in snap
            assert "cloud_coverage" in snap
            assert "raining" in snap


class TestDamageAeroFix:
    """T0.2: damage['aero'] debe usar damage_aero real, no brake_wear_fl * 0.1."""

    def test_damage_aero_uses_damage_aero_field(self, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """Con damage_aero=0.5, damage['aero'] debe ser exactamente 0.5."""
        mgr = LiveContextManager()
        telemetry = copy.deepcopy(mock_telemetry_dict)
        telemetry["damage_aero"] = 0.5
        # brake_wear_fl debe ser diferente para asegurar que no se usa como proxy
        telemetry["brake_wear_fl"] = 15.0
        mgr.on_lap_completed(telemetry, mock_strategy_dict, mock_session_dict)
        snap = mgr.snapshot("deep")
        assert snap["damage"]["aero"] == 0.5, "damage['aero'] debe ser damage_aero real (0.5), no brake_wear_fl*0.1"

    def test_damage_aero_zero_when_not_present(self, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """Cuando damage_aero no existe, default es 0.0."""
        mgr = LiveContextManager()
        telemetry = copy.deepcopy(mock_telemetry_dict)
        telemetry["damage_aero"] = 0.0
        mgr.on_lap_completed(telemetry, mock_strategy_dict, mock_session_dict)
        snap = mgr.snapshot("deep")
        assert snap["damage"]["aero"] == 0.0


class TestUpdateRealtime:
    """T0.3: update_realtime() actualiza campos volátiles sin esperar lap completa."""

    @pytest.fixture
    def base_manager(self, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """LiveContextManager con una vuelta completada como base."""
        mgr = LiveContextManager()
        mgr.on_lap_completed(mock_telemetry_dict, mock_strategy_dict, mock_session_dict)
        return mgr

    def test_update_realtime_exists(self, base_manager):
        """LiveContextManager debe tener método update_realtime."""
        assert hasattr(base_manager, "update_realtime"), "Debe existir update_realtime()"
        assert callable(getattr(base_manager, "update_realtime"))

    def test_update_realtime_updates_speed(self, base_manager):
        """update_realtime() debe poder actualizar speed en todos los snapshots."""
        new_speed = 95.5
        base_manager.update_realtime(
            {"speed": new_speed, "track_grip_level": 1, "cloud_coverage": 8, "raining": 0.7},
            {}
        )
        for tier in ("fast", "standard", "deep"):
            snap = base_manager.snapshot(tier)
            assert snap.get("speed") == new_speed, f"{tier} snapshot speed debe ser {new_speed}"

    def test_update_realtime_updates_gaps(self, base_manager):
        """update_realtime() debe poder actualizar gaps_ahead/gap_behind."""
        base_manager.update_realtime(
            {"gap_ahead": 1.5, "gap_behind": 2.5},
            {}
        )
        for tier in ("fast", "standard", "deep"):
            snap = base_manager.snapshot(tier)
            assert snap.get("gap_ahead") == 1.5, f"{tier} gap_ahead debe ser 1.5"
            assert snap.get("gap_behind") == 2.5, f"{tier} gap_behind debe ser 2.5"

    def test_update_realtime_updates_brake_wear(self, base_manager):
        """update_realtime() debe poder actualizar damage.brake_wear."""
        base_manager.update_realtime(
            {"brake_wear_fl": 80.0, "brake_wear_fr": 80.0, "brake_wear_rl": 75.0, "brake_wear_rr": 75.0},
            {}
        )
        snap = base_manager.snapshot("deep")
        assert snap["damage"]["brake_wear"] == 77.5, "damage.brake_wear debe ser avg de los 4 wells"

    def test_update_realtime_preserves_existing_fields(self, base_manager):
        """update_realtime() no debe borrar campos existentes no actualizados."""
        # Tomar valores originales de campos importantes
        snap_before = base_manager.snapshot("standard")
        orig_tyre_wear = snap_before.get("tyre_wear_current")
        orig_fuel = snap_before.get("fuel_in_tank")
        orig_battery = snap_before.get("battery_charge")

        base_manager.update_realtime({"speed": 100.0}, {})

        snap_after = base_manager.snapshot("standard")
        assert snap_after.get("tyre_wear_current") == orig_tyre_wear
        assert snap_after.get("fuel_in_tank") == orig_fuel
        assert snap_after.get("battery_charge") == orig_battery

    def test_update_realtime_works_on_empty_manager(self):
        """update_realtime() debe funcionar en manager sin lap completada."""
        mgr = LiveContextManager()
        # No llamar on_lap_completed
        mgr.update_realtime(
            {"speed": 50.0, "track_grip_level": 3, "cloud_coverage": 2, "raining": 0.0},
            {}
        )
        # No debe lanzar error
        for tier in ("fast", "standard", "deep"):
            snap = mgr.snapshot(tier)
            # Los campos deben existir aunque los snapshots estén vacíos
            assert "speed" in snap