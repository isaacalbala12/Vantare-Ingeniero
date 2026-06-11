"""Tests de aceptación ADR V2-V5 para la re-arquitectura voice beta."""

import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.race.telemetry_hub import TelemetryHub
from src.race.tick_loop import RaceTickDeps, race_tick_loop, run_race_tick_once
from src.voice.moderator import PlaybackModerator
from src.voice.play_command import PlayCommand
from src.voice.player_pygame import MockAudioPlayer
from src.voice.service import voice_loop
from src.voice.voice_queue import VoiceQueue


# ───────────────────── V2 ─────────────────────
@pytest.mark.asyncio
async def test_v2_cc_evaluates_on_race_tick_without_websocket():
    """V2: CC suite corre en race tick (crewchief_loop.on_frame), no depende de WS."""
    hub = TelemetryHub()
    spotter = MagicMock()
    spotter.enabled = True
    cc_loop = MagicMock()
    engine = MagicMock()
    engine.engineer_enabled = True

    strategy = MagicMock()
    strategy.snapshot_frame.return_value = {"lap": 1, "competitors": []}
    advice = MagicMock()
    advice.model_dump.return_value = {"fuel_laps": 2}
    strategy.get_latest_advice.return_value = advice

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=cc_loop,
        intelligence_engine=engine,
        telemetry_hub=hub,
    )

    # 3 race ticks, sin WS
    for _ in range(3):
        await run_race_tick_once(deps)

    assert cc_loop.on_frame.call_count == 3, f"CC debe evaluar en cada race tick, got {cc_loop.on_frame.call_count}"
    engine.evaluate_cycle.assert_not_called()


# ───────────────────── V3 ─────────────────────
class _CrashOncePlayer(MockAudioPlayer):
    def __init__(self) -> None:
        super().__init__()
        self._calls = 0

    async def play_text(self, text: str, *, priority: str) -> None:
        self._calls += 1
        if self._calls == 1:
            raise RuntimeError("simulated voice player crash")
        await super().play_text(text, priority=priority)


@pytest.mark.asyncio
async def test_v3_voice_loop_crash_does_not_stop_race_tick():
    """V3: excepción en voice_loop no detiene race_tick_loop."""
    hub = TelemetryHub()
    strategy = MagicMock()
    lap = {"lap": 0}

    def _next_snapshot():
        lap["lap"] += 1
        return {"lap": lap["lap"], "competitors": []}

    strategy.snapshot_frame.side_effect = _next_snapshot
    strategy.get_latest_advice.return_value = None

    deps_race = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=MagicMock(enabled=False),
        crewchief_loop=MagicMock(),
        intelligence_engine=MagicMock(engineer_enabled=False),
        telemetry_hub=hub,
    )

    vq = VoiceQueue()

    await vq.put(
        PlayCommand(
            id=str(uuid.uuid4()),
            text="crash test",
            priority="NORMAL",
            category="engineer",
            event_id="crash_test",
            ttl_ms=5000,
            expires_at=time.monotonic() + 5.0,
            wav_cache_key="crash_test",
        )
    )

    race_task = asyncio.create_task(race_tick_loop(deps_race))
    voice_task = asyncio.create_task(
        voice_loop(vq, _CrashOncePlayer(), PlaybackModerator(cooldown_s=0.0), tts=None)
    )

    await asyncio.sleep(0.2)
    ticks_after_crash = hub.tick_count
    assert ticks_after_crash >= 1

    await asyncio.sleep(0.15)
    assert hub.tick_count > ticks_after_crash, (
        f"Race tick debe seguir tras crash voice: {hub.tick_count} <= {ticks_after_crash}"
    )

    voice_task.cancel()
    race_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await voice_task
    with pytest.raises(asyncio.CancelledError):
        await race_task


# ───────────────────── V4 ─────────────────────
@pytest.mark.asyncio
async def test_v4_spotter_eval_once_per_tick_regardless_of_ws_clients():
    """V4: run_race_tick_once invoca spotter.evaluate_tick 1x por tick (no por cliente WS)."""
    spotter = MagicMock()
    spotter.enabled = True
    strategy = MagicMock()
    strategy.snapshot_frame.return_value = {"lap": 5, "competitors": []}
    advice = MagicMock()
    advice.model_dump.return_value = None
    strategy.get_latest_advice.return_value = advice

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=MagicMock(),
        intelligence_engine=MagicMock(engineer_enabled=True),
        telemetry_hub=TelemetryHub(),
    )

    for _ in range(3):
        await run_race_tick_once(deps)

    assert spotter.evaluate_tick.call_count == 3, (
        f"Spotter debe evaluar 1x por race tick (3 ticks), got {spotter.evaluate_tick.call_count}"
    )


# ───────────────────── V5 ─────────────────────
@pytest.mark.asyncio
async def test_v5_pilot_question_does_not_block_race_tick():
    """V5: handle_pilot_question async no serializa race_tick >500ms."""
    hub = TelemetryHub()

    # Mock LLM lento
    engine = MagicMock()
    engine.engineer_enabled = True
    engine.handle_pilot_question = AsyncMock()
    engine.handle_pilot_question.__name__ = "handle_pilot_question"

    spotter = MagicMock()
    spotter.enabled = True
    cc_loop = MagicMock()

    strategy = MagicMock()
    strategy.snapshot_frame.return_value = {"lap": 1, "competitors": []}
    advice = MagicMock()
    advice.model_dump.return_value = None
    strategy.get_latest_advice.return_value = advice

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=cc_loop,
        intelligence_engine=engine,
        telemetry_hub=hub,
    )

    # Lanzar PTT como task separada (como hace websocket.py)
    async def slow_ptt():
        # Simular handle_pilot_question lento
        await asyncio.sleep(0.3)
        # Si engine está disponible, llamarlo en una task separada
        if hasattr(engine, "handle_pilot_question"):
            task = asyncio.create_task(engine.handle_pilot_question("test"))
            await task

    slow_task = asyncio.create_task(slow_ptt())

    # Correr race ticks mientras PTT está en progreso
    tick_times: list[float] = []
    for _ in range(5):
        t0 = time.monotonic()
        await run_race_tick_once(deps)
        tick_times.append(time.monotonic() - t0)
        await asyncio.sleep(0.01)

    # PTT no debe bloquear race ticks
    assert hub.tick_count >= 3, f"Race tick debe avanzar durante PTT, ticks={hub.tick_count}"
    inter_tick_ms = [t * 1000 for t in tick_times]
    p95 = sorted(inter_tick_ms)[int(len(inter_tick_ms) * 0.95) - 1]
    assert p95 < 500, f"p95 inter-tick {p95:.0f}ms exceeds 500ms during PTT"

    slow_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await slow_task
