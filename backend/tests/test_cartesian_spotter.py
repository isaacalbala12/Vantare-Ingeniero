"""Tests del detector cartesian (estilo Crew Chief)."""

from __future__ import annotations

import pytest

from src.intelligence.cartesian_spotter import detect_cartesian_overlap, resolve_player_forward_xz
from tests.fixtures.spotter.helpers import load_frame


@pytest.fixture
def world_overlap_frame():
    return load_frame("world_overlap_no_path_delta")


class TestCartesianSpotter:
    def test_detects_right_with_zero_path_delta(self, world_overlap_frame):
        frame = world_overlap_frame
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
        assert hits[0].driver_index == 7

    def test_no_hit_when_longitudinally_far(self, world_overlap_frame):
        frame = world_overlap_frame
        comp = dict(frame["competitors"][0])
        comp["pos_z"] = frame["pos_z"] + 25.0
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
        assert hits == []

    def test_no_hit_when_diagonal_outside_window(self, world_overlap_frame):
        frame = world_overlap_frame
        comp = dict(frame["competitors"][0])
        comp["pos_x"] = frame["pos_x"] + 8.0
        comp["pos_z"] = frame["pos_z"] + 8.0
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
        assert hits == []

    def test_orientation_from_ori_fwd(self, world_overlap_frame):
        fwd = resolve_player_forward_xz(0.0, 1.0, 0.0, 0.0)
        assert fwd == (0.0, 1.0)

    def test_orientation_fallback_velocity(self):
        fwd = resolve_player_forward_xz(0.0, 0.0, 10.0, 0.0)
        assert abs(fwd[0] - 1.0) < 0.01
        assert abs(fwd[1]) < 0.01

    def test_excludes_pit_indices(self, world_overlap_frame):
        frame = world_overlap_frame
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
            exclude_indices={7},
        )
        assert hits == []

    def test_ranking_prefers_closer_longitudinal(self, world_overlap_frame):
        frame = world_overlap_frame
        near = dict(frame["competitors"][0])
        far = dict(frame["competitors"][0])
        far["driver_index"] = 8
        far["pos_z"] = frame["pos_z"] + 3.0
        fwd = resolve_player_forward_xz(
            frame["ori_fwd_x"],
            frame["ori_fwd_z"],
            frame["vel_x"],
            frame["vel_z"],
        )
        hits = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd,
            [far, near],
            lateral_threshold_m=3.0,
        )
        assert len(hits) == 2
        assert hits[0].driver_index == 7

    def test_three_wide_fixture_has_both_sides(self):
        frame = load_frame("three_wide")
        fwd = resolve_player_forward_xz(
            frame["ori_fwd_x"],
            frame["ori_fwd_z"],
            frame["vel_x"],
            frame["vel_z"],
        )
        hits = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd,
            frame["competitors"],
            lateral_threshold_m=3.0,
        )
        sides = {h.side for h in hits}
        assert "izquierda" in sides
        assert "derecha" in sides

    def test_lmu_invert_swaps_side(self, world_overlap_frame):
        frame = world_overlap_frame
        comp = frame["competitors"][0]
        fwd = resolve_player_forward_xz(
            frame["ori_fwd_x"], frame["ori_fwd_z"], frame["vel_x"], frame["vel_z"],
        )
        hits = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd, [comp], lateral_threshold_m=3.0, invert_lateral=True,
        )
        assert hits[0].side == "izquierda"

    def test_high_speed_wider_longitudinal_window(self, world_overlap_frame):
        frame = world_overlap_frame
        comp = dict(frame["competitors"][0])
        comp["pos_z"] = frame["pos_z"] + 12.0
        fwd = resolve_player_forward_xz(
            frame["ori_fwd_x"], frame["ori_fwd_z"], frame["vel_x"], frame["vel_z"],
        )
        slow = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd, [comp], lateral_threshold_m=3.0, player_speed_ms=5.0,
        )
        fast = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd, [comp], lateral_threshold_m=3.0, player_speed_ms=60.0,
        )
        assert slow == []
        assert len(fast) == 1

        frame = load_frame("pit_exclusion")
        fwd = resolve_player_forward_xz(
            frame["ori_fwd_x"],
            frame["ori_fwd_z"],
            frame["vel_x"],
            frame["vel_z"],
        )
        hits = detect_cartesian_overlap(
            (frame["pos_x"], frame["pos_y"], frame["pos_z"]),
            fwd,
            frame["competitors"],
            lateral_threshold_m=3.0,
            exclude_indices={99},
        )
        assert hits == []
