"""Tests para EventFlags y GlobalBehaviour."""

import pytest
from src.intelligence.event_flags import EventFlags
from src.config.global_behaviour import GlobalBehaviour, global_settings


class TestEventFlagsBasics:
    def test_default_values(self):
        f = EventFlags()
        assert f.is_pitting is False
        assert f.white_flag is False
        assert f.on_formation is False
        assert isinstance(f.exit_close_front, set)
        assert isinstance(f.exit_close_behind, set)

    def test_sets_are_independent(self):
        f1 = EventFlags()
        f2 = EventFlags()
        f1.exit_close_front.add("Alice")
        assert "Alice" not in f2.exit_close_front

    def test_modify_flag(self):
        f = EventFlags()
        f.is_pitting = True
        f.waiting_driver_ok = True
        assert f.is_pitting
        assert f.waiting_driver_ok


class TestEventFlagsReset:
    def test_reset_all_bools(self):
        f = EventFlags()
        f.is_pitting = True
        f.white_flag = True
        f.on_formation = True
        f.reset()
        assert f.is_pitting is False
        assert f.white_flag is False
        assert f.on_formation is False

    def test_reset_clears_sets(self):
        f = EventFlags()
        f.exit_close_front.add("Alice")
        f.exit_close_behind.add("Bob")
        f.reset()
        assert len(f.exit_close_front) == 0
        assert len(f.exit_close_behind) == 0


class TestSingleton:
    def test_singleton_exists(self):
        from src.intelligence.event_flags import event_flags
        assert isinstance(event_flags, EventFlags)


class TestGlobalBehaviour:
    def test_default_messages_is_all(self):
        s = GlobalBehaviour()
        assert "ALL" in s.messages

    def test_all_messages_enables_everything(self):
        s = GlobalBehaviour()
        assert s.message_type_enabled("FUEL")
        assert s.message_type_enabled("TYRES")
        assert s.message_type_enabled("RANDOM_CATEGORY")

    def test_none_messages_disables_everything(self):
        s = GlobalBehaviour()
        s.messages = {"NONE"}
        assert not s.message_type_enabled("FUEL")

    def test_specific_messages(self):
        s = GlobalBehaviour()
        s.messages = {"FUEL", "TYRES"}
        assert s.message_type_enabled("FUEL")
        assert s.message_type_enabled("TYRES")
        assert not s.message_type_enabled("DAMAGE")

    def test_singleton_exists(self):
        from src.config.global_behaviour import global_settings
        assert isinstance(global_settings, GlobalBehaviour)
