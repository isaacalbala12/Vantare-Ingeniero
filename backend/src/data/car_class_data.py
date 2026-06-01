from enum import Enum
from dataclasses import dataclass, field
from typing import List


class CarClassEnum(Enum):
    GT3 = "GT3"
    GTE = "GTE"
    LMP1 = "LMP1"
    LMP2 = "LMP2"
    HYPER_CAR = "HYPER_CAR"
    HYPER_CAR_RACE = "HYPER_CAR_RACE"
    LMDH = "LMDH"
    FORMULA_E = "FORMULA_E"
    UNKNOWN_RACE = "UNKNOWN_RACE"
    USER_CREATED = "USER_CREATED"
    HYPER_CAR_LMU = "HYPER_CAR_LMU"
    LMGT3 = "LMGT3"


class TyreTemp(Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"
    COOKING = "COOKING"


class BrakeTemp(Enum):
    COLD = "COLD"
    WARM = "WARM"
    HOT = "HOT"
    COOKING = "COOKING"


class DamageLevel(int, Enum):
    NONE = 1
    TRIVIAL = 2
    MINOR = 3
    MAJOR = 4
    DESTROYED = 5


@dataclass
class Threshold:
    name: Enum
    lower: float
    upper: float


@dataclass
class CarClass:
    car_class_enum: CarClassEnum
    brake_type: str = "Iron_Race"
    default_tyre_type: str = "Unknown_Race"
    max_safe_water: float = 105.0
    max_safe_oil: float = 125.0
    is_battery_powered: bool = False
    is_drs_capable: bool = False
    drs_range: float = -1.0
    is_vehicle_swap_allowed: bool = False
    is_refueling_allowed: bool = True
    enabled_message_types: List[str] = field(default_factory=lambda: ["ALL"])


TYRE_TEMP_THRESHOLDS = {
    "Soft": [
        Threshold(TyreTemp.COLD, -10000, 70),
        Threshold(TyreTemp.WARM, 70, 100),
        Threshold(TyreTemp.HOT, 100, 115),
        Threshold(TyreTemp.COOKING, 115, 10000),
    ],
    "Medium": [
        Threshold(TyreTemp.COLD, -10000, 75),
        Threshold(TyreTemp.WARM, 75, 105),
        Threshold(TyreTemp.HOT, 105, 120),
        Threshold(TyreTemp.COOKING, 120, 10000),
    ],
    "Hard": [
        Threshold(TyreTemp.COLD, -10000, 78),
        Threshold(TyreTemp.WARM, 78, 110),
        Threshold(TyreTemp.HOT, 110, 124),
        Threshold(TyreTemp.COOKING, 124, 10000),
    ],
    "Wet": [
        Threshold(TyreTemp.COLD, -10000, 40),
        Threshold(TyreTemp.WARM, 40, 80),
        Threshold(TyreTemp.HOT, 80, 105),
        Threshold(TyreTemp.COOKING, 105, 10000),
    ],
    "Intermediate": [
        Threshold(TyreTemp.COLD, -10000, 60),
        Threshold(TyreTemp.WARM, 60, 95),
        Threshold(TyreTemp.HOT, 95, 110),
        Threshold(TyreTemp.COOKING, 110, 10000),
    ],
    "Unknown_Race": [
        Threshold(TyreTemp.COLD, -10000, 60),
        Threshold(TyreTemp.WARM, 60, 117),
        Threshold(TyreTemp.HOT, 117, 137),
        Threshold(TyreTemp.COOKING, 137, 10000),
    ],
}

BRAKE_TEMP_THRESHOLDS = {
    "Iron_Race": [
        Threshold(BrakeTemp.COLD, -10000, 150),
        Threshold(BrakeTemp.WARM, 150, 700),
        Threshold(BrakeTemp.HOT, 700, 900),
        Threshold(BrakeTemp.COOKING, 900, 10000),
    ],
    "Ceramic": [
        Threshold(BrakeTemp.COLD, -10000, 150),
        Threshold(BrakeTemp.WARM, 150, 950),
        Threshold(BrakeTemp.HOT, 950, 1200),
        Threshold(BrakeTemp.COOKING, 1200, 10000),
    ],
    "Carbon": [
        Threshold(BrakeTemp.COLD, -10000, 400),
        Threshold(BrakeTemp.WARM, 400, 1200),
        Threshold(BrakeTemp.HOT, 1200, 1500),
        Threshold(BrakeTemp.COOKING, 1500, 10000),
    ],
}

CAR_CLASSES = {
    CarClassEnum.GT3: CarClass(
        CarClassEnum.GT3, brake_type="Ceramic", max_safe_oil=135
    ),
    CarClassEnum.GTE: CarClass(
        CarClassEnum.GTE, brake_type="Ceramic", max_safe_oil=135
    ),
    CarClassEnum.LMP1: CarClass(
        CarClassEnum.LMP1, brake_type="Carbon", max_safe_oil=140
    ),
    CarClassEnum.LMP2: CarClass(
        CarClassEnum.LMP2, brake_type="Ceramic", max_safe_oil=135
    ),
    CarClassEnum.HYPER_CAR: CarClass(
        CarClassEnum.HYPER_CAR, brake_type="Carbon",
        is_battery_powered=True, is_drs_capable=True, drs_range=1.0,
    ),
    CarClassEnum.LMDH: CarClass(
        CarClassEnum.LMDH, brake_type="Ceramic",
        is_drs_capable=True, drs_range=1.0,
    ),
    CarClassEnum.FORMULA_E: CarClass(
        CarClassEnum.FORMULA_E, is_refueling_allowed=False
    ),
    CarClassEnum.UNKNOWN_RACE: CarClass(
        CarClassEnum.UNKNOWN_RACE, enabled_message_types=["FUEL"]
    ),
}


def get_car_class(enum: CarClassEnum) -> CarClass:
    return CAR_CLASSES.get(enum, CAR_CLASSES[CarClassEnum.UNKNOWN_RACE])


def get_tyre_thresholds(tyre: str) -> List[Threshold]:
    return TYRE_TEMP_THRESHOLDS.get(tyre, TYRE_TEMP_THRESHOLDS["Unknown_Race"])


def get_brake_thresholds(brake: str) -> List[Threshold]:
    return BRAKE_TEMP_THRESHOLDS.get(brake, BRAKE_TEMP_THRESHOLDS["Iron_Race"])
