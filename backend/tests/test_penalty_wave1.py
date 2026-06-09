"""F4 — PenaltyTracker countdown."""

from src.intelligence.penalty_tracker import PenaltyTracker


def test_penalty_new_starts_countdown():
    tracker = PenaltyTracker()
    result = tracker.evaluate(1, 5, 1, False)
    assert result is not None
    assert "3 vueltas" in result.message


def test_penalty_countdown_2_laps():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    tracker._last_num = 1
    result = tracker.evaluate(1, 7, 1, False)
    assert result is not None
    assert "2 vueltas" in result.message


def test_penalty_served_clears():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    tracker._last_num = 1
    result = tracker.evaluate(0, 7, 1, False)
    assert result is not None
    assert "cumplida" in result.message
    assert tracker._state == "CLEAR"


def test_penalty_pit_now_sector_3():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    tracker._last_num = 1
    result = tracker.evaluate(1, 7, 0, False)  # mSector 0 = sector 3
    assert result is not None
    assert "Entra a boxes ahora" in result.message


def test_penalty_disqualified_after_three_laps():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    tracker._last_num = 1
    result = tracker.evaluate(1, 8, 1, False)
    assert result is not None
    assert result.event_id == "penalty_disqualified"
    assert "descalificado" in result.message.lower()


def test_cut_track_warning_on_steps_increase():
    tracker = PenaltyTracker()
    first = tracker.evaluate_cut_track(1, now=0.0)
    assert first is not None
    assert "cuidado" in first.message.lower()
    assert tracker.evaluate_cut_track(1, now=1.0) is None
    second = tracker.evaluate_cut_track(2, now=31.0)
    assert second is not None
    assert "penaliz" in second.message.lower()
