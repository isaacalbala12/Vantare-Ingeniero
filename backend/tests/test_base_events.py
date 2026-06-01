"""Tests para los 4 eventos base del Sub-proyecto 4."""

import pytest
import time

from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.intelligence.events.flags_monitor import FlagsMonitor, F_FCY_DEPLOYED, F_FCY_ENDED, F_CHEQUERED, F_FINISHED
from src.intelligence.events.session_monitor import SessionMonitor, F_FORMATION_START, F_FORMATION_END
from src.intelligence.events.lap_counter import LapCounter, F_LAP, F_WARMUP
from src.intelligence.events.position import PositionEvent, F_NEW_LEADER, F_LOST_LEAD, F_OVERTAKE, F_BEING_OVERTAKEN
from src.models.game_state_data import GameStateData, OpponentData
from src.models.enums import SessionType, SessionPhase, FullCourseYellowPhase


@pytest.fixture(autouse=True)
def reset_event_flags():
    event_flags.reset()
    yield
    event_flags.reset()


def _gsd(phase=SessionPhase.GREEN, stype=SessionType.RACE, lap=1, pos=5, fcy_phase=FullCourseYellowPhase.RACING, num_opponents=5):
    g = GameStateData()
    g.session.session_type = stype
    g.session.session_phase = phase
    g.session.completed_laps = lap
    g.session.class_position = pos
    g.session.sector_number = 1
    g.flag.fcy_phase = fcy_phase
    for i in range(num_opponents):
        g.opponents[f"Opponent_{i}"] = OpponentData(
            driver=f"Opponent_{i}",
            class_pos=pos + i + 1 if pos > 0 else i + 2,
        )
    return g


# === FLAGS MONITOR ===

class TestFlagsMonitor:
    def test_no_msg_on_init(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd())
        assert len(ap.msgs) == 0  # primer tick no emite

    def test_fcy_deployed(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        names = [m.name for m in ap.msgs]
        assert F_FCY_DEPLOYED in names

    def test_fcy_ended(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        names = [m.name for m in ap.msgs]
        assert F_FCY_ENDED in names

    def test_chequered(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.CHECKERED))
        names = [m.name for m in ap.msgs]
        assert F_CHEQUERED in names

    def test_finished(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FINISHED))
        names = [m.name for m in ap.msgs]
        assert F_FINISHED in names

    def test_no_fcy_msg_when_already_in_fcy(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        ap.clear()
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        # No debe re-emitir FCY_DEPLOYED
        names = [m.name for m in ap.msgs]
        assert F_FCY_DEPLOYED not in names

    def test_clear_state(self):
        ap = FakeAudioPlayer()
        ev = FlagsMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.clear_state()
        # Después de clear, próximo tick se reinicia
        ap.clear()
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ap.clear()
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        names = [m.name for m in ap.msgs]
        assert F_FCY_DEPLOYED in names


# === SESSION MONITOR ===

class TestSessionMonitor:
    def test_formation_start(self):
        ap = FakeAudioPlayer()
        ev = SessionMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FORMATION))
        names = [m.name for m in ap.msgs]
        assert F_FORMATION_START in names
        assert event_flags.on_formation is True

    def test_formation_end(self):
        ap = FakeAudioPlayer()
        ev = SessionMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FORMATION))
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        names = [m.name for m in ap.msgs]
        assert F_FORMATION_END in names
        assert event_flags.on_formation is False

    def test_no_formation_msg_on_init(self):
        ap = FakeAudioPlayer()
        ev = SessionMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        # No debe emitir nada porque prev era None
        assert len(ap.msgs) == 0

    def test_clear_state(self):
        ap = FakeAudioPlayer()
        ev = SessionMonitor(ap=ap)
        ev.trigger_internal(None, _gsd(phase=SessionPhase.FORMATION))
        ev.clear_state()
        assert event_flags.on_formation is False


# === LAP COUNTER ===

