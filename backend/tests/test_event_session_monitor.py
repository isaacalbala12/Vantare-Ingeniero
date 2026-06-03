"""Tests para SessionMonitor — formation, session transitions, chequered flag."""

import time
import pytest

from src.intelligence.events.session_monitor import SessionMonitor
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


@pytest.fixture(autouse=True)
def _clean_state():
    event_flags.on_formation = False
    yield
    event_flags.on_formation = False


def _gsd(session_type=SessionType.RACE, session_phase=SessionPhase.GREEN):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = session_type
    g.session.session_phase = session_phase
    return g


class TestFormationEvents:
    def test_formation_start(self):
        """Phase FORMATION → formation_start event fired."""
        ap = FakeAudioPlayer()
        mon = SessionMonitor(ap)
        prev = _gsd(session_phase=SessionPhase.GARAGE)
        curr = _gsd(session_phase=SessionPhase.FORMATION)
        mon.trigger_internal(prev, curr)
        names = [m.name for m in ap.msgs]
        assert "session/formation_start" in names

    def test_formation_end(self):
        """Phase GREEN after FORMATION → formation_end with go-go-go text."""
        ap = FakeAudioPlayer()
        mon = SessionMonitor(ap)
        # First, enter formation
        prev = _gsd(session_phase=SessionPhase.GARAGE)
        curr = _gsd(session_phase=SessionPhase.FORMATION)
        mon.trigger_internal(prev, curr)
        ap.clear()
        # Then transition to GREEN
        prev = curr
        curr = _gsd(session_phase=SessionPhase.GREEN)
        mon.trigger_internal(prev, curr)
        names = [m.name for m in ap.msgs]
        assert "session/formation_end" in names
        # Verify the message text contains the race start phrase
        assert len(ap.msgs) == 1
        assert "go go go" in ap.msgs[0].fragments[0].text


class TestSessionTransition:
    def test_session_transition(self):
        """SessionMonitor does NOT emit events on session_type changes (phase-only logic)."""
        ap = FakeAudioPlayer()
        mon = SessionMonitor(ap)
        prev = _gsd(session_type=SessionType.PRACTICE, session_phase=SessionPhase.GREEN)
        curr = _gsd(session_type=SessionType.RACE, session_phase=SessionPhase.GREEN)
        mon.trigger_internal(prev, curr)
        assert len(ap.msgs) == 0


class TestChequeredFlag:
    def test_chequered_flag(self):
        """SessionMonitor does NOT emit chequered event (handled by FlagsMonitor)."""
        ap = FakeAudioPlayer()
        mon = SessionMonitor(ap)
        prev = _gsd(session_phase=SessionPhase.GREEN)
        curr = _gsd(session_phase=SessionPhase.CHECKERED)
        mon.trigger_internal(prev, curr)
        assert len(ap.msgs) == 0


class TestNoEvent:
    def test_same_session_no_event(self):
        """No phase or type changes → no messages emitted."""
        ap = FakeAudioPlayer()
        mon = SessionMonitor(ap)
        prev = _gsd(session_type=SessionType.RACE, session_phase=SessionPhase.GREEN)
        curr = _gsd(session_type=SessionType.RACE, session_phase=SessionPhase.GREEN)
        mon.trigger_internal(prev, curr)
        assert len(ap.msgs) == 0
