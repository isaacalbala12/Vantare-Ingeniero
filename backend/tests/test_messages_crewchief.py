"""Tests del CrewChief queue system añadido a messages.py.

Cobertura:
- MessageFragment: text, time, integer, pause, opponent
- QueuedMessage: creación, expiry, delay, prepare_repeat
- TimeSpanWrapper
- contents(): strings, integers, floats, mixto
- Pause() function
- DelayedMessageEvent
- FragmentType constants
- Precision constants
- Compatibilidad: clases Pydantic existentes (BaseMessage, AlertMessage, etc.)
"""
import pytest
import time
from src.models.messages import (
    QueuedMessage, MessageFragment, FragmentType,
    DelayedMessageEvent, contents, Pause, Precision, TimeSpanWrapper,
    BaseMessage, AlertMessage, AdviceEndMessage, LLMPendingMessage,
)


# =========================================================
# MessageFragment
# =========================================================
class TestMessageFragment:
    def test_text_factory(self):
        f = MessageFragment.text("hello")
        assert f.type == FragmentType.TEXT
        assert f.text == "hello"

    def test_time_factory(self):
        f = MessageFragment.time(90.5)
        assert f.type == FragmentType.TIME
        assert f.time_span.seconds == 90.5
        assert f.time_span.precision == Precision.AUTO_LAPTIMES

    def test_time_with_custom_precision(self):
        f = MessageFragment.time(12.3, Precision.TENTHS)
        assert f.time_span.precision == Precision.TENTHS

    def test_integer_factory(self):
        f = MessageFragment.integer(42)
        assert f.type == FragmentType.INTEGER
        assert f.integer == 42

    def test_pause_factory(self):
        f = MessageFragment.pause(500)
        assert f.type == FragmentType.PAUSE
        assert f.pause_ms == 500

    def test_opponent_factory(self):
        f = MessageFragment.opponent("Alice")
        assert f.type == FragmentType.OPPONENT
        assert f.opponent == "Alice"


# =========================================================
# QueuedMessage
# =========================================================
class TestQueuedMessage:
    def test_basic_creation(self):
        m = QueuedMessage("test/path")
        assert m.name == "test/path"
        assert m.priority == 5  # default
        assert m.can_play

    def test_unique_ids(self):
        m1 = QueuedMessage("a")
        m2 = QueuedMessage("b")
        assert m1.id != m2.id

    def test_custom_priority(self):
        m = QueuedMessage("test", priority=20)
        assert m.priority == 20

    def test_expiry_default(self):
        m = QueuedMessage("test")
        # Default expiry=10s
        assert not m.is_expired(time.time())

    def test_expiry_with_short_timeout(self):
        m = QueuedMessage("test", expires=0.1)
        assert not m.is_expired(time.time())
        assert m.is_expired(time.time() + 1.0)

    def test_expiry_zero_never_expires(self):
        """expires=0 significa 'nunca expira'."""
        m = QueuedMessage("test", expires=0)
        assert m.expiry == 0
        assert not m.is_expired(time.time() + 1000)

    def test_delay(self):
        m = QueuedMessage("test", delay=1.0)
        assert not m.is_due(time.time())
        assert m.is_due(time.time() + 1.5)

    def test_age(self):
        m = QueuedMessage("test")
        time.sleep(0.05)
        assert m.age() >= 0.05

    def test_alternate(self):
        m = QueuedMessage("a", alternate=["b", "c"])
        assert m.alternate == ["b", "c"]

    def test_fragments(self):
        m = QueuedMessage("test", fragments=[MessageFragment.text("hi")])
        assert len(m.fragments) == 1

    def test_validation(self):
        m = QueuedMessage("test", validation={"check": lambda x: True})
        assert m.validation == {"check": lambda x: True}


class TestPrepareRepeat:
    def test_repeat_name_prefix(self):
        m = QueuedMessage("test/path")
        m.prepare_repeat()
        assert m.name.startswith("REPEAT_")
        assert "test/path" in m.name

    def test_repeat_clears_state(self):
        m = QueuedMessage("test", priority=20, delay=5.0, expires=10.0)
        m.event = "something"
        m.trigger_fn = lambda: None
        m.prepare_repeat()
        assert m.priority == 5  # Default
        assert m.due == 0  # Inmediato
        assert m.event is None
        assert m.trigger_fn is None
        assert m.delay == 0


# =========================================================
# contents()
# =========================================================
class TestContents:
    def test_string(self):
        r = contents("hello")
        assert len(r) == 1
        assert r[0].type == FragmentType.TEXT
        assert r[0].text == "hello"

    def test_integer(self):
        r = contents(42)
        assert r[0].type == FragmentType.INTEGER
        assert r[0].integer == 42

    def test_float(self):
        r = contents(90.5)
        assert r[0].type == FragmentType.TIME

    def test_time_span_wrapper(self):
        r = contents(TimeSpanWrapper(45.0))
        assert r[0].type == FragmentType.TIME
        assert r[0].time_span.seconds == 45.0

    def test_mixed(self):
        r = contents("hello", 42, 90.5)
        assert len(r) == 3
        assert r[0].type == FragmentType.TEXT
        assert r[1].type == FragmentType.INTEGER
        assert r[2].type == FragmentType.TIME

    def test_none_value(self):
        r = contents(None, "test")
        assert r[0] is None
        assert r[1].text == "test"

    def test_existing_fragment(self):
        f = MessageFragment.text("hi")
        r = contents(f)
        assert r[0] is f


# =========================================================
# Pause()
# =========================================================
class TestPauseFunction:
    def test_pause(self):
        p = Pause(300)
        assert p.type == FragmentType.PAUSE
        assert p.pause_ms == 300


# =========================================================
# DelayedMessageEvent
# =========================================================
class TestDelayedMessageEvent:
    def test_creation(self):
        dme = DelayedMessageEvent("method", [1, True], None)
        assert dme.method_name == "method"
        assert dme.method_params == [1, True]
        assert dme.event_instance is None

    def test_with_event_instance(self):
        class MockEvent:
            pass
        evt = MockEvent()
        dme = DelayedMessageEvent("do_something", [42], evt)
        assert dme.event_instance is evt


# =========================================================
# Compatibilidad con Pydantic existentes
# =========================================================
class TestExistingPydanticModels:
    def test_base_message(self):
        m = BaseMessage(event="test")
        assert m.event == "test"
        assert m.timestamp > 0

    def test_alert_message(self):
        m = AlertMessage(
            alert_id="a1",
            event="alert",
            category="fuel",
            message="low fuel",
            audio_priority="HIGH",
        )
        assert m.alert_id == "a1"
        assert m.category == "fuel"
        assert m.audio_priority == "HIGH"

    def test_llm_pending_message(self):
        m = LLMPendingMessage(
            event="llm_pending",
            advice_id="abc",
            trigger_name="fuel_critical",
            priority="CRITICAL",
        )
        assert m.priority == "CRITICAL"

    def test_advice_end_message(self):
        m = AdviceEndMessage(
            event="advice_end",
            advice_id="abc",
            full_text="refuel now",
        )
        assert m.full_text == "refuel now"
        assert m.actions == []
