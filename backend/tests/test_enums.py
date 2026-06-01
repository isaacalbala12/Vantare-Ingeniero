"""Tests del módulo enums — enumerados del sistema.

Cobertura:
- Todos los enums: SessionType, SessionPhase, FlagEnum, etc.
- Valores correctos de cada miembro
- str-enum behavior (heredan de str)
"""
import pytest
from src.models.enums import (
    SessionType, SessionPhase, FlagEnum,
    FullCourseYellowPhase, FrozenOrderPhase,
    FrozenOrderColumn, FrozenOrderAction,
    PitWindow, ControlType, TyreType,
)


class TestSessionType:
    def test_all_values(self):
        assert SessionType.UNAVAILABLE.value == "Unavailable"
        assert SessionType.PRACTICE.value == "Practice"
        assert SessionType.QUALIFY.value == "Qualify"
        assert SessionType.PRIVATE_QUALIFY.value == "PrivateQualify"
        assert SessionType.RACE.value == "Race"
        assert SessionType.HOT_LAP.value == "HotLap"
        assert SessionType.LONE_PRACTICE.value == "LonePractice"

    def test_str_enum(self):
        """Los SessionType son str+Enum."""
        assert isinstance(SessionType.RACE, str)
        assert SessionType.RACE == "Race"

    def test_count(self):
        assert len(list(SessionType)) == 7


class TestSessionPhase:
    def test_all_values(self):
        assert SessionPhase.UNAVAILABLE.value == "Unavailable"
        assert SessionPhase.GARAGE.value == "Garage"
        assert SessionPhase.GRIDWALK.value == "Gridwalk"
        assert SessionPhase.FORMATION.value == "Formation"
        assert SessionPhase.COUNTDOWN.value == "Countdown"
        assert SessionPhase.GREEN.value == "Green"
        assert SessionPhase.FULL_COURSE_YELLOW.value == "FullCourseYellow"
        assert SessionPhase.CHECKERED.value == "Checkered"
        assert SessionPhase.FINISHED.value == "Finished"

    def test_count(self):
        assert len(list(SessionPhase)) == 9


class TestFlagEnum:
    def test_values(self):
        assert FlagEnum.GREEN.value == "GREEN"
        assert FlagEnum.YELLOW.value == "YELLOW"
        assert FlagEnum.DOUBLE_YELLOW.value == "DOUBLE_YELLOW"
        assert FlagEnum.BLUE.value == "BLUE"
        assert FlagEnum.WHITE.value == "WHITE"
        assert FlagEnum.BLACK.value == "BLACK"
        assert FlagEnum.CHEQUERED.value == "CHEQUERED"


class TestFullCourseYellowPhase:
    def test_all_phases(self):
        assert FullCourseYellowPhase.PENDING.value == "PENDING"
        assert FullCourseYellowPhase.IN_PROGRESS.value == "IN_PROGRESS"
        assert FullCourseYellowPhase.PITS_CLOSED.value == "PITS_CLOSED"
        assert FullCourseYellowPhase.PITS_OPEN_LEAD_LAP.value == "PITS_OPEN_LEAD_LAP"
        assert FullCourseYellowPhase.PITS_OPEN.value == "PITS_OPEN"
        assert FullCourseYellowPhase.LAST_LAP_NEXT.value == "LAST_LAP_NEXT"
        assert FullCourseYellowPhase.LAST_LAP_CURRENT.value == "LAST_LAP_CURRENT"
        assert FullCourseYellowPhase.RACING.value == "RACING"

    def test_count(self):
        assert len(list(FullCourseYellowPhase)) == 8


class TestFrozenOrder:
    def test_phase_values(self):
        assert FrozenOrderPhase.NONE.value == "None"
        assert FrozenOrderPhase.FCY.value == "FullCourseYellow"
        assert FrozenOrderPhase.FORMATION.value == "FormationStanding"
        assert FrozenOrderPhase.ROLLING.value == "Rolling"

    def test_column_values(self):
        assert FrozenOrderColumn.NONE.value == "None"
        assert FrozenOrderColumn.LEFT.value == "Left"
        assert FrozenOrderColumn.RIGHT.value == "Right"

    def test_action_values(self):
        assert FrozenOrderAction.NONE.value == "None"
        assert FrozenOrderAction.FOLLOW.value == "Follow"
        assert FrozenOrderAction.CATCH_UP.value == "CatchUp"
        assert FrozenOrderAction.ALLOW_TO_PASS.value == "AllowToPass"


class TestPitWindow:
    def test_values(self):
        assert PitWindow.UNAVAILABLE.value == "Unavailable"
        assert PitWindow.CLOSED.value == "Closed"
        assert PitWindow.OPEN.value == "Open"


class TestControlType:
    def test_values(self):
        assert ControlType.PLAYER.value == "Player"
        assert ControlType.AI.value == "AI"
        assert ControlType.REMOTE.value == "Remote"
        assert ControlType.REPLAY.value == "Replay"


class TestTyreType:
    def test_values(self):
        assert TyreType.SOFT.value == "Soft"
        assert TyreType.MEDIUM.value == "Medium"
        assert TyreType.HARD.value == "Hard"
        assert TyreType.WET.value == "Wet"
        assert TyreType.INTERMEDIATE.value == "Intermediate"
