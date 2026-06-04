"""Tests para FuelEvent — pipeline, silent failures, cross-event."""

import time
import pytest

from src.intelligence.events.fuel import FuelEvent
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


@pytest.fixture(autouse=True)
def _clean_flags():
    event_flags.is_pitting_this_lap = False
    event_flags.fuel_warning_active = False
    yield
    event_flags.is_pitting_this_lap = False
    event_flags.fuel_warning_active = False


def _gsd(fuel_left=50.0, laps=5, phase=SessionPhase.GREEN, car_class="GT3"):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.session.completed_laps = laps
    g.car_class = car_class
    g.fuel.fuel_left = fuel_left
    g.fuel.fuel_capacity = 100.0
    return g


class TestSilentFailures:
    def test_silent_skip_when_fuel_zero(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        ev.trigger_internal(None, _gsd(fuel_left=0))
        assert len(ap.messages) == 0

    def test_silent_suppress_below_min_laps(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        ev.trigger_internal(None, _gsd(fuel_left=50, laps=0))
        assert len(ap.messages) == 0

    def test_no_false_low_without_consumption_data(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        ev.trigger_internal(None, _gsd(fuel_left=3, laps=5))
        # Sin datos de consumo previos, no hay estimacion
        assert len(ap.messages) == 0


class TestPipelineIntegration:
    def test_consumption_from_sequence_of_ticks(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        ev.trigger_internal(None, _gsd(fuel_left=50, laps=1))
        ev.trigger_internal(None, _gsd(fuel_left=47, laps=2))
        ev.trigger_internal(None, _gsd(fuel_left=44, laps=3))
        ev.trigger_internal(None, _gsd(fuel_left=41, laps=4))
        assert ev._avg_consumption > 0

    def test_low_fuel_emitted_with_3_samples(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        # Build up consumption samples: 3 L/lap
        for i in range(4):
            ev.trigger_internal(None, _gsd(fuel_left=50 - i * 3, laps=i + 1))
        # avg_consumption=3.0, fuel_left=41. Simulate a long stint: use delta=3,
        # advance to fuel_left=6 at lap=8 so avg stays ~3 and laps_left=2.
        ev.trigger_internal(None, _gsd(fuel_left=38, laps=5))
        ev.trigger_internal(None, _gsd(fuel_left=35, laps=6))
        ev.trigger_internal(None, _gsd(fuel_left=32, laps=7))
        ev.trigger_internal(None, _gsd(fuel_left=6, laps=8))
        names = [m.name for m in ap.messages]
        assert "fuel/low_fuel_warning" in names

    def test_fuel_ok_after_refuel(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        ev.trigger_internal(None, _gsd(fuel_left=30, laps=5))
        ap.clear()
        ev.trigger_internal(None, _gsd(fuel_left=80, laps=5))
        names = [m.name for m in ap.messages]
        assert "fuel/fuel_ok_after_refuel" in names


class TestCrossEvent:
    def test_suppressed_when_pitting(self):
        event_flags.is_pitting_this_lap = True
        try:
            ap = FakeAudioPlayer()
            ev = FuelEvent(ap)
            ev.trigger_internal(None, _gsd(fuel_left=5, laps=5))
            assert len(ap.messages) == 0
        finally:
            event_flags.is_pitting_this_lap = False

    def test_sets_fuel_warning_flag(self):
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)
        for i in range(4):
            ev.trigger_internal(None, _gsd(fuel_left=50 - i * 3, laps=i + 1))
        ev.trigger_internal(None, _gsd(fuel_left=6, laps=5))
        assert event_flags.fuel_warning_active
        event_flags.fuel_warning_active = False


class TestMessageFlow:
    def test_stale_fuel_message(self):
        from src.models.messages import QueuedMessage
        msg = QueuedMessage("fuel/old_warning", expires=0.001)
        assert msg.is_expired(time.time() + 0.1)
