"""Tests para PitStops — state machine, cross-event flags, pipeline."""

import time
import pytest

from src.intelligence.events.pit_stops import PitStops, LMU_PIT_NONE, LMU_PIT_ENTERING, LMU_PIT_STOPPED, LMU_PIT_EXITING
from src.intelligence.base_event import FakeAudioPlayer, AbstractEvent
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData, PitData
from src.models.enums import SessionType, SessionPhase


def _gsd(pit_state=LMU_PIT_NONE, in_pitlane=False, num_pitstops=0,
         phase=SessionPhase.GREEN, car_class="GT3"):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.car_class = car_class
    g.pit.in_pitlane = in_pitlane
    g.pit.pit_state = pit_state
    g.pit.num_pitstops = num_pitstops
    g.pit.scheduled_stops = 0
    return g


class TestSilentFailures:
    def test_silent_no_countdown_when_not_pitting(self):
        ap = FakeAudioPlayer()
        ev = PitStops(ap)
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_NONE))
        assert len(ap.messages) == 0

    def test_silent_state_machine_no_skip(self):
        """Saltar de NONE a STOPPED sin ENTERING no crashea."""
        ap = FakeAudioPlayer()
        ev = PitStops(ap)
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_STOPPED))
        assert len(ap.messages) == 0  # No countdown sin entrada previa

    def test_silent_suppress_in_garage(self):
        g = _gsd(phase=SessionPhase.GARAGE)
        ev = PitStops()
        assert ev.should_suppress(g)

    def test_clear_state_prevents_stale_state(self):
        ap = FakeAudioPlayer()
        ev = PitStops(ap)
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        ev.clear_state()
        ap.clear()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        names = [m.name for m in ap.messages]
        assert "pit_stops/pit_entry" in names


class TestPipelineIntegration:
    def test_full_pit_cycle_entering_to_exit(self):
        ap = FakeAudioPlayer()
        ev = PitStops(ap)
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_STOPPED))
        ap.clear()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_EXITING))
        names = [m.name for m in ap.immediate_messages]
        assert "pit_stops/go_go_go" in names

    def test_exit_clears_is_pitting_flag(self):
        ev = PitStops()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        assert event_flags.is_pitting_this_lap
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_NONE, in_pitlane=False))
        assert not event_flags.is_pitting_this_lap

    def test_pit_entry_sets_is_pitting_flag(self):
        ev = PitStops()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        assert event_flags.is_pitting_this_lap


class TestCrossEvent:
    def test_cross_sets_is_pitting_flag_for_fuel(self):
        """Fuel debe leer event_flags.is_pitting_this_lap para suprimir warning."""
        event_flags.is_pitting_this_lap = False
        ev = PitStops()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        assert event_flags.is_pitting_this_lap is True
        event_flags.is_pitting_this_lap = False

    def test_mandatory_stop_completed_resets_flags(self):
        ev = PitStops()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_STOPPED, num_pitstops=0))
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_STOPPED, num_pitstops=1))
        # mandatory stop flag should be cleared
        assert not event_flags.waiting_for_mandatory_stop_timer

    def test_cross_stale_flag_cleared_after_exit(self):
        """Tras salir de pits, el flag se limpia."""
        ev = PitStops()
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        assert event_flags.is_pitting_this_lap
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_NONE, in_pitlane=False))
        assert not event_flags.is_pitting_this_lap


class TestMessageFlow:
    def test_go_go_go_has_correct_priority(self):
        ap = FakeAudioPlayer()
        ev = PitStops(ap)
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_ENTERING))
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_STOPPED))
        ev.trigger_internal(None, _gsd(pit_state=LMU_PIT_EXITING))
        assert len(ap.immediate_messages) >= 1
        assert ap.immediate_messages[0].priority == 15
