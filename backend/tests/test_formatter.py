"""Unit tests for the telemetry frame formatter."""

import pytest
from src.intelligence.formatter import format_event_text, _safe_float, _safe_int


class TestSafeFloat:
    def test_float_value(self) -> None:
        assert _safe_float(42.3) == 42.3

    def test_int_value(self) -> None:
        assert _safe_float(42) == 42.0

    def test_none_value(self) -> None:
        assert _safe_float(None) == 0.0

    def test_string_num(self) -> None:
        assert _safe_float("42.5") == 42.5

    def test_invalid_string(self) -> None:
        assert _safe_float("abc") == 0.0


class TestFormatEventText:
    def _make_frame(self, overrides: dict | None = None) -> dict:
        """Helper para crear un frame base con valores por defecto."""
        base = {
            "lap_number": 10,
            "standing_position": 3,
            "fuel_in_tank": 42.3,
            "tyre_wear_fl": 72.0,
            "tyre_wear_fr": 68.0,
            "tyre_wear_rl": 65.0,
            "tyre_wear_rr": 63.0,
            "safety_car_active": False,
            "yellow_flag_active": False,
            "full_course_yellow_active": False,
            "time_gap_place_ahead": 2.1,
            "time_gap_place_behind": 0.0,
            "speed": 180.5,
            "cloud_coverage": 2,
            "raining": 0.0,
            "avg_path_wetness": 0.0,
            "ambient_temp": 22.0,
            "track_temp": 35.0,
            "drs_state": False,
            "rear_flap_activated": False,
            "pit_state": 0,
            "battery_charge": 85.0,
            "dent_severity_avg": 5.0,
        }
        if overrides:
            base.update(overrides)
        return base

    def test_normal_frame(self) -> None:
        frame = self._make_frame()
        result = format_event_text(frame, "lap_completed", 10)
        # Should include T (lap > 3)
        assert "T72/68/65/63" in result
        assert "L10" in result
        assert "P3" in result
        assert "F42.3" in result
        assert "Elap_completed" in result

    def test_lap_3_omits_tyres(self) -> None:
        frame = self._make_frame()
        result = format_event_text(frame, "pit_entry", 3)
        # Should NOT include T (lap <= 3)
        assert "T" not in result.split("|")[3]
        assert "|SCN|" in result

    def test_safety_car_active(self) -> None:
        frame = self._make_frame({"safety_car_active": True})
        result = format_event_text(frame, "safety_car", 15)
        assert "SCS" in result

    def test_negative_gap_behind(self) -> None:
        frame = self._make_frame({
            "time_gap_place_ahead": 0.0,
            "time_gap_place_behind": 1.2,
        })
        result = format_event_text(frame, "gap_change", 12)
        assert "G-1.2" in result

    def test_drs_active(self) -> None:
        frame = self._make_frame({"drs_state": True})
        result = format_event_text(frame, "position_change", 20)
        assert "DRSS" in result

    def test_missing_fields(self) -> None:
        frame = {"lap_number": 5, "speed": None}
        result = format_event_text(frame, "lap_completed", 5)
        # Should not crash, defaults applied
        assert "L5" in result
        assert "P0" in result  # default when missing
        assert "SCN" in result
        assert "F0.0" in result

    def test_full_example(self) -> None:
        """Coincide con el ejemplo del orchestrator.md: Safety Car V26 P3 lluvia ligera."""
        frame = self._make_frame({
            "lap_number": 26,
            "standing_position": 3,
            "fuel_in_tank": 42.3,
            "tyre_wear_fl": 72.0,
            "tyre_wear_fr": 68.0,
            "tyre_wear_rl": 65.0,
            "tyre_wear_rr": 63.0,
            "safety_car_active": True,
            "yellow_flag_active": True,
            "time_gap_place_ahead": 2.1,
            "speed": 180.0,
            "cloud_coverage": 6,
            "raining": 0.3,
            "avg_path_wetness": 0.4,
            "ambient_temp": 22.0,
            "track_temp": 30.0,
            "drs_state": False,
            "pit_state": 0,
            "battery_charge": 85.0,
            "dent_severity_avg": 12.0,
        })
        result = format_event_text(frame, "safety_car", 26)
        assert result == (
            "L26|P3|F42.3|T72/68/65/63|SCS|YFS|G+2.1|S180|"
            "CLD6|RAIN0.3|WET0.4|A22|TEMP30|DRSN|PIT0|BAT85|D12|Esafety_car"
        )