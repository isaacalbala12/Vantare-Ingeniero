"""Tests para FlagsMonitor — transiciones FCY, chequered y clear_state."""

import pytest
import time

from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.intelligence.events.flags_monitor import (
    FlagsMonitor,
    F_FCY_DEPLOYED,
    F_FCY_ENDING,
    F_FCY_ENDED,
    F_CHEQUERED,
    F_FINISHED,
)
from src.models.game_state_data import GameStateData
from src.models.enums import (
    SessionType,
    SessionPhase,
    FullCourseYellowPhase,
)


@pytest.fixture(autouse=True)
def _clean_flags():
    event_flags.reset()
    event_flags.on_manual_formation_lap = False
    yield
    event_flags.reset()
    event_flags.on_manual_formation_lap = False


def _gsd(
    phase=SessionPhase.GREEN,
    fcy_phase=FullCourseYellowPhase.RACING,
    session_type=SessionType.RACE,
    lap=1,
):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = session_type
    g.session.session_phase = phase
    g.session.completed_laps = lap
    g.session.class_position = 5
    g.car_class = "GT3"
    g.flag.fcy_phase = fcy_phase
    return g


class TestFCYDeployed:
    def test_fcy_deployed(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        # Primer tick: establece _prev_phase = GREEN
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        # Segundo tick: transición GREEN → FCY
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        names = [m.name for m in ap.msgs]
        assert F_FCY_DEPLOYED in names


class TestFCYEnding:
    def test_fcy_ending(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        # Primer tick: FCY con fcy_phase=IN_PROGRESS
        ev.trigger_internal(None, _gsd(
            phase=SessionPhase.FULL_COURSE_YELLOW,
            fcy_phase=FullCourseYellowPhase.IN_PROGRESS,
        ))
        # Segundo tick: transición a LAST_LAP_NEXT
        ev.trigger_internal(None, _gsd(
            phase=SessionPhase.FULL_COURSE_YELLOW,
            fcy_phase=FullCourseYellowPhase.LAST_LAP_NEXT,
        ))
        names = [m.name for m in ap.msgs]
        assert F_FCY_ENDING in names


class TestFCYEnded:
    def test_fcy_ended(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        # Secuencia: GREEN → FCY → GREEN
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        names = [m.name for m in ap.msgs]
        assert F_FCY_ENDED in names


class TestChequered:
    def test_chequered(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.CHECKERED))
        names = [m.name for m in ap.msgs]
        assert F_CHEQUERED in names


class TestClearState:
    def test_clear_state(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        # Ejecutar ticks para poblar estado interno
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        assert ev._prev_phase == SessionPhase.FULL_COURSE_YELLOW
        assert ev._laps_in_fcy == 0
        # Limpiar estado
        ev.clear_state()
        assert ev._prev_phase is None
        assert ev._prev_fcy_phase is None
        assert ev._laps_in_fcy == 0
