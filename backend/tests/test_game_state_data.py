import pytest
from src.models.game_state_data import (
    GameStateData, SessionData, PositionAndMotionData,
    PitData, FlagData, TyreData, CarDamageData,
    EngineData, FuelData, BatteryData, OpponentData,
    PenaltiesData, OvertakingAidsData, FrozenOrderData,
    Rotation, TimingData
)
from src.models.enums import SessionType, SessionPhase, FlagEnum

def test_game_state_data_defaults():
    g = GameStateData()
    assert g.session.session_type == SessionType.UNAVAILABLE
    assert g.motion.world_x == 0.0
    assert not g.pit.in_pitlane
    assert g.fuel.fuel_left == 0.0

def test_session_data_defaults():
    s = SessionData()
    assert s.completed_laps == 0
    assert s.class_position == 0
    assert not s.just_gone_green

def test_motion_speed_kmh():
    m = PositionAndMotionData(car_speed=50.0)
    assert m.speed_kmh == 180.0  # 50 m/s * 3.6

def test_rotation_defaults():
    r = Rotation()
    assert r.yaw == 0.0
    assert r.pitch == 0.0
    assert r.roll == 0.0

def test_battery_normalized_fraction():
    b = BatteryData(percentage=0.5, capacity=100.0)
    assert b.get_normalized() == 0.5  # (0.5 * 100) / 100

def test_battery_normalized_percent():
    b = BatteryData(percentage=85.0)
    assert b.get_normalized() == 85.0

def test_tyre_data_defaults():
    t = TyreData()
    assert t.fl_temp == 0.0
    assert t.fl_wear == 0.0

def test_car_damage_defaults():
    d = CarDamageData()
    assert d.aero == "NONE"
    assert len(d.suspension) == 4

def test_opponent_data_defaults():
    o = OpponentData()
    assert o.driver == ""
    assert not o.in_pits

def test_penalties_defaults():
    p = PenaltiesData()
    assert p.num_outstanding == 0
    assert not p.has_drivethrough

def test_overtaking_aids_defaults():
    oa = OvertakingAidsData()
    assert not oa.drs_enabled
    assert oa.drs_range == -1.0

def test_timing_data():
    t = TimingData()
    t.best_laps["CURRENT"] = 90.5
    assert t.get_best("CURRENT") == 90.5
    assert t.get_best("NONEXISTENT") == -1

def test_game_state_data_set_fields():
    g = GameStateData()
    g.session.driver_name = "Test Driver"
    g.motion.car_speed = 42.0
    g.fuel.fuel_left = 56.7
    g.tyre.fl_temp = 87.3
    assert g.session.driver_name == "Test Driver"
    assert g.fuel.fuel_left == 56.7
    assert g.tyre.fl_temp == 87.3
    assert g.motion.speed_kmh == pytest.approx(151.2)