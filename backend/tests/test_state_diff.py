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


def test_anti_bounce_position_oscillation():
    """Posición oscila 3→5→4→4→4, debe reportar cambio a 4 tras settle."""
    diff = StateDiff()
    t0 = 1000.0

    # Tick 1: pos=3
    diff.update(_make_flat(place=3), t0)
    diff._last_confirmed_position = 3

    # Tick 2: pos=5 (inicia pending)
    c = diff.update(_make_flat(place=5), t0 + 0.1)
    assert not c.position_changed  # Pendiente, no reportado

    # Tick 3: pos=4 (sobrescribe pending)
    c = diff.update(_make_flat(place=4), t0 + 0.2)
    assert not c.position_changed  # Nuevo pending

    # Tick 4: pos=4 estable, pending settle time pasado
    c = diff.update(_make_flat(place=4), t0 + 2.0)
    assert c.position_changed  # Debe reportar
    assert c.new_position == 4
    assert c.old_position == 3  # Desde la última posición confirmada
