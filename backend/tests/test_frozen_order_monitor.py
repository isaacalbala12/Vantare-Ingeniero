"""Tests para FrozenOrderMonitor — cross-event state, ordering, pipeline."""

import time
import pytest

from src.intelligence.events.frozen_order_monitor import FrozenOrderMonitor
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_engine import EventEngine
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase, FrozenOrderPhase


def _gsd(phase=SessionPhase.GREEN, fo_phase=FrozenOrderPhase.NONE):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.car_class = "GT3"
    g.frozen_order.phase = fo_phase
    return g


class TestSilentSuppression:
    def test_no_message_without_fo_data(self):
        ap = FakeAudioPlayer()
        ev = FrozenOrderMonitor(ap)
        g = _gsd()
        g.frozen_order.phase = FrozenOrderPhase.NONE
        ev.trigger_internal(None, g)
        assert len(ap.messages) == 0
        assert len(ap.immediate_messages) == 0

    def test_silent_suppress_during_manual_formation(self):
        event_flags.on_manual_formation_lap = True
        try:
            ap = FakeAudioPlayer()
            ev = FrozenOrderMonitor(ap)
            ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.FCY))
            assert len(ap.immediate_messages) == 0
        finally:
            event_flags.on_manual_formation_lap = False


class TestPipelineIntegration:
    def test_sc_deployed_via_fcy_phase(self):
        ap = FakeAudioPlayer()
        ev = FrozenOrderMonitor(ap)
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.FCY))
        names = [m.name for m in ap.immediate_messages]
        assert "frozen_order/sc_deployed" in names

    def test_sc_ending_via_transition_to_none(self):
        ap = FakeAudioPlayer()
        ev = FrozenOrderMonitor(ap)
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.FCY))
        ap.clear()
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.NONE))
        names = [m.name for m in ap.messages]
        assert "frozen_order/sc_ending" in names

    def test_no_duplicate_sc_ending(self):
        ap = FakeAudioPlayer()
        ev = FrozenOrderMonitor(ap)
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.FCY))
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.NONE))
        ap.clear()
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.NONE))
        assert len(ap.messages) == 0


class TestSilentState:
    def test_clear_state_then_sc_redispatches(self):
        ap = FakeAudioPlayer()
        ev = FrozenOrderMonitor(ap)
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.FCY))
        ev.clear_state()
        ap.clear()
        ev.trigger_internal(None, _gsd(fo_phase=FrozenOrderPhase.FCY))
        names = [m.name for m in ap.immediate_messages]
        assert "frozen_order/sc_deployed" in names


class TestCrossEventOrdering:
    def test_frozen_order_sequence_after_flags_monitor(self):
        """FrozenOrder(7) runs AFTER FlagsMonitor(5) in event engine."""
        from src.intelligence.events.frozen_order_monitor import FrozenOrderMonitor as FO
        from src.intelligence.events.flags_monitor import FlagsMonitor
        engine = EventEngine()
        engine.register_event("fo", FO())
        engine.register_event("flags", FlagsMonitor())
        # FrozenOrder(7) runs after FlagsMonitor(5)
        assert engine._events["fo"].sequence >= engine._events["flags"].sequence
