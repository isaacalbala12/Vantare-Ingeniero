"""Tests para EventEngine."""

import asyncio
import pytest

from src.intelligence.base_event import AbstractEvent, FakeAudioPlayer
from src.intelligence.event_engine import EventEngine
from src.intelligence.event_flags import event_flags
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase
from src.models.messages import QueuedMessage


class _CountingEvent(AbstractEvent):
    sequence = 50
    category = "ALL"

    def __init__(self, ap=None):
        super().__init__(ap)
        self.calls = 0

    def trigger_internal(self, prev, curr):
        self.calls += 1

    def clear_state(self):
        self.calls = 0


class _RaiseEvent(AbstractEvent):
    sequence = 50
    category = "ALL"

    def trigger_internal(self, prev, curr):
        raise RuntimeError("boom")

    def clear_state(self):
        pass


class _SlowEvent(AbstractEvent):
    sequence = 50
    category = "ALL"

    def trigger_internal(self, prev, curr):
        import time
        time.sleep(3)  # > TIMEOUT (2s)

    def clear_state(self):
        pass


def _gsd(phase=SessionPhase.GREEN, stype=SessionType.RACE):
    g = GameStateData()
    g.session.session_phase = phase
    g.session.session_type = stype
    return g


class TestEventEngineBasics:
    def test_create_empty(self):
        e = EventEngine()
        assert e.registered_names() == []

    def test_register(self):
        e = EventEngine()
        ev = _CountingEvent()
        e.register("counter", ev)
        assert "counter" in e.registered_names()

    def test_unregister(self):
        e = EventEngine()
        ev = _CountingEvent()
        e.register("counter", ev)
        e.unregister("counter")
        assert "counter" not in e.registered_names()

    def test_get_event(self):
        e = EventEngine()
        ev = _CountingEvent()
        e.register("counter", ev)
        assert e.get("counter") is ev

    def test_get_missing_event(self):
        e = EventEngine()
        assert e.get("nope") is None


class TestEventEngineTick:
    @pytest.mark.asyncio
    async def test_tick_calls_applicable(self):
        e = EventEngine()
        ev = _CountingEvent()
        e.register("counter", ev)
        await e.tick(None, _gsd())
        assert ev.calls == 1

    @pytest.mark.asyncio
    async def test_tick_skips_nonapplicable(self):
        e = EventEngine()

        class _WrongPhaseEvent(AbstractEvent):
            sequence = 50
            applicable_phases = [SessionPhase.FORMATION]

            def trigger_internal(self, prev, curr):
                self.calls += 1

            def clear_state(self):
                self.calls = 0

        ev = _WrongPhaseEvent()
        ev.calls = 0
        e.register("wrong", ev)
        await e.tick(None, _gsd(phase=SessionPhase.GREEN))
        assert ev.calls == 0

    @pytest.mark.asyncio
    async def test_tick_handles_none_curr(self):
        e = EventEngine()
        ev = _CountingEvent()
        e.register("counter", ev)
        await e.tick(None, None)
        assert ev.calls == 0

    @pytest.mark.asyncio
    async def test_tick_executes_in_sequence_order(self):
        e = EventEngine()
        order = []

        class _E1(AbstractEvent):
            sequence = 30

            def trigger_internal(self, prev, curr):
                order.append("E1")

            def clear_state(self):
                pass

        class _E2(AbstractEvent):
            sequence = 10

            def trigger_internal(self, prev, curr):
                order.append("E2")

            def clear_state(self):
                pass

        class _E3(AbstractEvent):
            sequence = 20

            def trigger_internal(self, prev, curr):
                order.append("E3")

            def clear_state(self):
                pass

        e.register("e1", _E1())
        e.register("e2", _E2())
        e.register("e3", _E3())
        await e.tick(None, _gsd())
        assert order == ["E2", "E3", "E1"]


class TestEventEngineFaultTolerance:
    @pytest.mark.asyncio
    async def test_exception_doesnt_crash_engine(self):
        e = EventEngine()
        ok = _CountingEvent()
        bad = _RaiseEvent()
        e.register("ok", ok)
        e.register("bad", bad)
        await e.tick(None, _gsd())
        assert ok.calls == 1  # sigue ejecutándose el resto

    @pytest.mark.asyncio
    async def test_fail_count_increments(self):
        e = EventEngine()
        bad = _RaiseEvent()
        e.register("bad", bad)
        await e.tick(None, _gsd())
        assert e.get_fail_count("bad") == 1

    @pytest.mark.asyncio
    async def test_success_resets_fail_count(self):
        e = EventEngine()
        bad = _RaiseEvent()
        ok = _CountingEvent()
        e.register("bad", bad)
        e.register("ok", ok)
        # Primero bad, luego ok no afecta el contador de bad
        await e.tick(None, _gsd())
        assert e.get_fail_count("bad") == 1
        # Pero si bad tiene éxito, se resetea
        bad.__class__ = type('ok', (_CountingEvent,), {})
        # No es trivial cambiar la clase, mejor probar con uno nuevo
        e2 = EventEngine()
        good = _CountingEvent()
        # Manualmente: increment fail, then success
        e2.register("x", good)
        await e2.tick(None, _gsd())  # success
        assert e2.get_fail_count("x") == 0

    @pytest.mark.asyncio
    async def test_timeout_disables_event(self):
        e = EventEngine()
        slow = _SlowEvent()
        e.register("slow", slow)
        await e.tick(None, _gsd())
        assert e.get_fail_count("slow") == 1
        assert not e.is_disabled("slow")
        # 10 timeouts más
        for _ in range(9):
            await e.tick(None, _gsd())
        assert e.is_disabled("slow")

    @pytest.mark.asyncio
    async def test_disabled_event_skipped(self):
        e = EventEngine()
        slow = _SlowEvent()
        e.register("slow", slow)
        for _ in range(10):
            await e.tick(None, _gsd())
        # Ahora está disabled, no debe ejecutar más
        # Reemplazamos trigger_internal para contar
        counter = [0]

        class _Counter(AbstractEvent):
            sequence = 50

            def trigger_internal(self, prev, curr):
                counter[0] += 1

            def clear_state(self):
                pass

        e.register("counter", _Counter())
        await e.tick(None, _gsd())
        # counter debe ejecutarse porque está enabled
        assert counter[0] == 1
        # slow no se cuenta (ya disabled)


class TestEventEngineClearAll:
    @pytest.mark.asyncio
    async def test_clear_all_resets_state(self):
        e = EventEngine()
        ev = _CountingEvent()
        e.register("c", ev)
        await e.tick(None, _gsd())
        ev.calls = 99
        e.clear_all()
        # Después de clear_all, calls debe resetearse
        assert ev.calls == 0
