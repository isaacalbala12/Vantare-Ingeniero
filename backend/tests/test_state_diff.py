import pytest
from src.services.state_diff import StateDiff, TickChanges


def _make_flat(lap=1, sector=1, phase=5, place=1, running_time=10.0):
    return {
        "lap_number": lap,
        "sector_number": sector,
        "session_phase": phase,
        "session_running_time": running_time,
        "place": place,
        "driver_name": "Player",
        "leader_raw_name": "Leader",
        "rivals": [],
    }


def test_first_update_no_changes():
    diff = StateDiff()
    changes = diff.update(_make_flat())
    assert isinstance(changes, TickChanges)
    assert not changes.position_changed


def test_new_lap_detected():
    diff = StateDiff()
    diff.update(_make_flat(lap=1))
    changes = diff.update(_make_flat(lap=2))
    assert changes.new_lap


def test_new_sector_detected():
    diff = StateDiff()
    diff.update(_make_flat(sector=1))
    changes = diff.update(_make_flat(sector=2))
    assert changes.new_sector


def test_session_phase_changed():
    diff = StateDiff()
    diff.update(_make_flat(phase=5))
    changes = diff.update(_make_flat(phase=6))
    assert changes.session_phase_changed


def test_leader_changed():
    diff = StateDiff()
    diff.update(_make_flat())
    changes = diff.update({**_make_flat(), "leader_raw_name": "NewLeader"})
    assert changes.leader_changed


def test_retired_drivers():
    diff = StateDiff()
    diff.update(_make_flat())
    prev_rivals = [
        {"driver_raw_name": "Alice", "in_pits": False},
        {"driver_raw_name": "Bob", "in_pits": False},
    ]
    diff._prev_rivals = {r["driver_raw_name"]: r for r in prev_rivals}
    changes = diff.update({
        **_make_flat(),
        "rivals": [{"driver_raw_name": "Alice", "in_pits": False}],
    })
    assert "Bob" in changes.retired_drivers


def test_pit_entry_detected():
    diff = StateDiff()
    diff.update(_make_flat())
    prev_rivals = [{"driver_raw_name": "Alice", "in_pits": False}]
    diff._prev_rivals = {r["driver_raw_name"]: r for r in prev_rivals}
    changes = diff.update({
        **_make_flat(),
        "rivals": [{"driver_raw_name": "Alice", "in_pits": True}],
    })
    assert "Alice" in changes.pit_entries


def test_pit_exit_detected():
    diff = StateDiff()
    diff.update(_make_flat())
    prev_rivals = [{"driver_raw_name": "Alice", "in_pits": True}]
    diff._prev_rivals = {r["driver_raw_name"]: r for r in prev_rivals}
    changes = diff.update({
        **_make_flat(),
        "rivals": [{"driver_raw_name": "Alice", "in_pits": False}],
    })
    assert "Alice" in changes.pit_exits
