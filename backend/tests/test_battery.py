"""Tests para BatteryEvent — integracion, silent failures, cross-event."""

import time
import pytest

from src.intelligence.events.battery import BatteryEvent
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


def _gsd(ve_pct=50, laps=5, phase=SessionPhase.GREEN, car_class="GT3"):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.session.completed_laps = laps
    g.car_class = car_class
    g.battery.percentage = ve_pct
    return g


class TestSilentFailures:
    def test_silent_skip_when_no_battery(self):
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)
        ev.trigger_internal(None, _gsd(ve_pct=0))
        assert len(ap.messages) == 0

    def test_no_false_low_with_zero_laps(self):
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)
        ev.trigger_internal(None, _gsd(ve_pct=10, laps=0))
        assert len(ap.messages) == 0


class TestPipelineIntegration:
    def test_low_battery_warning(self):
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)
        ev.trigger_internal(None, _gsd(ve_pct=20))
        names = [m.name for m in ap.messages]
        assert "battery/battery_low" in names

    def test_critical_battery_warning(self):
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)
        ev.trigger_internal(None, _gsd(ve_pct=5))
        names = [m.name for m in ap.immediate_messages]
        assert "battery/battery_critical" in names

    def test_recharge_detected(self):
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)
        ev.trigger_internal(None, _gsd(ve_pct=20))
        ap.clear()
        ev.trigger_internal(None, _gsd(ve_pct=80))
        names = [m.name for m in ap.messages]
        assert "battery/recharge_complete" in names


class TestSilentState:
    def test_clear_state_prevents_stale_warnings(self):
        ev = BatteryEvent()
        ev.trigger_internal(None, _gsd(ve_pct=5))
        ev.clear_state()
        ap = FakeAudioPlayer()
        ev.audio_player = ap
        ev.trigger_internal(None, _gsd(ve_pct=5))
        names = [m.name for m in ap.immediate_messages]
        assert "battery/battery_critical" in names
