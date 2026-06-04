"""Tests para ConditionsMonitor — pipeline integration + silent failures."""

import time
import pytest

from src.intelligence.events.conditions_monitor import ConditionsMonitor
from src.intelligence.base_event import FakeAudioPlayer
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase
from src.intelligence.event_flags import event_flags


def _gsd(phase=SessionPhase.GREEN, rain=0.0, track_temp=25.0, car_class="GT3"):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.car_class = car_class
    g.weather.rain_intensity = rain
    g.weather.track_temp = track_temp
    return g


class TestSilentSuppression:
    def test_silent_suppress_when_no_weather_data(self):
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        g = _gsd()
        g.weather.rain_intensity = 0.0
        g.weather.track_temp = -999.0
        ev.trigger_internal(None, g)
        assert len(ap.messages) == 0

    def test_no_message_when_weather_unchanged(self):
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        ev.trigger_internal(None, _gsd(rain=0.5))
        ap.clear()
        ev.trigger_internal(None, _gsd(rain=0.5))
        assert len(ap.messages) == 0

    def test_silent_suppress_during_garage(self):
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        assert not ev.is_applicable(SessionType.RACE, SessionPhase.GARAGE)

    def test_silent_suppress_when_car_class_has_no_conditions(self):
        g = _gsd(car_class="NONEXISTENT")
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        # Car class not recognized -> _is_enabled_for_class falls back to UNKNOWN_RACE
        # which now has ["ALL"] so this should NOT suppress
        assert not ev.should_suppress(g)


class TestPipelineIntegration:
    def test_rain_starting_from_builder_data(self):
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        ev.trigger_internal(None, _gsd(rain=0.0))
        ap.clear()
        ev.trigger_internal(None, _gsd(rain=0.5))
        names = [m.name for m in ap.messages]
        assert "conditions/rain_starting" in names

    def test_rain_stopping_from_builder_data(self):
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        ev.trigger_internal(None, _gsd(rain=0.5))
        ap.clear()
        ev._last_rain_msg_time = 0
        ev.trigger_internal(None, _gsd(rain=0.0))
        names = [m.name for m in ap.messages]
        assert "conditions/rain_stopping" in names

    def test_track_temp_change_rising(self):
        ap = FakeAudioPlayer()
        ev = ConditionsMonitor(ap)
        ev._last_temp_msg_time = 0
        ev.trigger_internal(None, _gsd(track_temp=20.0))
        ap.clear()
        ev.trigger_internal(None, _gsd(track_temp=27.0))
        names = [m.name for m in ap.messages]
        assert any("track_temp_rising" in n for n in names)


class TestCrossEvent:
    def test_cross_event_fcy_suppresses_conditions(self):
        event_flags.on_manual_formation_lap = True
        try:
            ap = FakeAudioPlayer()
            ev = ConditionsMonitor(ap)
            ev.trigger_internal(None, _gsd())
            assert len(ap.messages) == 0
        finally:
            event_flags.on_manual_formation_lap = False


class TestClearState:
    def test_clear_state_prevents_stale_detection(self):
        ev = ConditionsMonitor()
        ev.trigger_internal(None, _gsd(rain=0.5))
        ev.clear_state()
        ev.trigger_internal(None, _gsd(rain=0.5))
        ap = FakeAudioPlayer()
        ev.audio_player = ap
        ev.trigger_internal(None, _gsd(rain=0.0))
        assert len(ap.messages) == 0
