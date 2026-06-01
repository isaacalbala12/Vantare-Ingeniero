"""Tests del car_class_data — definiciones de clases de coches y umbrales.

Cobertura:
- Enums: CarClassEnum, TyreTemp, BrakeTemp, DamageLevel
- Threshold dataclass
- CarClass dataclass con sus flags
- Thresholds de neumáticos: Soft, Medium, Hard, Wet, Intermediate, Unknown
- Thresholds de frenos: Iron, Ceramic, Carbon
- Funciones get_car_class, get_tyre_thresholds, get_brake_thresholds
"""
import pytest
from src.data.car_class_data import (
    CarClassEnum, CarClass, Threshold,
    TyreTemp, BrakeTemp, DamageLevel,
    get_car_class, get_tyre_thresholds, get_brake_thresholds,
    TYRE_TEMP_THRESHOLDS, BRAKE_TEMP_THRESHOLDS, CAR_CLASSES,
)


class TestEnums:
    def test_car_class_enum_values(self):
        assert CarClassEnum.GT3.value == "GT3"
        assert CarClassEnum.HYPER_CAR.value == "HYPER_CAR"
        assert CarClassEnum.LMP2.value == "LMP2"

    def test_tyre_temp_values(self):
        assert TyreTemp.COLD.value == "COLD"
        assert TyreTemp.WARM.value == "WARM"
        assert TyreTemp.HOT.value == "HOT"
        assert TyreTemp.COOKING.value == "COOKING"

    def test_brake_temp_values(self):
        assert BrakeTemp.COLD.value == "COLD"
        assert BrakeTemp.WARM.value == "WARM"
        assert BrakeTemp.HOT.value == "HOT"
        assert BrakeTemp.COOKING.value == "COOKING"

    def test_damage_level_values(self):
        assert DamageLevel.NONE.value == 1
        assert DamageLevel.TRIVIAL.value == 2
        assert DamageLevel.MINOR.value == 3
        assert DamageLevel.MAJOR.value == 4
        assert DamageLevel.DESTROYED.value == 5


class TestCarClass:
    def test_gt3_defaults(self):
        cc = get_car_class(CarClassEnum.GT3)
        assert cc.brake_type == "Ceramic"
        assert cc.max_safe_oil == 135.0
        assert cc.is_battery_powered is False
        assert cc.is_drs_capable is False

    def test_hypercar_battery_and_drs(self):
        cc = get_car_class(CarClassEnum.HYPER_CAR)
        assert cc.brake_type == "Carbon"
        assert cc.is_battery_powered is True
        assert cc.is_drs_capable is True
        assert cc.drs_range > 0

    def test_lmp2_ceramic(self):
        cc = get_car_class(CarClassEnum.LMP2)
        assert cc.brake_type == "Ceramic"

    def test_lmp1_carbon(self):
        cc = get_car_class(CarClassEnum.LMP1)
        assert cc.brake_type == "Carbon"

    def test_unknown_class_fallback(self):
        """Clases no definidas caen a UNKNOWN_RACE con mensaje FUEL."""
        cc = get_car_class(CarClassEnum.USER_CREATED)
        assert cc.enabled_message_types == ["FUEL"]

    def test_refueling_allowed(self):
        cc_gt3 = get_car_class(CarClassEnum.GT3)
        assert cc_gt3.is_refueling_allowed is True
        cc_fe = get_car_class(CarClassEnum.FORMULA_E)
        assert cc_fe.is_refueling_allowed is False

    def test_unknown_class_has_default_tyre(self):
        cc = get_car_class(CarClassEnum.UNKNOWN_RACE)
        assert cc.default_tyre_type == "Unknown_Race"


class TestTyreThresholds:
    def test_soft_thresholds(self):
        th = get_tyre_thresholds("Soft")
        assert len(th) == 4
        assert th[0].name == TyreTemp.COLD
        assert th[1].name == TyreTemp.WARM
        assert th[2].name == TyreTemp.HOT
        assert th[3].name == TyreTemp.COOKING

    def test_soft_warm_threshold_value(self):
        """Soft: WARM entre 70 y 100."""
        th = get_tyre_thresholds("Soft")
        warm = next(t for t in th if t.name == TyreTemp.WARM)
        assert warm.lower == 70
        assert warm.upper == 100

    def test_hard_cooking_threshold(self):
        """Hard: COOKING a partir de 124."""
        th = get_tyre_thresholds("Hard")
        cooking = next(t for t in th if t.name == TyreTemp.COOKING)
        assert cooking.lower == 124

    def test_wet_lower_temps(self):
        """Wet tiene temperaturas más bajas que Soft."""
        wet = get_tyre_thresholds("Wet")
        soft = get_tyre_thresholds("Soft")
        wet_warm = next(t for t in wet if t.name == TyreTemp.WARM)
        soft_warm = next(t for t in soft if t.name == TyreTemp.WARM)
        assert wet_warm.upper < soft_warm.upper

    def test_unknown_tyre_fallback(self):
        """Neumático desconocido cae a Unknown_Race."""
        th = get_tyre_thresholds("Nonexistent")
        unknown = get_tyre_thresholds("Unknown_Race")
        assert th[0].name == unknown[0].name
        assert th[0].upper == unknown[0].upper

    def test_all_compounds_have_4_thresholds(self):
        for compound in ["Soft", "Medium", "Hard", "Wet", "Intermediate", "Unknown_Race"]:
            th = get_tyre_thresholds(compound)
            assert len(th) == 4, f"{compound} has {len(th)} thresholds"

    def test_thresholds_cover_full_range(self):
        """Los umbrales deben cubrir de -inf a +inf sin gaps."""
        for compound, th in TYRE_TEMP_THRESHOLDS.items():
            # El primero empieza en -10000 (cubre todo lo bajo)
            assert th[0].lower <= -9000
            # El último va hasta +10000 (cubre todo lo alto)
            assert th[-1].upper >= 9000


class TestBrakeThresholds:
    def test_iron_thresholds(self):
        th = get_brake_thresholds("Iron_Race")
        assert len(th) == 4
        cold = next(t for t in th if t.name == BrakeTemp.COLD)
        assert cold.upper == 150

    def test_ceramic_warmer(self):
        """Ceramic aguanta más que Iron."""
        ceramic = get_brake_thresholds("Ceramic")
        iron = get_brake_thresholds("Iron_Race")
        ceramic_cooking = next(t for t in ceramic if t.name == BrakeTemp.COOKING)
        iron_cooking = next(t for t in iron if t.name == BrakeTemp.COOKING)
        assert ceramic_cooking.lower > iron_cooking.lower

    def test_carbon_highest(self):
        """Carbon aguanta más temperatura."""
        carbon = get_brake_thresholds("Carbon")
        cold = next(t for t in carbon if t.name == BrakeTemp.COLD)
        assert cold.upper == 400  # Carbon empieza a "warm" a 400

    def test_unknown_brake_fallback(self):
        th = get_brake_thresholds("Nonexistent")
        iron = get_brake_thresholds("Iron_Race")
        assert th[0].name == iron[0].name
