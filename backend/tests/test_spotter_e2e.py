"""E2E spotter: fixtures → adapter → SpotterService → AlertMessage."""

from __future__ import annotations

from src.intelligence.spotter import SpotterService
from src.intelligence.spotter_adapter import frame_to_spotter_tick
from tests.fixtures.spotter.helpers import assert_alerts_over_sequence, load_frame, load_tick_sequence


class TestSpotterE2E:
    def test_world_overlap_fixture_broadcasts_proximity(self, mock_broadcast, broadcast_messages):
        frame = load_frame("world_overlap_no_path_delta")
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            spotter_off_qualifying=False,
            invert_lateral=False,
            enabled=True,
        )
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        assert_alerts_over_sequence(broadcast_messages, min_proximity=1, max_proximity=2)

    def test_tick_sequence_emits_proximity_with_antispam(self, mock_broadcast, broadcast_messages):
        ticks = load_tick_sequence("tick_sequence_overtake")
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            spotter_off_qualifying=False,
            invert_lateral=False,
            enabled=True,
        )
        for frame in ticks:
            spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))

        prox = [m for m in broadcast_messages if m.category == "proximity" and not m.payload.get("clear")]
        assert len(prox) >= 1
        assert len(prox) <= 3

    def test_ws_contract_fields(self, mock_broadcast, broadcast_messages):
        frame = load_frame("side_by_side_gt3_hypercar")
        spotter = SpotterService(broadcast_callback=mock_broadcast, proximity_threshold_m=3.0, invert_lateral=False, enabled=True)
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        alert = next(m for m in broadcast_messages if m.category == "proximity")
        payload = alert.model_dump(mode="json")
        assert payload["event"] == "alert"
        assert payload["message"]
        assert payload["category"] == "proximity"
        assert payload["severity"]
        assert int(payload["audio_priority"]) >= 2

    def test_pit_exclusion_no_proximity(self, mock_broadcast, broadcast_messages):
        frame = load_frame("pit_exclusion")
        spotter = SpotterService(broadcast_callback=mock_broadcast, proximity_threshold_m=3.0, invert_lateral=False, enabled=True)
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        assert not any(m.category == "proximity" for m in broadcast_messages)

    def test_three_wide_emits_single_high_alert(self, mock_broadcast, broadcast_messages):
        frame = load_frame("three_wide")
        spotter = SpotterService(broadcast_callback=mock_broadcast, proximity_threshold_m=3.0, invert_lateral=False, enabled=True)
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        prox = [m for m in broadcast_messages if m.category == "proximity"]
        assert len(prox) == 1
        assert prox[0].severity == "HIGH"
        assert prox[0].payload.get("three_wide") is True

    def test_three_wide_with_lmu_invert(self, mock_broadcast, broadcast_messages):
        frame = load_frame("three_wide")
        spotter = SpotterService(
            broadcast_callback=mock_broadcast,
            proximity_threshold_m=3.0,
            invert_lateral=True,
            enabled=True,
        )
        spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
        prox = [m for m in broadcast_messages if m.category == "proximity"]
        assert len(prox) == 1
        assert prox[0].payload.get("three_wide") is True
