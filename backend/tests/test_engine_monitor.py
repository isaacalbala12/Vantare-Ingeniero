"""Tests para EngineMonitor — pipeline, silent failures, cross-event."""

import time
import pytest

from src.intelligence.events.engine_monitor import EngineMonitor
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


def _gsd(water=90, oil=100, rpm=5000, gear=2, max_rpm=8000, overheating=False,
         speed=30, phase=SessionPhase.GREEN, car_class="GT3"):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.car_class = car_class
    g.motion.car_speed = speed
    g.engine.water_temp = water
    g.engine.oil_temp = oil
    g.engine.rpm = rpm
    g.engine.gear = gear
    g.engine.max_rpm = max_rpm
    g.engine.overheating = overheating
    return g


class TestSilentFailures:
    def test_silent_no_warning_below_min_samples(self):
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)
        for _ in range(5):
            ev.trigger_internal(None, _gsd(water=120))
        assert len(ap.messages) == 0

    def test_silent_not_stall_when_stationary(self):
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)
        for _ in range(10):
            ev.trigger_internal(None, _gsd(rpm=0, gear=1, speed=0))
        assert len(ap.messages) == 0

    def test_silent_skip_when_garage(self):
        ev = EngineMonitor()
        assert not ev.is_applicable(SessionType.RACE, SessionPhase.GARAGE)

    def test_clear_state_empties_samples(self):
        ev = EngineMonitor()
        for _ in range(15):
            ev.trigger_internal(None, _gsd(water=120))
        ev.clear_state()
        assert len(ev._water_samples) == 0


class TestPipelineIntegration:
    def test_water_overheating(self):
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)
        for _ in range(10):
            ev.trigger_internal(None, _gsd(water=115))
        names = [m.name for m in ap.messages]
        assert "engine_monitor/engine_overheating" in names

    def test_oil_overheating(self):
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)
        for _ in range(10):
            ev.trigger_internal(None, _gsd(oil=135))
        names = [m.name for m in ap.messages]
        assert "engine_monitor/oil_overheating" in names

    def test_overheating_icon_triggers_immediately(self):
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)
        for _ in range(10):
            ev.trigger_internal(None, _gsd(overheating=True))
        names = [m.name for m in ap.immediate_messages]
        assert "engine_monitor/engine_overheating" in names

    def test_engine_stall(self):
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)
        for _ in range(10):
            ev.trigger_internal(None, _gsd(water=90))
        ap.clear()
        ev.trigger_internal(None, _gsd(rpm=0, gear=2, speed=5))
        names = [m.name for m in ap.immediate_messages]
        assert "engine_monitor/engine_stalled" in names
