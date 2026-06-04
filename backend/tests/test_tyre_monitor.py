"""Tests para TyreMonitor — pipeline, silent failures, cross-event."""

import time
import pytest
from dataclasses import replace

from src.intelligence.events.tyre_monitor import TyreMonitor
from src.intelligence.base_event import FakeAudioPlayer
from src.models.game_state_data import GameStateData, TyreData
from src.models.enums import SessionType, SessionPhase


def _gsd(phase=SessionPhase.GREEN, car_class="GT3", fl_temp=90, fr_temp=90,
         rl_temp=90, rr_temp=90, fl_wear=0, fr_wear=0, rl_wear=0, rr_wear=0,
         fl_press=160, fr_press=160, rl_press=160, rr_press=160,
         compound="Soft", speed=30.0):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.car_class = car_class
    g.motion.car_speed = speed
    g.tyre.fl_temp = fl_temp
    g.tyre.fr_temp = fr_temp
    g.tyre.rl_temp = rl_temp
    g.tyre.rr_temp = rr_temp
    g.tyre.fl_wear = fl_wear
    g.tyre.fr_wear = fr_wear
    g.tyre.rl_wear = rl_wear
    g.tyre.rr_wear = rr_wear
    g.tyre.fl_pressure = fl_press
    g.tyre.fr_pressure = fr_press
    g.tyre.rl_pressure = rl_press
    g.tyre.rr_pressure = rr_press
    g.tyre.fl_compound = compound
    g.tyre.fr_compound = compound
    g.tyre.rl_compound = compound
    g.tyre.rr_compound = compound
    return g


class TestSilentFailures:
    def test_no_lockup_when_stopped(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        g = _gsd(fl_temp=90, speed=0)
        ev.trigger_internal(None, g)
        g2 = _gsd(fl_temp=110, fl_press=140, speed=0)
        ev._prev_temps = [90, 90, 90, 90]
        ev._prev_pressures = [160, 160, 160, 160]
        ev.trigger_internal(None, g2)
        names = [m.name for m in ap.messages]
        assert all("locking" not in n for n in names)

    def test_missing_compound_fallback(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(compound="Unknown_Race"))
        ev.trigger_internal(None, _gsd(compound="Unknown_Race"))
        assert len(ap.messages) == 0  # No compound change on first init or same unknown


class TestPipelineIntegration:
    def test_overheating_detected(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(fl_temp=115))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/fl_overheating" in names

    def test_cold_tyres_detected(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(fl_temp=50))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/fl_cold" in names

    def test_lockup_detected(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(fl_temp=90, fl_press=160))
        ev.trigger_internal(None, _gsd(fl_temp=108, fl_press=153))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/fl_locking" in names

    def test_wear_warning(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(fl_wear=0.85))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/wear_warning" in names

    def test_pressure_high(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(fl_press=230))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/fl_pressure_high" in names

    def test_pressure_low(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(fl_press=80))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/fl_pressure_low" in names

    def test_compound_change(self):
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)
        ev.trigger_internal(None, _gsd(compound="Soft"))
        ap.clear()
        ev.trigger_internal(None, _gsd(compound="Hard"))
        names = [m.name for m in ap.messages]
        assert "tyre_monitor/compound_change" in names
