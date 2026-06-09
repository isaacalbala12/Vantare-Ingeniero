"""Tests Wave 8 — triggers de eventos R3."""

import pytest

from src.intelligence.triggers import (
    FlagsMonitorTrigger,
    MulticlassWarningTrigger,
    DriverSwapTrigger,
    PenaltyMonitorTrigger,
    PushNowTrigger,
    SessionEndTrigger,
)


class TestFlagsMonitorTrigger:
    @pytest.fixture
    def trigger(self):
        return FlagsMonitorTrigger()

    def test_triggers_on_safety_car(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        trigger.condition(telemetry, mock_strategy_dict, mock_session_dict)
        telemetry["safety_car_active"] = True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

    def test_triggers_on_blue_flag_edge(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        trigger.condition(telemetry, mock_strategy_dict, mock_session_dict)
        telemetry["blue_flag_active"] = True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert "azul" in trigger.alert_text.lower()


class TestMulticlassWarningTrigger:
    @pytest.fixture
    def trigger(self):
        return MulticlassWarningTrigger()

    def test_hypercar_approaching_from_behind(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["player_class"] = "GT3"
        strategy = {
            **mock_strategy_dict,
            "competitors": [
                {
                    "driver_class": "Hypercar",
                    "gap_to_player": -1.5,
                    "in_pits": False,
                }
            ],
        }
        assert trigger.condition(telemetry, strategy, mock_session_dict) is True
        assert "HYPERCAR" in trigger.alert_text.upper()

    def test_slower_class_ahead_to_lap(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["player_class"] = "Hypercar"
        strategy = {
            **mock_strategy_dict,
            "competitors": [
                {
                    "driver_class": "GT3",
                    "gap_to_player": 0.8,
                    "in_pits": False,
                }
            ],
        }
        assert trigger.condition(telemetry, strategy, mock_session_dict) is True
        assert "doblar" in trigger.alert_text.lower()


class TestDriverSwapTrigger:
    @pytest.fixture
    def trigger(self):
        return DriverSwapTrigger()

    def test_detects_driver_change(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["driver_name"] = "Fernando Alonso"
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False

        telemetry["driver_name"] = "Lewis Hamilton"
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert "Hamilton" in trigger.alert_text


class TestPenaltyMonitorTrigger:
    @pytest.fixture
    def trigger(self):
        return PenaltyMonitorTrigger()

    def test_disabled_in_wave1(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        """Wave 1: penalizaciones las gestiona ProactiveMonitorSuite."""
        telemetry = dict(mock_telemetry_dict)
        telemetry["num_penalties"] = 1
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False


class TestPushNowTrigger:
    @pytest.fixture
    def trigger(self):
        return PushNowTrigger()

    def test_last_laps(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["session_type"] = "race"
        telemetry["session_laps_left"] = 2
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True

    def test_undercut_window(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["session_type"] = "race"
        telemetry["session_laps_left"] = 20
        telemetry["gap_behind"] = 1.0
        strategy = {
            **mock_strategy_dict,
            "pit_window": {"undercut_potential": True},
        }
        assert trigger.condition(telemetry, strategy, mock_session_dict) is True


class TestSessionEndTrigger:
    @pytest.fixture
    def trigger(self):
        return SessionEndTrigger()

    def test_final_lap(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["lap_number"] = 10
        telemetry["session_laps_left"] = 1
        telemetry["standing_position"] = 3
        telemetry["lap_time_best"] = 102.456
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert "P3" in trigger.alert_text

    def test_fires_once(self, trigger, mock_telemetry_dict, mock_strategy_dict, mock_session_dict):
        telemetry = dict(mock_telemetry_dict)
        telemetry["lap_number"] = 10
        telemetry["session_laps_left"] = 0.5
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is True
        assert trigger.condition(telemetry, mock_strategy_dict, mock_session_dict) is False
