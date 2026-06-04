"""Tests para DamageReporting — pipeline, silent failures, cross-event."""

import time
import pytest

from src.intelligence.events.damage_reporting import DamageReporting
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


def _gsd(phase=SessionPhase.GREEN, impact_time=-1.0, impact_mag=0.0,
         aero="NONE", suspension=None, fl_press=160, speed=30, roll=0, pitch=0):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.car_class = "GT3"
    g.motion.car_speed = speed
    g.motion.orientation.roll = roll
    g.motion.orientation.pitch = pitch
    g.tyre.fl_pressure = fl_press
    g.tyre.fr_pressure = fl_press
    g.tyre.rl_pressure = fl_press
    g.tyre.rr_pressure = fl_press
    g.damage.last_impact_time = impact_time
    g.damage.last_impact_magnitude = impact_mag
    g.damage.aero = aero
    if suspension:
        g.damage.suspension = suspension
    return g


class TestSilentFailures:
    def test_silent_skip_when_no_damage(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd())
        assert len(ap.messages) == 0

    def test_no_impact_when_magnitude_zero(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(impact_time=1.0, impact_mag=0))
        assert len(ap.messages) == 0

    def test_not_rollover_when_moving(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(roll=80, speed=30))
        assert len(ap.messages) == 0

    def test_not_puncture_when_moving(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(fl_press=2, speed=30))
        assert len(ap.messages) == 0


class TestPipelineIntegration:
    def test_impact_detected(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(impact_time=100.0, impact_mag=3.0))
        names = [m.name for m in ap.messages]
        assert "damage/damage_reporting" in names

    def test_heavy_impact_sets_driver_ok_flag(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(impact_time=100.0, impact_mag=10.0))
        assert event_flags.waiting_for_driver_is_ok_response
        event_flags.waiting_for_driver_is_ok_response = False

    def test_aero_damage(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(aero="MINOR"))
        names = [m.name for m in ap.messages]
        assert "damage/aero_damage" in names

    def test_suspension_damage(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(suspension=["MINOR", "NONE", "NONE", "NONE"]))
        names = [m.name for m in ap.messages]
        assert "damage/suspension_fl" in names

    def test_puncture_when_stopped(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(fl_press=2, speed=1))
        names = [m.name for m in ap.immediate_messages]
        assert any("puncture" in n for n in names)

    def test_rollover_when_stopped(self):
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)
        ev.trigger_internal(None, _gsd(roll=50, speed=0))
        names = [m.name for m in ap.immediate_messages]
        assert any("rollover" in n for n in names)
