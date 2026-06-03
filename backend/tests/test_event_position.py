"""Tests para PositionEvent — cambios de posición, liderato y overtakes."""

import pytest

from src.intelligence.events.position import PositionEvent
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData, OpponentData
from src.models.enums import SessionType, SessionPhase


@pytest.fixture(autouse=True)
def _clean_flags():
    event_flags.on_manual_formation_lap = False
    event_flags.on_formation = False
    yield
    event_flags.on_manual_formation_lap = False
    event_flags.on_formation = False


def _opp():
    """At least one opponent so num_cars > 1."""
    return {"rival": OpponentData(class_pos=2)}


def _gsd(class_position=1, phase=SessionPhase.GREEN, session_type=SessionType.RACE, now=0.0, opponents=None):
    g = GameStateData()
    g.now = now
    g.session.session_type = session_type
    g.session.session_phase = phase
    g.session.class_position = class_position
    g.opponents = opponents or {}
    return g


class TestPositionEvent:
    def test_position_gained(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap)
        # Tick 1: establish baseline at P4
        ev.trigger_internal(None, _gsd(class_position=4, opponents=_opp()))
        # Tick 2: gained a position
        ev.trigger_internal(None, _gsd(class_position=3, opponents=_opp()))
        names = [m.name for m in ap.msgs]
        assert "position/overtaking" in names

    def test_position_lost(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap)
        # Tick 1: establish baseline at P2
        ev.trigger_internal(None, _gsd(class_position=2, opponents=_opp()))
        # Tick 2: lost a position
        ev.trigger_internal(None, _gsd(class_position=4, opponents=_opp()))
        names = [m.name for m in ap.msgs]
        assert "position/being_overtaken" in names

    def test_new_leader(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap)
        # Tick 1: establish baseline at P2
        ev.trigger_internal(None, _gsd(class_position=2, opponents=_opp()))
        # Tick 2: take the lead
        ev.trigger_internal(None, _gsd(class_position=1, opponents=_opp()))
        names = [m.name for m in ap.msgs]
        assert "position/new_leader" in names
        assert "position/leading" in names

    def test_leading_continues(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap)
        # Tick 1: become leader
        ev.trigger_internal(None, _gsd(class_position=1, opponents=_opp()))
        # Tick 2: still leading — should not re-emit leading
        ev.trigger_internal(None, _gsd(class_position=1, opponents=_opp()))
        names = [m.name for m in ap.msgs]
        assert "position/leading" in names
        assert names.count("position/leading") == 1

    def test_overtaking_detected(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap)
        opponents = {
            "rival": OpponentData(class_pos=2),
        }
        # Tick 1: establish baseline at P2
        ev.trigger_internal(None, _gsd(class_position=2, opponents=opponents))
        # Tick 2: overtake rival → P1
        ev.trigger_internal(None, _gsd(class_position=1, opponents=opponents))
        names = [m.name for m in ap.msgs]
        assert "position/overtaking" in names

    def test_consistently_last(self):
        ap = FakeAudioPlayer()
        ev = PositionEvent(ap)
        opponents = {
            "leader": OpponentData(class_pos=1),
            "mid": OpponentData(class_pos=2),
        }
        # 3 ticks at last position (P3 of 3 cars)
        ev.trigger_internal(None, _gsd(class_position=3, opponents=opponents))
        ev.trigger_internal(None, _gsd(class_position=3, opponents=opponents))
        ev.trigger_internal(None, _gsd(class_position=3, opponents=opponents))
        names = [m.name for m in ap.msgs]
        assert "position/consistently_last" in names
