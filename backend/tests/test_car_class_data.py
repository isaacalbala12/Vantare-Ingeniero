import pytest
from src.data.car_class_data import (
    CarClassEnum, CarClass, get_car_class,
    TyreTemp, BrakeTemp, DamageLevel,
    get_tyre_thresholds, get_brake_thresholds,
    TYRE_TEMP_THRESHOLDS, BRAKE_TEMP_THRESHOLDS
)


def test_car_class_enum_values():
    assert CarClassEnum.GT3.value == "GT3"
    assert CarClassEnum.HYPER_CAR.value == "HYPER_CAR"


def test_get_car_class_gt3():
    cc = get_car_class(CarClassEnum.GT3)
    assert cc.brake_type == "Ceramic"
    assert cc.max_safe_oil == 135.0
    assert not cc.is_battery_powered


def test_get_car_class_hypercar():
    cc = get_car_class(CarClassEnum.HYPER_CAR)
    assert cc.brake_type == "Carbon"
    assert cc.is_battery_powered
    assert cc.is_drs_capable


def test_get_car_class_unknown_fallback():
    cc = get_car_class(CarClassEnum.UNKNOWN_RACE)
    assert cc.enabled_message_types == ["FUEL"]


def test_tyre_temp_thresholds_soft():
    th = get_tyre_thresholds("Soft")
    assert len(th) == 4
    assert th[0].name == TyreTemp.COLD
    assert th[1].name == TyreTemp.WARM


def test_tyre_temp_thresholds_unknown_fallback():
    th = get_tyre_thresholds("Nonexistent")
    assert th[0].name == TyreTemp.COLD


def test_brake_thresholds_carbon():
    th = get_brake_thresholds("Carbon")
    assert th[0].name == BrakeTemp.COLD
    assert th[0].upper == 400.0


def test_damage_level_values():
    assert DamageLevel.NONE.value == 1
    assert DamageLevel.DESTROYED.value == 5


def test_car_class_is_refueling():
    cc = get_car_class(CarClassEnum.GT3)
    assert cc.is_refueling_allowed
    cc2 = get_car_class(CarClassEnum.FORMULA_E)
    assert not cc2.is_refueling_allowed
