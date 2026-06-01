"""Tests del GameStateData y todos sus dataclasses.

Cobertura:
- Creación por defecto de cada dataclass
- Propiedades computadas: speed_kmh, get_normalized
- Mutabilidad de listas/dict por defecto
"""
import pytest
from src.models.game_state_data import (
    GameStateData, SessionData, PositionAndMotionData,
    PitData, FlagData, TyreData, CarDamageData,
    EngineData, FuelData, BatteryData, OpponentData,
    PenaltiesData, OvertakingAidsData, FrozenOrderData,
    Rotation, TimingData,
)
from src.models.enums import (
    SessionType, SessionPhase, FlagEnum,
    FullCourseYellowPhase, PitWindow, FrozenOrderPhase,
    FrozenOrderAction,
)


class TestGameStateDataDefaults:
    def test_all_subobjects_present(self):
        g = GameStateData()
        assert g.session is not None
        assert g.motion is not None
        assert g.pit is not None
        assert g.flag is not None
        assert g.tyre is not None
        assert g.damage is not None
        assert g.engine is not None
        assert g.fuel is not None
        assert g.battery is not None
        assert g.overtaking is not None
        assert g.penalties is not None
        assert g.frozen_order is not None
        assert g.timing is not None

    def test_opponents_is_empty_dict(self):
        g = GameStateData()
        assert g.opponents == {}

    def test_mutable_defaults_independent(self):
        """Dos GameStateData no deben compartir listas/dicts."""
        g1 = GameStateData()
        g2 = GameStateData()
        g1.opponents["x"] = OpponentData()
        assert "x" not in g2.opponents

    def test_timing_dict_independent(self):
        g1 = GameStateData()
        g2 = GameStateData()
        g1.timing.best_laps["x"] = 90.0
        assert "x" not in g2.timing.best_laps


class TestMotion:
    def test_speed_kmh_conversion(self):
        m = PositionAndMotionData(car_speed=50.0)
        assert m.speed_kmh == 180.0  # 50 m/s * 3.6

    def test_speed_kmh_zero(self):
        m = PositionAndMotionData()
        assert m.speed_kmh == 0.0

    def test_world_coordinates_default(self):
        m = PositionAndMotionData()
        assert m.world_x == 0.0
        assert m.world_y == 0.0
        assert m.world_z == 0.0

    def test_orientation_default(self):
        m = PositionAndMotionData()
        assert m.orientation.yaw == 0.0


class TestBattery:
    def test_fraction_with_capacity(self):
        b = BatteryData(percentage=0.5, capacity=100.0)
        # 0.5 (fracción) * 100 / 100 (capacity) = 0.5
        assert b.get_normalized() == 0.5

    def test_percent_input(self):
        b = BatteryData(percentage=85.0)
        assert b.get_normalized() == 85.0

    def test_zero_capacity_falls_back(self):
        b = BatteryData(percentage=0.7, capacity=0.0)
        # Sin capacity, multiplica por 100
        assert b.get_normalized() == 70.0

    def test_large_value_passthrough(self):
        """Si el valor es >100, no intenta normalizar."""
        b = BatteryData(percentage=255.0)
        assert b.get_normalized() == 255.0


class TestTyre:
    def test_all_corners_independent(self):
        t = TyreData()
        t.fl_temp = 80
        t.fr_temp = 82
        assert t.fl_temp != t.fr_temp

    def test_default_zero(self):
        t = TyreData()
        assert t.fl_temp == 0.0
        assert t.rr_wear == 0.0


class TestDamage:
    def test_default_damage_state_none(self):
        d = CarDamageData()
        assert d.aero == "NONE"
        assert d.engine == "NONE"
        assert d.transmission == "NONE"

    def test_suspension_4_corners(self):
        d = CarDamageData()
        assert len(d.suspension) == 4
        assert len(d.brakes) == 4


class TestOpponent:
    def test_default(self):
        o = OpponentData()
        assert o.driver == ""
        assert o.car_number == "-1"
        assert o.in_pits is False
        assert o.laps == 0


class TestPenalties:
    def test_default(self):
        p = PenaltiesData()
        assert p.num_outstanding == 0
        assert p.max_incident == 0
        assert p.is_off_track is False


class TestTiming:
    def test_get_best_existing(self):
        t = TimingData()
        t.best_laps["CURRENT"] = 90.5
        assert t.get_best("CURRENT") == 90.5

    def test_get_best_missing(self):
        t = TimingData()
        assert t.get_best("NONE") == -1.0


class TestFrozenOrder:
    def test_default(self):
        fo = FrozenOrderData()
        assert fo.phase == FrozenOrderPhase.NONE
        assert fo.position == -1
