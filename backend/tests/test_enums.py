import pytest
from src.models.enums import (
    SessionType, SessionPhase, FlagEnum, FullCourseYellowPhase,
    FrozenOrderPhase, FrozenOrderColumn, FrozenOrderAction,
    PitWindow, TyreType, ControlType
)


def test_session_type_values():
    assert SessionType.RACE.value == "Race"
    assert SessionType.PRACTICE.value == "Practice"


def test_session_phase_values():
    assert SessionPhase.GREEN.value == "Green"
    assert SessionPhase.FULL_COURSE_YELLOW.value == "FullCourseYellow"
    assert SessionPhase.UNAVAILABLE.value == "Unavailable"


def test_flag_enum_values():
    assert FlagEnum.GREEN.value == "GREEN"
    assert FlagEnum.YELLOW.value == "YELLOW"
    assert FlagEnum.BLUE.value == "BLUE"
    assert FlagEnum.CHEQUERED.value == "CHEQUERED"


def test_fcy_phases():
    assert FullCourseYellowPhase.PENDING.value == "PENDING"
    assert FullCourseYellowPhase.RACING.value == "RACING"
    assert FullCourseYellowPhase.PITS_CLOSED.value == "PITS_CLOSED"


def test_frozen_order():
    assert FrozenOrderPhase.FCY.value == "FullCourseYellow"
    assert FrozenOrderPhase.FORMATION.value == "FormationStanding"


def test_pit_window():
    assert PitWindow.OPEN.value == "Open"
    assert PitWindow.CLOSED.value == "Closed"


def test_tyre_types():
    assert TyreType.SOFT.value == "Soft"
    assert TyreType.WET.value == "Wet"


def test_control_type():
    assert ControlType.PLAYER.value == "Player"
    assert ControlType.AI.value == "AI"

def test_frozen_order_column():
    assert FrozenOrderColumn.NONE.value == "None"
    assert FrozenOrderColumn.LEFT.value == "Left"
    assert FrozenOrderColumn.RIGHT.value == "Right"

def test_frozen_order_action():
    assert FrozenOrderAction.NONE.value == "None"
    assert FrozenOrderAction.FOLLOW.value == "Follow"
    assert FrozenOrderAction.CATCH_UP.value == "CatchUp"
    assert FrozenOrderAction.ALLOW_TO_PASS.value == "AllowToPass"