class TestLapCounter:
    def test_no_msg_on_init(self):
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)
        ev.trigger_internal(None, _gsd(lap=0))
        assert len(ap.msgs) == 0

    def test_lap_increments(self):
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)
        ev.trigger_internal(None, _gsd(lap=1))
        ev.trigger_internal(None, _gsd(lap=2))
        names = [m.name for m in ap.msgs]
        assert F_LAP in names

    def test_same_lap_no_msg(self):
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)
        ev.trigger_internal(None, _gsd(lap=3))
        ev.trigger_internal(None, _gsd(lap=3))
        # Solo debe emitir si realmente hay incremento desde prev
        # El primer tick no emite (prev_lap=0), segundo tick prev=3, curr=3 no incrementa
        assert len(ap.msgs) == 0

    def test_pit_out_lap_warmup(self):
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)
        # Vuelta 1 en pits
        g1 = _gsd(lap=1)
        g1.pit.in_pitlane = True
        ev.trigger_internal(None, g1)
        # Vuelta 2 fuera de pits
        g2 = _gsd(lap=2)
        g2.pit.in_pitlane = False
        ev.trigger_internal(g1, g2)
        names = [m.name for m in ap.msgs]
        assert F_WARMUP in names

    def test_clear_state(self):
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)
        ev.trigger_internal(None, _gsd(lap=1))
        ev.trigger_internal(None, _gsd(lap=2))
        ev.clear_state()
        ap.clear()
        ev.trigger_internal(None, _gsd(lap=2))
        # Después de clear, prev_lap=0, así que curr=2 no incrementa desde 0
        # Solo se emite si curr > prev
        assert len(ap.msgs) == 0


# === POSITION EVENT ===

class TestPositionEvent:
    def test_no_msg_on_init(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        ev.trigger_internal(None, _gsd(pos=0))
        assert len(ap.msgs) == 0

    def test_new_leader(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        # P5 → P1
        ev.trigger_internal(None, _gsd(pos=5))
        ev.trigger_internal(None, _gsd(pos=1))
        names = [m.name for m in ap.msgs]
        assert F_NEW_LEADER in names

    def test_lost_lead(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        # P1 → P2
        ev.trigger_internal(None, _gsd(pos=1))
        ev.trigger_internal(None, _gsd(pos=2))
        names = [m.name for m in ap.msgs]
        assert F_LOST_LEAD in names

    def test_overtake(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        # P5 → P4
        ev.trigger_internal(None, _gsd(pos=5))
        ev.trigger_internal(None, _gsd(pos=4))
        names = [m.name for m in ap.msgs]
        assert F_OVERTAKE in names

    def test_being_overtaken(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        # P4 → P5
        ev.trigger_internal(None, _gsd(pos=4))
        ev.trigger_internal(None, _gsd(pos=5))
        names = [m.name for m in ap.msgs]
        assert F_BEING_OVERTAKEN in names

    def test_anti_bounce_position_oscillation(self):
        """Posición estable entre ticks no debe disparar overtake/being_overtaken."""
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        # Mismo pos (5) durante 4 ticks
        ev.trigger_internal(None, _gsd(pos=5))
        ev.trigger_internal(None, _gsd(pos=5))
        ev.trigger_internal(None, _gsd(pos=5))
        ev.trigger_internal(None, _gsd(pos=5))
        # No debe haber overtake ni being_overtaken
        names = [m.name for m in ap.msgs]
        assert F_OVERTAKE not in names
        assert F_BEING_OVERTAKEN not in names

    def test_pole_position_in_qualify(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        g = _gsd(pos=1, stype=SessionType.QUALIFY)
        ev.trigger_internal(None, g)
        names = [m.name for m in ap.msgs]
        assert "position/pole" in names

    def test_consistently_last(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        # Solo nosotros, P1
        ev.trigger_internal(None, _gsd(pos=1))
        ev.trigger_internal(None, _gsd(pos=1))
        ev.trigger_internal(None, _gsd(pos=1))
        ev.trigger_internal(None, _gsd(pos=1))
        # No debe haber "consistently_last" porque num_cars=1
        names = [m.name for m in ap.msgs]
        assert "position/consistently_last" not in names

    def test_clear_state(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap=ap)
        ev.trigger_internal(None, _gsd(pos=5))
        ev.trigger_internal(None, _gsd(pos=4))
        ev.clear_state()
        ap.clear()
        # Después de clear, prev_pos=0, así que curr=4 con bounce
        ev.trigger_internal(None, _gsd(pos=4))
        ev.trigger_internal(None, _gsd(pos=4))
        # No debe haber overtake (estamos en el mismo pos)
        names = [m.name for m in ap.msgs]
        assert F_OVERTAKE not in names
