"""
Pipeline spotter proximidad sin LMU.

Simula un frame sidecar (mPathLateral + mLapDist) y verifica:
  sidecar frame → spotter_adapter → SpotterService → AlertMessage (WS)

Ejecutar:
  pytest tests/test_spotter_proximity_pipeline.py -v
  python scripts/verify_spotter_pipeline.py
"""

from __future__ import annotations

import pytest

from src.intelligence.spotter import SpotterService
from src.intelligence.spotter_adapter import frame_to_spotter_tick
from src.intelligence.cartesian_spotter import detect_cartesian_overlap, resolve_player_forward_xz
from src.intelligence.spotter_geometry import detect_path_lateral_proximity
from tests.fixtures.spotter.helpers import load_frame
from src.models.messages import AlertMessage


def make_side_by_side_race_frame() -> dict:
    """Frame tipo sidecar: GT3 con Hypercar a la derecha en la misma vuelta."""
    return {
        "session_type": "race",
        "in_pits": False,
        "pit_limiter_active": False,
        "lap_number": 5,
        "lap_distance": 2400.0,
        "path_lateral": 0.0,
        "pos_x": 100.0,
        "pos_y": 0.0,
        "pos_z": 200.0,
        "vel_x": 0.0,
        "vel_y": 0.0,
        "vel_z": 35.0,
        "ori_fwd_x": 0.0,
        "ori_fwd_z": 1.0,
        "player_class": "GT3",
        "vehicle_name": "Porsche 911 GT3 R",
        "time_gap_car_ahead": 1.2,
        "time_gap_car_behind": 0.8,
        "competitors": [
            {
                "driver_index": 42,
                "driver_class": "Hypercar",
                "driver_name": "Villeneuve",
                "lap_number": 5,
                "lap_distance": 2404.0,
                "path_lateral": 2.6,
                "speed": 45.0,
                "in_pits": False,
                "pos_x": 102.0,
                "pos_y": 0.0,
                "pos_z": 205.0,
            }
        ],
    }


def make_world_only_miss_frame() -> dict:
    """Mismo rival pero sin offset lateral en path (solo mundo XZ lejano)."""
    frame = make_side_by_side_race_frame()
    frame["competitors"][0]["path_lateral"] = 0.05
    frame["competitors"][0]["lap_distance"] = 2600.0
    frame["competitors"][0]["pos_x"] = 150.0
    frame["competitors"][0]["pos_z"] = 280.0
    return frame


class TestProximityPipelineNoLMU:
    def test_path_geometry_detects_side_by_side(self):
        frame = make_side_by_side_race_frame()
        comp = frame["competitors"][0]
        hits = detect_path_lateral_proximity(
            frame["lap_number"],
            frame["lap_distance"],
            frame["path_lateral"],
            [comp],
            4.0,
        )
        assert len(hits) == 1
        assert hits[0].side == "derecha"

    def test_spotter_adapter_preserves_path_fields(self):
        frame = make_side_by_side_race_frame()
        tick = frame_to_spotter_tick(frame, advice=None)
        assert tick["lap_number"] == 5
        assert tick["path_lateral"] == 0.0
        assert tick["competitors"][0]["path_lateral"] == 2.6

    def test_full_pipeline_broadcasts_proximity_alert(self, mock_broadcast, broadcast_messages):
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            spotter_off_qualifying=False,
            invert_lateral=False,
            enabled=True,
        )
        frame = make_side_by_side_race_frame()
        tick = frame_to_spotter_tick(frame, advice=None)
        spotter.evaluate_tick(tick)

        prox = [m for m in broadcast_messages if getattr(m, "category", None) == "proximity"]
        assert len(prox) == 1
        alert = prox[0]
        assert isinstance(alert, AlertMessage)
        assert alert.event == "alert"
        assert alert.audio_priority == "2"
        assert "derecha" in alert.message.lower()
        assert "hypercar" in alert.message.lower() or "coche" in alert.message.lower()

    def test_path_based_beats_world_only_miss(self, mock_broadcast, broadcast_messages):
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            invert_lateral=False,
            enabled=True,
        )
        miss_tick = frame_to_spotter_tick(make_world_only_miss_frame(), advice=None)
        spotter.evaluate_tick(miss_tick)
        assert not any(getattr(m, "category", None) == "proximity" for m in broadcast_messages)

        broadcast_messages.clear()
        hit_tick = frame_to_spotter_tick(make_side_by_side_race_frame(), advice=None)
        spotter.evaluate_tick(hit_tick)
        assert any(getattr(m, "category", None) == "proximity" for m in broadcast_messages)

    def test_cartesian_detects_world_overlap_no_path_delta(self):
        frame = load_frame("world_overlap_no_path_delta")
        comp = frame["competitors"][0]
        fwd = resolve_player_forward_xz(
            frame["ori_fwd_x"],
            frame["ori_fwd_z"],
            frame["vel_x"],
            frame["vel_z"],
        )
        hits = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd,
            [comp],
            lateral_threshold_m=3.0,
        )
        assert len(hits) == 1
        assert hits[0].side == "derecha"

    def test_cartesian_pipeline_broadcasts_without_path_delta(self, mock_broadcast, broadcast_messages):
        frame = load_frame("world_overlap_no_path_delta")
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            invert_lateral=False,
            enabled=True,
        )
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        prox = [m for m in broadcast_messages if getattr(m, "category", None) == "proximity"]
        assert len(prox) == 1

    def test_alert_serializes_for_frontend_voice(self, mock_broadcast, broadcast_messages):
        """Payload JSON tal como lo recibe useWebSocket → shouldVoiceAlert (priority >= 2)."""
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            invert_lateral=False,
            enabled=True,
        )
        spotter.evaluate_tick(frame_to_spotter_tick(make_side_by_side_race_frame(), advice=None))
        alert = next(m for m in broadcast_messages if m.category == "proximity")
        payload = alert.model_dump(mode="json")

        assert payload["event"] == "alert"
        assert payload["category"] == "proximity"
        assert int(payload["audio_priority"]) >= 2
        assert payload["message"]

    def test_integrated_pipeline_uses_path_over_velocity(self, mock_broadcast, broadcast_messages):
        """path_lateral fiable debe ganar a proyección XZ cuando difieren."""
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=4.0,
            invert_lateral=True,
            enabled=True,
        )
        frame = make_side_by_side_race_frame()
        # Mundo XZ sugiere izquierda; path_lateral +2.6 → derecha (pista)
        frame["competitors"][0]["pos_x"] = 98.0
        frame["competitors"][0]["pos_z"] = 205.0
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        prox = [m for m in broadcast_messages if getattr(m, "category", None) == "proximity"]
        assert len(prox) == 1
        assert "derecha" in prox[0].message.lower()
