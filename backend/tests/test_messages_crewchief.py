import pytest, time
from src.models.messages import (
    QueuedMessage, MessageFragment, FragmentType,
    DelayedMessageEvent, contents, Pause, Precision, TimeSpanWrapper
)

def test_fragment_text():
    f = MessageFragment.text("hello")
    assert f.type == FragmentType.TEXT
    assert f.text == "hello"

def test_fragment_time():
    f = MessageFragment.time(90.5)
    assert f.type == FragmentType.TIME
    assert f.time_span.seconds == 90.5

def test_fragment_integer():
    f = MessageFragment.integer(42)
    assert f.type == FragmentType.INTEGER
    assert f.integer == 42

def test_fragment_pause():
    f = MessageFragment.pause(500)
    assert f.type == FragmentType.PAUSE
    assert f.pause_ms == 500

def test_queued_message_defaults():
    m = QueuedMessage("test/path")
    assert m.name == "test/path"
    assert m.priority == 5
    assert m.can_play

def test_queued_message_expiry():
    m = QueuedMessage("test", expires=0.1)
    assert not m.is_expired(time.time())
    assert m.is_expired(time.time() + 1.0)

def test_queued_message_delay():
    m = QueuedMessage("test", delay=1.0)
    assert not m.is_due(time.time())
    assert m.is_due(time.time() + 1.5)

def test_prepare_repeat():
    m = QueuedMessage("test/path")
    m.prepare_repeat()
    assert "REPEAT" in m.name
    assert m.priority == 5

def test_contents_mixed():
    r = contents("hello", 42, 90.5)
    assert len(r) == 3
    assert r[0].type == FragmentType.TEXT
    assert r[0].text == "hello"
    assert r[1].type == FragmentType.INTEGER
    assert r[2].type == FragmentType.TIME

def test_contents_none():
    r = contents(None, "test")
    assert r[0] is None
    assert r[1].text == "test"

def test_pause_function():
    p = Pause(300)
    assert p.type == FragmentType.PAUSE
    assert p.pause_ms == 300

def test_delayed_message_event():
    dme = DelayedMessageEvent("method", [1, True], None)
    assert dme.method_name == "method"
    assert dme.method_params == [1, True]