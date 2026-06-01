"""Tests para AbstractEvent y FakeAudioPlayer."""

import pytest

from src.intelligence.base_event import AbstractEvent, FakeAudioPlayer
from src.models.enums import SessionType, SessionPhase
from src.models.game_state_data import GameStateData
from src.models.messages import QueuedMessage
from src.intelligence.event_flags import event_flags


class _DummyEvent(AbstractEvent):
    def trigger_internal(self, prev, curr):
        pass

    def clear_state(self):
        pass


def _gsd(t=SessionType.RACE, p=SessionPhase.GREEN):
    g = GameStateData()
    g.session.session_type = t
    g.session.session_phase = p
    return g


class TestAbstractEventBasics:
    def test_creation_with_default_ap(self):
        ev = _DummyEvent()
        assert ev.ap is None

    def test_creation_with_ap(self):
        ap = object()
        ev = _DummyEvent(ap=ap)
        assert ev.ap is ap

    def test_default_applicable_types(self):
        ev = _DummyEvent()
        assert SessionType.RACE in ev.applicable_types
        assert SessionType.PRACTICE in ev.applicable_types
        assert SessionType.QUALIFY in ev.applicable_types

    def test_default_applicable_phases(self):
        ev = _DummyEvent()
        assert SessionPhase.GREEN in ev.applicable_phases

    def test_applicable_race_green(self):
        ev = _DummyEvent()
        assert ev.applicable(SessionType.RACE, SessionPhase.GREEN)

    def test_applicable_qualify_countdown(self):
        ev = _DummyEvent()
        assert ev.applicable(SessionType.QUALIFY, SessionPhase.COUNTDOWN)

    def test_not_applicable_hotlap(self):
        ev = _DummyEvent()
        assert not ev.applicable(SessionType.HOT_LAP, SessionPhase.GREEN)

    def test_not_applicable_garage(self):
        ev = _DummyEvent()
        assert not ev.applicable(SessionType.RACE, SessionPhase.GARAGE)


class TestAbstractEventSuppression:
    def test_should_suppress_formation_lap(self):
        ev = _DummyEvent()
        event_flags.on_manual_formation_lap = True
        try:
            assert ev.should_suppress(_gsd())
        finally:
            event_flags.on_manual_formation_lap = False

    def test_should_not_suppress_normal(self):
        ev = _DummyEvent()
        event_flags.on_manual_formation_lap = False
        assert not ev.should_suppress(_gsd())


class TestAbstractEventPlayback:
    def test_play_no_ap_doesnt_crash(self):
        ev = _DummyEvent()
        ev.play(QueuedMessage("test/path"))

    def test_play_imm_no_ap_doesnt_crash(self):
        ev = _DummyEvent()
        ev.play_imm(QueuedMessage("test/path"))

    def test_play_calls_ap(self):
        captured = []
        ap = type("MockAP", (), {"play": lambda self, m: captured.append(m)})()
        ev = _DummyEvent(ap=ap)
        ev.play(QueuedMessage("test/path"))
        assert len(captured) == 1
        assert captured[0].name == "test/path"

    def test_play_imm_calls_ap(self):
        captured = []
        ap = type("MockAP", (), {"play_imm": lambda self, m: captured.append(m)})()
        ev = _DummyEvent(ap=ap)
        ev.play_imm(QueuedMessage("test/path"))
        assert len(captured) == 1

    def test_ap_play_exception_logged_not_raised(self):
        class _BadAP:
            def play(self, m):
                raise RuntimeError("boom")

        ev = _DummyEvent(ap=_BadAP())
        ev.play(QueuedMessage("test"))  # no debe lanzar


class TestAbstractEventIsValid:
    def test_valid_with_normal_state(self):
        ev = _DummyEvent()
        assert ev.is_valid("foo", _gsd())

    def test_invalid_with_none(self):
        ev = _DummyEvent()
        assert not ev.is_valid("foo", None)

    def test_invalid_with_garage(self):
        ev = _DummyEvent()
        assert not ev.is_valid("foo", _gsd(p=SessionPhase.GARAGE))


class TestStaticHelpers:
    def test_C_packs_strings(self):
        frags = _DummyEvent.C("hello", 42)
        assert len(frags) == 2

    def test_P_returns_pause(self):
        from src.models.messages import FragmentType
        p = _DummyEvent.P(500)
        assert p.type == FragmentType.PAUSE
        assert p.pause_ms == 500


class TestFakeAudioPlayer:
    def test_play_records(self):
        ap = FakeAudioPlayer()
        ap.play(QueuedMessage("a"))
        assert len(ap.msgs) == 1
        assert ap.msgs[0].name == "a"

    def test_play_imm_records(self):
        ap = FakeAudioPlayer()
        ap.play_imm(QueuedMessage("b"))
        assert len(ap.imms) == 1

    def test_clear_resets(self):
        ap = FakeAudioPlayer()
        ap.play(QueuedMessage("a"))
        ap.play_imm(QueuedMessage("b"))
        ap.play_spotter_message("spot")
        ap.clear()
        assert ap.msgs == []
        assert ap.imms == []
        assert ap.spotter_calls == []

    def test_pause_q(self):
        ap = FakeAudioPlayer()
        ap.pause_q(5.0)
        assert ap.paused_for == 5.0
        ap.unpause_q()
        assert ap.paused_for == 0.0
