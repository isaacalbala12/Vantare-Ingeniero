"""Tests para gate de combustible crítico vs fin de carrera."""

import pytest

from src.intelligence.fuel_safety import (
    fuel_critical_from_strategy,
    fuel_critical_from_tick,
    is_fuel_autonomy_critical,
)
from src.intelligence.triggers import FuelCriticalTrigger


class TestIsFuelAutonomyCritical:
    def test_low_autonomy_but_covers_race_laps(self):
        assert is_fuel_autonomy_critical(
            estimated_laps_remaining=2.5,
            critical_threshold=3.0,
            session_laps_left=2.0,
            pit_stops_needed=0,
        ) is False

    def test_low_autonomy_needs_stop(self):
        assert is_fuel_autonomy_critical(
            estimated_laps_remaining=2.5,
            critical_threshold=3.0,
            session_laps_left=15.0,
            pit_stops_needed=1,
        ) is True

    def test_fuel_in_tank_covers_finish_without_pit_stops_field(self):
        assert is_fuel_autonomy_critical(
            estimated_laps_remaining=2.0,
            critical_threshold=3.0,
            session_laps_left=10.0,
            fuel_in_tank=50.0,
            fuel_needed_to_finish=45.0,
        ) is False

    def test_above_threshold_not_critical(self):
        assert is_fuel_autonomy_critical(
            estimated_laps_remaining=4.0,
            critical_threshold=3.0,
            session_laps_left=2.0,
            pit_stops_needed=0,
        ) is False


class TestFuelCriticalTriggerFinishSafe:
    @pytest.fixture
    def trigger(self):
        return FuelCriticalTrigger()

    def test_no_trigger_when_finish_on_current_fuel(self, trigger, mock_telemetry_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["session_laps_left"] = 2.0
        telemetry["fuel_in_tank"] = 45.0
        strategy = {
            "fuel": {
                "estimated_laps_remaining": 2.5,
                "fuel_needed_to_finish": 40.0,
                "pit_stops_needed": 0,
                "fuel_in_tank": 45.0,
            }
        }
        assert trigger.condition(telemetry, strategy, mock_session_dict) is False

    def test_triggers_when_stop_required(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        strategy = dict(mock_strategy_dict)
        strategy["fuel"]["estimated_laps_remaining"] = 2.5
        strategy["fuel"]["pit_stops_needed"] = 1
        assert trigger.condition(mock_telemetry_dict, strategy, mock_session_dict) is True

    def test_spotter_tick_finish_safe(self):
        tick = {
            "fuel_laps_remaining": 0.8,
            "session_laps_left": 0.5,
            "pit_stops_needed": 0,
            "fuel_in_tank": 30.0,
            "fuel_needed_to_finish": 25.0,
        }
        assert fuel_critical_from_tick(tick, threshold=1.0) is False

    def test_strategy_helper_matches_trigger(self, mock_telemetry_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["session_laps_left"] = 2.0
        strategy = {
            "fuel": {
                "estimated_laps_remaining": 2.2,
                "fuel_needed_to_finish": 38.0,
                "pit_stops_needed": 0,
            }
        }
        assert fuel_critical_from_strategy(telemetry, strategy, threshold=3.0) is False
