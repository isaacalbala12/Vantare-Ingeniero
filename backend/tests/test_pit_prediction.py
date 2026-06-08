"""Tests pit_prediction module."""

from src.intelligence.pit_prediction import (
    count_pit_context,
    estimate_position_after_pit_stop,
    format_pit_exit_prediction,
)


def test_estimate_position_after_pit():
    assert estimate_position_after_pit_stop(5, competitors_ahead_in_pits=2, competitors_behind_passing=1) == 4


def test_format_pit_exit_with_window():
    msg = format_pit_exit_prediction(5, 7, pit_window_open=True)
    assert msg is not None
    assert "Ventana de boxes" in msg
    assert "P7" in msg


def test_count_pit_context():
    competitors = [
        {"driver_index": 0, "standing_position": 5, "in_pits": False},
        {"driver_index": 1, "standing_position": 3, "in_pits": True},
        {"driver_index": 2, "standing_position": 8, "in_pits": False},
    ]
    ahead, behind = count_pit_context(competitors, player_index=0)
    assert ahead == 1
    assert behind == 1
