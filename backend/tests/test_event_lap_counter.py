"""Tests para LapCounter — detección de vueltas, warmup y primer vuelta tras pit."""

import time

import pytest

from src.intelligence.events.lap_counter import LapCounter
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase


@pytest.fixture(autouse=True)
def _clean_flags():
    event_flags.on_manual_formation_lap = False
    event_flags.last_lap_was_pit_lap = False
    yield
    event_flags.on_manual_formation_lap = False
    event_flags.last_lap_was_pit_lap = False


def _gsd(
    laps: int = 1,
    sector: int = 1,
    phase: SessionPhase = SessionPhase.GREEN,
    in_pitlane: bool = False,
    session_type: SessionType = SessionType.RACE,
):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = session_type
    g.session.session_phase = phase
    g.session.completed_laps = laps
    g.session.sector_number = sector
    g.pit.in_pitlane = in_pitlane
    return g


class TestLapCounter:
    def test_new_lap_detected(self):
        """Lap increment → new_lap event emitted."""
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)

        ev.trigger_internal(None, _gsd(laps=1))
        ev.trigger_internal(None, _gsd(laps=2))

        names = [m.name for m in ap.msgs]
        assert "lap/new_lap" in names

    def test_same_lap_no_event(self):
        """Lap unchanged → no messages emitted."""
        ap = FakeAudioPlayer()
        ev = LapCounter(ap)

        prev = _gsd(laps=3)
        curr = _gsd(laps=3)

        ev.trigger_internal(prev, curr)

        assert len(ap.msgs) == 0

    def test_first_lap_after_pit(self):
        """Exiting pits + lap increment → warmup_lap + new_lap."""
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)

        # Vuelta 1 en pits
        g1 = _gsd(laps=1, in_pitlane=True)
        ev.trigger_internal(None, g1)

        # Vuelta 2 fuera de pits (saliendo + incremento)
        g2 = _gsd(laps=2, in_pitlane=False)
        ev.trigger_internal(g1, g2)

        names = [m.name for m in ap.msgs]
        assert "lap/warmup_lap" in names
        assert "lap/new_lap" in names

    def test_warmup_lap_detected(self):
        """FORMATION phase + prev in pits + lap increment → warmup_lap."""
        ap = FakeAudioPlayer()
        ev = LapCounter(ap=ap)

        g1 = _gsd(laps=1, phase=SessionPhase.FORMATION, in_pitlane=True)
        ev.trigger_internal(None, g1)

        g2 = _gsd(laps=2, phase=SessionPhase.FORMATION, in_pitlane=False)
        ev.trigger_internal(g1, g2)

        names = [m.name for m in ap.msgs]
        assert "lap/warmup_lap" in names
        assert "lap/new_lap" in names

    def test_clear_state_resets(self):
        """clear_state() resets internal state and event_flags."""
        ap = FakeAudioPlayer()
        ev = LapCounter(ap)

        # Build some state
        prev = _gsd(laps=3)
        curr = _gsd(laps=4)
        ev.trigger_internal(prev, curr)
        event_flags.last_lap_was_pit_lap = True

        assert ev._prev_lap == 4
        assert ev._max_lap_seen == 4

        ev.clear_state()

        assert ev._prev_lap == 0
        assert ev._prev_sector == 1
        assert ev._was_pitting is False
        assert ev._played_first_lap_after_pit is False
        assert ev._max_lap_seen == 0
        assert event_flags.last_lap_was_pit_lap is False

    def test_suppress_during_fcy(self):
        """on_manual_formation_lap flag → no messages."""
        ap = FakeAudioPlayer()
        ev = LapCounter(ap)

        event_flags.on_manual_formation_lap = True
        try:
            # Prime counter first
            ev.trigger_internal(None, _gsd(laps=2))

            prev = _gsd(laps=2)
            curr = _gsd(laps=3, phase=SessionPhase.FULL_COURSE_YELLOW)
            ev.trigger_internal(prev, curr)
            assert len(ap.msgs) == 0
        finally:
            event_flags.on_manual_formation_lap = False
