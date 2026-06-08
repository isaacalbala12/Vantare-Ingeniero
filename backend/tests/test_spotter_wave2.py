"""Tests Wave 2 — spotter avanzado."""

import time

import pytest

from src.intelligence.spotter import SpotterService
from src.intelligence.spotter_geometry import (
    build_proximity_message,
    detect_lateral_proximity,
    detect_path_lateral_proximity,
)
from shared_strategy.vehicle_lookup import get_vehicle_width


@pytest.fixture
def spotter(mock_broadcast):
    return SpotterService(
        broadcast_callback=mock_broadcast,
        proximity_threshold_m=3.0,
        invert_lateral=False,
    )


@pytest.fixture
def base_tick():
    return {
        "in_pits": False,
        "pit_limiter_active": False,
        "gap_ahead": 5.0,
        "gap_behind": 5.0,
        "damage_aero": 0.0,
        "suspension_damage": 0.0,
        "safety_car_active": False,
        "full_course_yellow_active": False,
        "session_laps_left": 10.0,
        "estimated_laps_remaining": 10.0,
        "session_type": "race",
        "lap_number": 3,
        "lap_distance": 1200.0,
        "path_lateral": 0.0,
        "pos_x": 0.0,
        "pos_y": 0.0,
        "pos_z": 0.0,
        "vel_x": 0.0,
        "vel_y": 0.0,
        "vel_z": 30.0,
        "player_class": "GT3",
        "vehicle_name": "Porsche 911 GT3 R",
        "competitors": [],
    }


class TestLateralProximity:
    def test_car_detected_to_the_right(self):
        hits = detect_lateral_proximity(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 30.0),
            [{"driver_index": 1, "driver_class": "GT3", "pos_x": 2.0, "pos_y": 0.0, "pos_z": 5.0, "speed": 20.0}],
            3.0,
        )
        assert len(hits) == 1
        assert hits[0].side == "derecha"

    def test_car_detected_to_the_left(self):
        hits = detect_lateral_proximity(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 30.0),
            [{"driver_index": 2, "driver_class": "GT3", "pos_x": -2.0, "pos_y": 0.0, "pos_z": 5.0, "speed": 20.0}],
            3.0,
        )
        assert len(hits) == 1
        assert hits[0].side == "izquierda"

    def test_no_alert_when_car_is_far(self):
        hits = detect_lateral_proximity(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 30.0),
            [{"driver_index": 3, "driver_class": "GT3", "pos_x": 10.0, "pos_y": 0.0, "pos_z": 20.0, "speed": 20.0}],
            3.0,
        )
        assert hits == []


class TestPathLateralProximity:
    def test_side_by_side_on_same_lap(self):
        hits = detect_path_lateral_proximity(
            3,
            1200.0,
            0.0,
            [
                {
                    "driver_index": 9,
                    "driver_class": "GT3",
                    "driver_name": "Rival",
                    "lap_number": 3,
                    "lap_distance": 1203.0,
                    "path_lateral": 2.5,
                }
            ],
            4.0,
        )
        assert len(hits) == 1
        assert hits[0].side == "derecha"

    def test_spotter_path_proximity_alert(self, spotter, base_tick):
        tick = dict(base_tick)
        tick["competitors"] = [
            {
                "driver_index": 10,
                "driver_class": "Hypercar",
                "driver_name": "Fast",
                "lap_number": 3,
                "lap_distance": 1205.0,
                "path_lateral": -2.2,
                "speed": 30.0,
                "in_pits": False,
            }
        ]
        alerts = spotter.evaluate(tick)
        prox = [a for a in alerts if a.category == "proximity"]
        assert len(prox) == 1
        assert "izquierda" in prox[0].message.lower()


class TestSpotterWave2:
    def test_proximity_alert_right(self, spotter, base_tick):
        tick = dict(base_tick)
        tick["competitors"] = [
            {
                "driver_index": 5,
                "driver_class": "GT3",
                "driver_name": "Rival",
                "pos_x": 2.0,
                "pos_y": 0.0,
                "pos_z": 5.0,
                "speed": 25.0,
                "in_pits": False,
            }
        ]
        alerts = spotter.evaluate(tick)
        prox = [a for a in alerts if a.category == "proximity"]
        assert len(prox) == 1
        assert "derecha" in prox[0].message.lower()

    def test_multiclass_hypercar_lapping(self, spotter, base_tick):
        tick = dict(base_tick)
        tick["competitors"] = [
            {
                "driver_index": 6,
                "driver_class": "Hypercar",
                "driver_name": "Villeneuve",
                "pos_x": 2.0,
                "pos_y": 0.0,
                "pos_z": 5.0,
                "speed": 35.0,
                "in_pits": False,
            }
        ]
        alerts = spotter.evaluate(tick)
        prox = [a for a in alerts if a.category == "proximity"][0]
        assert "doblando" in prox.message.lower()
        assert "derecha" in prox.message.lower()

    def test_qualifying_silent_except_sc_and_fuel(self, spotter, base_tick):
        tick = dict(base_tick)
        tick["session_type"] = "qualifying"
        tick["gap_ahead"] = 0.2
        alerts = spotter.evaluate(tick)
        assert not any(a.category == "gaps" for a in alerts)

        tick["safety_car_active"] = True
        alerts = spotter.evaluate(tick)
        assert any(a.category == "safety_car" for a in alerts)

        tick["safety_car_active"] = False
        tick["estimated_laps_remaining"] = 0.4
        alerts = spotter.evaluate(tick)
        assert any(a.category == "fuel" for a in alerts)

    def test_qualifying_can_be_disabled(self, mock_broadcast, base_tick):
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            spotter_off_qualifying=False,
        )
        tick = dict(base_tick)
        tick["session_type"] = "qualifying"
        tick["gap_ahead"] = 0.2
        alerts = spotter.evaluate(tick)
        assert any(a.category == "gaps" for a in alerts)

    def test_pitted_competitor_ignored(self, spotter, base_tick):
        tick = dict(base_tick)
        tick["competitors"] = [
            {
                "driver_index": 7,
                "driver_class": "GT3",
                "pos_x": 1.0,
                "pos_y": 0.0,
                "pos_z": 2.0,
                "speed": 0.0,
                "in_pits": True,
            }
        ]
        alerts = spotter.evaluate(tick)
        assert not any(a.category == "proximity" for a in alerts)

    def test_stationary_competitor_excluded_after_grace(self, spotter, base_tick):
        tick = dict(base_tick)
        comp = {
            "driver_index": 8,
            "driver_class": "GT3",
            "pos_x": 1.5,
            "pos_y": 0.0,
            "pos_z": 4.0,
            "speed": 0.0,
            "in_pits": False,
        }
        tick["competitors"] = [comp]
        spotter._stopped_since[8] = time.monotonic() - 6.0
        alerts = spotter.evaluate(tick)
        assert not any(a.category == "proximity" for a in alerts)

    def test_spotter_disabled_returns_no_alerts(self, spotter, base_tick):
        spotter.enabled = False
        tick = dict(base_tick)
        tick["safety_car_active"] = True
        assert spotter.evaluate(tick) == []

    def test_build_proximity_message_multiclass(self):
        msg = build_proximity_message("GT3", "Hypercar", "X", "derecha")
        assert msg == "Hypercar doblando por la derecha"


class TestVehicleLookup:
    def test_known_vehicle_width(self):
        assert get_vehicle_width("Ferrari 499P", 2.0) == 2.0

    def test_unknown_vehicle_uses_class_fallback(self):
        assert get_vehicle_width("Coche Desconocido", 2.05) == 2.05
