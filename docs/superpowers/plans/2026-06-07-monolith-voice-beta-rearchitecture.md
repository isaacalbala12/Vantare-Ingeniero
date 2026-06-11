# Monolith Voice Beta Re-architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a stable beta with one disciplined Python monolith: global `race_loop` @ 20 Hz, backend-owned audio via `voice_loop`, spotter pre-cache, and UI as passive overlay—fixing P0 CC-on-WebSocket and frontend TTS silence.

**Architecture:** Single `backend.exe` (PyInstaller onedir) with three async loops in one process: `race_loop` (telemetry + spotter + CC + validation), `voice_loop` (PlayCommand queue + TTS + pygame playback + ducking), and existing `StrategyService` @ 0.5 Hz. Frontend stops playing spotter/engineer audio when `voiceBackendPlayback=true`. Optional `multiprocessing` audio worker only after pista metrics (not in this plan).

**Tech Stack:** Python 3.12, FastAPI, asyncio, pygame.mixer, edge-tts, pycaw/comtypes (ducking), Tauri 2, React 19, pytest, Vitest.

**Decisions record:** [`docs/architecture/2026-06-07-rearchitecture-decisions-record.md`](../architecture/2026-06-07-rearchitecture-decisions-record.md)

---

## File map (locked)

| File | Responsibility |
|------|----------------|
| `backend/src/race/telemetry_hub.py` | Thread-safe last snapshot + advice for UI broadcast |
| `backend/src/race/tick_loop.py` | Global 20 Hz: snapshot → spotter → CC |
| `backend/src/voice/play_command.py` | Internal voice contract |
| `backend/src/voice/voice_queue.py` | Priority asyncio queue, capacity 16 |
| `backend/src/voice/moderator.py` | Cooldown + dequeue guards (not gap validation) |
| `backend/src/voice/bridge.py` | AlertMessage → PlayCommand + WS still broadcasts |
| `backend/src/voice/spotter_cache.py` | Pre-synthesize spotter phrases at startup |
| `backend/src/voice/tts_manager.py` | Edge TTS + cache lookup |
| `backend/src/voice/player_pygame.py` | pygame.mixer playback + interrupt |
| `backend/src/voice/ducking.py` | pycaw duck + Tauri fallback hook |
| `backend/src/voice/service.py` | `voice_loop` consumer |
| `backend/src/main.py` | Wire loops in lifespan |
| `backend/src/routers/websocket.py` | UI-only telemetry; remove CC from WS loop |
| `scripts/doctor.ps1` | Post-install health |

---

## Hito 1 — Global race_loop (P0 fix)

### Task 1: TelemetryHub

**Files:**
- Create: `backend/src/race/__init__.py`
- Create: `backend/src/race/telemetry_hub.py`
- Test: `backend/tests/test_telemetry_hub.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_telemetry_hub.py
from src.race.telemetry_hub import TelemetryHub


def test_hub_stores_latest_snapshot_and_advice():
    hub = TelemetryHub()
    hub.update(snapshot={"lap": 3, "speed_ms": 50.0}, advice={"fuel_laps": 2})
    snap, adv = hub.get_latest()
    assert snap["lap"] == 3
    assert adv["fuel_laps"] == 2


def test_hub_returns_copy_not_reference():
    hub = TelemetryHub()
    original = {"lap": 1}
    hub.update(snapshot=original, advice=None)
    original["lap"] = 99
    snap, _ = hub.get_latest()
    assert snap["lap"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_telemetry_hub.py -v`  
Expected: FAIL `ModuleNotFoundError: src.race.telemetry_hub`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/race/__init__.py
# (empty)

# backend/src/race/telemetry_hub.py
from __future__ import annotations

import copy
import threading
from typing import Any


class TelemetryHub:
    """Last race snapshot for UI WebSocket broadcast (10 Hz)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] | None = None
        self._advice: dict[str, Any] | None = None
        self.tick_count: int = 0
        self.last_tick_monotonic: float = 0.0

    def update(self, *, snapshot: dict[str, Any], advice: dict[str, Any] | None) -> None:
        with self._lock:
            self._snapshot = copy.deepcopy(snapshot)
            self._advice = copy.deepcopy(advice) if advice else None
            self.tick_count += 1

    def get_latest(self) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        with self._lock:
            snap = copy.deepcopy(self._snapshot) if self._snapshot else None
            adv = copy.deepcopy(self._advice) if self._advice else None
            return snap, adv

    def record_tick_time(self, now: float) -> None:
        with self._lock:
            self.last_tick_monotonic = now
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_telemetry_hub.py -v`  
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/race backend/tests/test_telemetry_hub.py
git commit -m "feat(race): add TelemetryHub for UI snapshot broadcast"
```

---

### Task 2: race_tick_loop core

**Files:**
- Create: `backend/src/race/tick_loop.py`
- Test: `backend/tests/test_race_tick_loop.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_race_tick_loop.py
import asyncio
from unittest.mock import MagicMock

import pytest

from src.race.telemetry_hub import TelemetryHub
from src.race.tick_loop import RaceTickDeps, run_race_tick_once


@pytest.mark.asyncio
async def test_run_race_tick_once_evaluates_spotter_and_cc():
    hub = TelemetryHub()
    spotter = MagicMock()
    spotter.enabled = True
    cc_loop = MagicMock()
    engine = MagicMock()
    engine.engineer_enabled = True

    strategy = MagicMock()
    strategy.snapshot_frame.return_value = {"lap": 5, "competitors": []}
    advice = MagicMock()
    advice.model_dump.return_value = {"fuel_laps": 3}
    strategy.get_latest_advice.return_value = advice

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=cc_loop,
        intelligence_engine=engine,
        telemetry_hub=hub,
    )

    await run_race_tick_once(deps)

    assert spotter.evaluate_tick.called
    cc_loop.on_frame.assert_called_once()
    snap, adv = hub.get_latest()
    assert snap["lap"] == 5
    assert adv["fuel_laps"] == 3


@pytest.mark.asyncio
async def test_run_race_tick_once_skips_when_no_snapshot():
    hub = TelemetryHub()
    spotter = MagicMock()
    spotter.enabled = True
    strategy = MagicMock()
    strategy.snapshot_frame.return_value = None

    deps = RaceTickDeps(
        strategy_service=strategy,
        spotter_service=spotter,
        crewchief_loop=MagicMock(),
        intelligence_engine=MagicMock(),
        telemetry_hub=hub,
    )

    await run_race_tick_once(deps)
    spotter.evaluate_tick.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_race_tick_loop.py -v`  
Expected: FAIL import error

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/race/tick_loop.py
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from src.intelligence.spotter_adapter import frame_to_spotter_tick
from src.race.telemetry_hub import TelemetryHub

logger = logging.getLogger("vantare.race_tick")

TICK_INTERVAL_S = 0.05  # 20 Hz


@dataclass
class RaceTickDeps:
    strategy_service: Any
    spotter_service: Any
    crewchief_loop: Any
    intelligence_engine: Any
    telemetry_hub: TelemetryHub


async def run_race_tick_once(deps: RaceTickDeps) -> None:
    strategy = deps.strategy_service
    spotter = deps.spotter_service
    if strategy is None:
        return

    snapshot = strategy.snapshot_frame()
    if snapshot is None:
        return

    advice_obj = strategy.get_latest_advice()
    advice_dict = advice_obj.model_dump(mode="json") if advice_obj is not None else None

    if spotter is not None and getattr(spotter, "enabled", False):
        spotter_tick = frame_to_spotter_tick(snapshot, advice_dict)
        spotter.evaluate_tick(spotter_tick)

    cc_loop = deps.crewchief_loop
    engine = deps.intelligence_engine
    if cc_loop is not None and engine is not None and getattr(engine, "engineer_enabled", False):
        try:
            cc_loop.on_frame(snapshot, now=time.monotonic(), strategy=advice_dict or {})
        except Exception as exc:
            logger.debug("CrewChief on_frame failed: %s", exc)

    deps.telemetry_hub.update(snapshot=snapshot, advice=advice_dict)
    deps.telemetry_hub.record_tick_time(time.monotonic())


async def race_tick_loop(deps: RaceTickDeps) -> None:
    """Global 20 Hz loop — independent of WebSocket clients."""
    while True:
        loop_started = time.monotonic()
        try:
            await run_race_tick_once(deps)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("race_tick_loop error: %s", exc, exc_info=True)
        elapsed = time.monotonic() - loop_started
        await asyncio.sleep(max(0.0, TICK_INTERVAL_S - elapsed))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_race_tick_loop.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/race/tick_loop.py backend/tests/test_race_tick_loop.py
git commit -m "feat(race): add global race_tick_loop (spotter + CC)"
```

---

### Task 3: Wire race_loop in main.py (replace spotter_eval_loop)

**Files:**
- Modify: `backend/src/main.py:101-110,274-279`
- Modify: `backend/src/routers/websocket.py` (remove `spotter_eval_loop` export usage only)

- [ ] **Step 1: Write failing integration test**

```python
# backend/tests/test_race_loop_lifespan.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_lifespan_starts_race_tick_not_spotter_eval():
    with patch("src.main.TelemetryReader") as Reader, patch(
        "src.main.StrategyService"
    ) as Strat, patch("src.main.poll_api", new_callable=AsyncMock), patch(
        "src.main.HistoryStore"
    ), patch(
        "src.main.ProfileStore"
    ), patch(
        "src.main.TraceStore"
    ), patch(
        "src.main.IntelligenceEngine"
    ) as EngineCls, patch(
        "src.main.SpotterService"
    ), patch(
        "src.main.build_crewchief_suite"
    ), patch(
        "src.main.CrewChiefGameStateLoop"
    ), patch(
        "src.main.asyncio.create_task"
    ) as create_task:
        reader = MagicMock()
        Reader.return_value = reader
        strat = MagicMock()
        strat.wait_until_ready = AsyncMock()
        Strat.return_value = strat

        from src.main import lifespan
        from fastapi import FastAPI

        app = FastAPI()
        ctx = lifespan(app)
        await ctx.__aenter__()

        task_names = [str(c.args[0]) for c in create_task.call_args_list if c.args]
        assert any("race_tick_loop" in n for n in task_names)
        assert not any("spotter_eval_loop" in n for n in task_names)
        await ctx.__aexit__(None, None, None)
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && python -m pytest tests/test_race_loop_lifespan.py -v`  
Expected: FAIL (still uses spotter_eval_loop)

- [ ] **Step 3: Implement wiring in main.py**

In `lifespan`, replace block:

```python
    from src.race.telemetry_hub import TelemetryHub
    from src.race.tick_loop import RaceTickDeps, race_tick_loop

    telemetry_hub = TelemetryHub()
    app.state.telemetry_hub = telemetry_hub

    # ... after intelligence_engine + crewchief_loop created ...

    race_deps = RaceTickDeps(
        strategy_service=strategy_service,
        spotter_service=spotter_service,
        crewchief_loop=app.state.crewchief_loop,
        intelligence_engine=intelligence_engine,
        telemetry_hub=telemetry_hub,
    )
    race_task = asyncio.create_task(race_tick_loop(race_deps))
    app.state.race_task = race_task
    logger.info("race_tick_loop spawned (20Hz global)")
```

Remove:

```python
    from src.routers.websocket import spotter_eval_loop
    spotter_task = asyncio.create_task(spotter_eval_loop(app.state))
```

Shutdown: cancel `race_task` instead of `spotter_task`.

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_race_loop_lifespan.py tests/test_race_tick_loop.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/main.py backend/tests/test_race_loop_lifespan.py
git commit -m "feat(race): wire global race_tick_loop in lifespan"
```

---

### Task 4: Remove CC from telemetry_sender_loop + UI 10 Hz

**Files:**
- Modify: `backend/src/routers/websocket.py:137-187`
- Test: `backend/tests/test_ws_telemetry_hub.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ws_telemetry_hub.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.race.telemetry_hub import TelemetryHub
from src.routers.websocket import router as ws_router


def test_telemetry_sender_reads_hub_not_cc_on_frame():
    app = FastAPI()
    app.include_router(ws_router)
    hub = TelemetryHub()
    hub.update(snapshot={"lap": 7, "speed_ms": 60}, advice=None)
    app.state.telemetry_hub = hub
    app.state.telemetry_reader = MagicMock()
    app.state.strategy_service = None
    app.state.intelligence_engine = MagicMock()
    app.state.crewchief_loop = MagicMock()

    with patch("src.routers.websocket.mp_encode", return_value=b"\x00\x01"):
        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            raw = ws.receive_bytes()
            assert raw == b"\x00\x01"
    app.state.crewchief_loop.on_frame.assert_not_called()
```

- [ ] **Step 2: Run — expect FAIL** (CC still called or hub missing)

- [ ] **Step 3: Rewrite telemetry_sender_loop**

```python
UI_TELEMETRY_INTERVAL_S = 0.1  # 10 Hz

async def telemetry_sender_loop(websocket: WebSocket, app_state) -> None:
    """Broadcast last snapshot from TelemetryHub — no race logic."""
    while True:
        loop_started_at = time.monotonic()
        try:
            hub = getattr(app_state, "telemetry_hub", None)
            state_dict = None
            if hub is not None:
                state_dict, _ = hub.get_latest()
            if state_dict is None:
                strategy_service = getattr(app_state, "strategy_service", None)
                if strategy_service and hasattr(strategy_service, "snapshot_frame"):
                    state_dict = strategy_service.snapshot_frame()
            if state_dict is None:
                await asyncio.sleep(UI_TELEMETRY_INTERVAL_S)
                continue
            raw = mp_encode(state_dict)
            await websocket.send_bytes(raw)
            await asyncio.sleep(compute_loop_sleep(UI_TELEMETRY_INTERVAL_S, loop_started_at))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Error sending telemetry: %s", e)
            break
```

Delete lines 167-177 (`crewchief_loop.on_frame` block).

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_ws_telemetry_hub.py tests/test_race_tick_loop.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/routers/websocket.py backend/tests/test_ws_telemetry_hub.py
git commit -m "fix(ws): decouple UI telemetry from CC evaluation"
```

---

### Task 5: CC runs without WebSocket (acceptance V2)

**Files:**
- Test: `backend/tests/test_race_loop_no_ws.py`

- [ ] **Step 1: Write test**

```python
# backend/tests/test_race_loop_no_ws.py
import asyncio
from unittest.mock import MagicMock

import pytest

from src.race.telemetry_hub import TelemetryHub
from src.race.tick_loop import RaceTickDeps, race_tick_loop


@pytest.mark.asyncio
async def test_race_loop_increments_hub_without_websocket():
    hub = TelemetryHub()
    strategy = MagicMock()
    strategy.snapshot_frame.side_effect = [{"lap": i} for i in range(5)]
    strategy.get_latest_advice.return_value = None
    spotter = MagicMock()
    spotter.enabled = True
    cc = MagicMock()
    engine = MagicMock()
    engine.engineer_enabled = True

    deps = RaceTickDeps(strategy, spotter, cc, engine, hub)
    task = asyncio.create_task(race_tick_loop(deps))
    await asyncio.sleep(0.25)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert hub.tick_count >= 3
    assert cc.on_frame.call_count >= 3
```

- [ ] **Step 2–4: Run until PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_race_loop_no_ws.py
git commit -m "test(race): CC evaluates without WebSocket clients"
```

---

## Hito 2 — PlayCommand + voice_loop (in-process)

### Task 6: PlayCommand model

**Files:**
- Create: `backend/src/voice/__init__.py`
- Create: `backend/src/voice/play_command.py`
- Test: `backend/tests/test_play_command.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_play_command.py
import time
from src.voice.play_command import PlayCommand, play_command_from_alert


def test_play_command_from_alert_spotter_is_immediate():
    cmd = play_command_from_alert(
        text="Coche a la izquierda",
        category="spotter",
        audio_priority="IMPORTANT",
        event_id="proximity_left",
        ttl_seconds=2,
        payload={"queue_class": "IMMEDIATE"},
    )
    assert cmd.priority == "IMMEDIATE"
    assert cmd.category == "spotter"
    assert cmd.expires_at > time.monotonic()


def test_expired_command_detected():
    cmd = PlayCommand(
        id="1",
        text="x",
        priority="NORMAL",
        category="engineer",
        event_id="fuel",
        ttl_ms=100,
        expires_at=time.monotonic() - 1,
    )
    assert cmd.is_expired() is True
```

- [ ] **Step 3: Implementation**

```python
# backend/src/voice/play_command.py
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Literal

Priority = Literal["IMMEDIATE", "NORMAL", "ENGINEER"]


@dataclass(frozen=True)
class PlayCommand:
    id: str
    text: str
    priority: Priority
    category: str
    event_id: str
    ttl_ms: int
    expires_at: float
    wav_cache_key: str | None = None
    validation_key: str | None = None

    def is_expired(self, now: float | None = None) -> bool:
        return time.monotonic() if now is None else now > self.expires_at


def _map_priority(audio_priority: str, payload: dict | None) -> Priority:
    payload = payload or {}
    qc = str(payload.get("queue_class") or "").upper()
    if qc == "IMMEDIATE" or audio_priority.upper() in ("IMPORTANT", "IMMEDIATE"):
        return "IMMEDIATE"
    if str(payload.get("category") or "").lower() == "voice_response":
        return "ENGINEER"
    return "NORMAL"


def play_command_from_alert(
    *,
    text: str,
    category: str,
    audio_priority: str,
    event_id: str,
    ttl_seconds: int,
    payload: dict | None = None,
) -> PlayCommand:
    ttl_ms = max(1000, int(ttl_seconds * 1000))
    priority = _map_priority(audio_priority, payload)
    cache_key = event_id if category == "spotter" else None
    return PlayCommand(
        id=str(uuid.uuid4()),
        text=text.strip(),
        priority=priority,
        category=category,
        event_id=event_id,
        ttl_ms=ttl_ms,
        expires_at=time.monotonic() + ttl_ms / 1000.0,
        wav_cache_key=cache_key,
        validation_key=(payload or {}).get("validation_key"),
    )
```

- [ ] **Step 4–5: pytest PASS + commit**

---

### Task 7: VoiceQueue with priority

**Files:**
- Create: `backend/src/voice/voice_queue.py`
- Test: `backend/tests/test_voice_queue.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_voice_queue.py
import asyncio
import pytest
import time
from src.voice.play_command import PlayCommand
from src.voice.voice_queue import VoiceQueue, PRIORITY_RANK


def _cmd(priority: str, event_id: str) -> PlayCommand:
    return PlayCommand(
        id=event_id,
        text=event_id,
        priority=priority,  # type: ignore
        category="spotter" if priority == "IMMEDIATE" else "engineer",
        event_id=event_id,
        ttl_ms=5000,
        expires_at=time.monotonic() + 5,
    )


@pytest.mark.asyncio
async def test_immediate_dequeued_before_normal():
    q = VoiceQueue(maxsize=16)
    await q.put(_cmd("NORMAL", "a"))
    await q.put(_cmd("IMMEDIATE", "b"))
    first = await q.get()
    assert first.event_id == "b"
```

- [ ] **Step 3: Implementation**

```python
# backend/src/voice/voice_queue.py
from __future__ import annotations

import asyncio
from src.voice.play_command import PlayCommand

PRIORITY_RANK = {"IMMEDIATE": 0, "NORMAL": 1, "ENGINEER": 2}


class VoiceQueue:
    def __init__(self, maxsize: int = 16) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, float, PlayCommand]] = asyncio.PriorityQueue(
            maxsize=maxsize
        )

    async def put(self, cmd: PlayCommand) -> None:
        rank = PRIORITY_RANK.get(cmd.priority, 9)
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        await self._queue.put((rank, cmd.expires_at, cmd))

    async def get(self) -> PlayCommand:
        _, _, cmd = await self._queue.get()
        return cmd
```

- [ ] **Step 4–5: PASS + commit**

---

### Task 8: PlaybackModerator (cooldown, not gap logic)

**Files:**
- Create: `backend/src/voice/moderator.py`
- Test: `backend/tests/test_voice_moderator.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_voice_moderator.py
import time
from src.voice.moderator import PlaybackModerator
from src.voice.play_command import PlayCommand


def _cmd(event_id: str) -> PlayCommand:
    return PlayCommand(
        id="1",
        text="t",
        priority="NORMAL",
        category="engineer",
        event_id=event_id,
        ttl_ms=5000,
        expires_at=time.monotonic() + 5,
    )


def test_cooldown_blocks_duplicate_event():
    mod = PlaybackModerator(cooldown_s=2.0)
    now = time.monotonic()
    assert mod.should_play(_cmd("fuel_low"), now=now) is True
    mod.mark_played(_cmd("fuel_low"), now=now)
    assert mod.should_play(_cmd("fuel_low"), now=now + 0.5) is False
```

- [ ] **Step 3: Implementation**

```python
# backend/src/voice/moderator.py
from __future__ import annotations

import time

from src.voice.play_command import PlayCommand


class PlaybackModerator:
    def __init__(self, cooldown_s: float = 1.5) -> None:
        self._cooldown_s = cooldown_s
        self._last_played: dict[str, float] = {}

    def should_play(self, cmd: PlayCommand, *, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if cmd.is_expired(now):
            return False
        last = self._last_played.get(cmd.event_id)
        if last is not None and (now - last) < self._cooldown_s:
            return False
        return True

    def mark_played(self, cmd: PlayCommand, *, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        self._last_played[cmd.event_id] = now
```

- [ ] **Step 4–5: PASS + commit**

---

### Task 9: VoiceBridge — dual emit WS + queue

**Files:**
- Create: `backend/src/voice/bridge.py`
- Modify: `backend/src/main.py` (install bridge as broadcast wrapper)
- Test: `backend/tests/test_voice_bridge.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_voice_bridge.py
from unittest.mock import MagicMock
from src.models.messages import AlertMessage
from src.voice.bridge import VoiceBridge
from src.voice.voice_queue import VoiceQueue


def test_alert_enqueues_play_command_and_broadcasts():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)
    alert = AlertMessage(
        event="alert",
        alert_id="a1",
        category="spotter",
        message="Coche a la izquierda",
        audio_priority="IMPORTANT",
        severity="INFO",
        ttl=2,
        dismissable=True,
        payload={"event_id": "proximity_left", "queue_class": "IMMEDIATE"},
    )
    import asyncio

    asyncio.get_event_loop().run_until_complete(bridge.send_alert(alert))
    ws_cb.assert_called_once()
    assert q._queue.qsize() == 1  # internal test access
```

- [ ] **Step 3: Implementation**

```python
# backend/src/voice/bridge.py
from __future__ import annotations

import logging
from typing import Callable

from src.models.messages import AlertMessage, BaseMessage
from src.voice.play_command import play_command_from_alert
from src.voice.voice_queue import VoiceQueue

logger = logging.getLogger("vantare.voice_bridge")


class VoiceBridge:
    def __init__(
        self,
        *,
        ws_broadcast: Callable[[BaseMessage], None],
        voice_queue: VoiceQueue,
        enabled: bool = True,
    ) -> None:
        self._ws_broadcast = ws_broadcast
        self._queue = voice_queue
        self.enabled = enabled

    def send(self, message: BaseMessage) -> None:
        if isinstance(message, AlertMessage):
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.send_alert(message))
            except RuntimeError:
                pass
        self._ws_broadcast(message)

    async def send_alert(self, alert: AlertMessage) -> None:
        self._ws_broadcast(alert)
        if not self.enabled:
            return
        payload = alert.payload or {}
        event_id = str(payload.get("event_id") or alert.category)
        cmd = play_command_from_alert(
            text=alert.message,
            category=alert.category,
            audio_priority=alert.audio_priority,
            event_id=event_id,
            ttl_seconds=alert.ttl,
            payload=payload,
        )
        await self._queue.put(cmd)
        logger.debug("Enqueued PlayCommand %s %s", cmd.priority, cmd.event_id)
```

Wire in `main.py`:

```python
from src.voice.voice_queue import VoiceQueue
from src.voice.bridge import VoiceBridge

voice_queue = VoiceQueue()
app.state.voice_queue = voice_queue
bridge = VoiceBridge(ws_broadcast=broadcast_sync, voice_queue=voice_queue, enabled=settings.VOICE_BACKEND_PLAYBACK)
spotter_service = SpotterService(broadcast_callback=bridge.send)
intelligence_engine = IntelligenceEngine(broadcast_callback=bridge.send, ...)
```

Add to `config.py`:

```python
VOICE_BACKEND_PLAYBACK: bool = True
```

- [ ] **Step 4–5: PASS + commit**

---

### Task 10: voice_loop skeleton with mock player

**Files:**
- Create: `backend/src/voice/service.py`
- Create: `backend/src/voice/player_pygame.py` (stub `MockAudioPlayer` first)
- Test: `backend/tests/test_voice_loop.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_voice_loop.py
import asyncio
import time
import pytest
from src.voice.play_command import PlayCommand
from src.voice.voice_queue import VoiceQueue
from src.voice.moderator import PlaybackModerator
from src.voice.service import voice_loop, MockAudioPlayer


@pytest.mark.asyncio
async def test_voice_loop_plays_non_expired_command():
    q = VoiceQueue()
    player = MockAudioPlayer()
    mod = PlaybackModerator()
    cmd = PlayCommand(
        id="1",
        text="test",
        priority="IMMEDIATE",
        category="spotter",
        event_id="t",
        ttl_ms=5000,
        expires_at=time.monotonic() + 5,
    )
    await q.put(cmd)
    task = asyncio.create_task(voice_loop(q, player, mod, tts=None))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert player.played == ["test"]
```

- [ ] **Step 3: Implementation**

```python
# backend/src/voice/player_pygame.py
from __future__ import annotations


class MockAudioPlayer:
    def __init__(self) -> None:
        self.played: list[str] = []

    async def play_text(self, text: str, *, priority: str) -> None:
        self.played.append(text)


class PygameAudioPlayer:
    """Filled in Task 12."""
    async def play_bytes(self, data: bytes, *, priority: str) -> None:
        raise NotImplementedError


# backend/src/voice/service.py
from __future__ import annotations

import asyncio
import logging

from src.voice.moderator import PlaybackModerator
from src.voice.player_pygame import MockAudioPlayer
from src.voice.voice_queue import VoiceQueue

logger = logging.getLogger("vantare.voice_loop")


async def voice_loop(
    queue: VoiceQueue,
    player: MockAudioPlayer,
    moderator: PlaybackModerator,
    tts: object | None,
) -> None:
    while True:
        try:
            cmd = await queue.get()
            if not moderator.should_play(cmd):
                continue
            if tts is not None and hasattr(tts, "synthesize"):
                audio = await tts.synthesize(cmd.text, cache_key=cmd.wav_cache_key)
                if hasattr(player, "play_bytes"):
                    await player.play_bytes(audio, priority=cmd.priority)
                else:
                    await player.play_text(cmd.text, priority=cmd.priority)
            else:
                await player.play_text(cmd.text, priority=cmd.priority)
            moderator.mark_played(cmd)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("voice_loop error: %s", exc, exc_info=True)
```

Wire in `main.py` lifespan after voice_queue created:

```python
from src.voice.service import voice_loop
from src.voice.moderator import PlaybackModerator
from src.voice.player_pygame import MockAudioPlayer  # replace Task 12

player = MockAudioPlayer()
app.state.voice_task = asyncio.create_task(
    voice_loop(voice_queue, player, PlaybackModerator(), tts=None)
)
```

- [ ] **Step 4–5: PASS + commit**

---

## Hito 3 — Real audio (pre-cache + pygame + ducking)

### Task 11: Spotter phrase cache

**Files:**
- Create: `backend/src/voice/spotter_cache.py`
- Test: `backend/tests/test_spotter_cache.py`

- [ ] **Step 1: Test with mocked Edge TTS**

```python
# backend/tests/test_spotter_cache.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.voice.spotter_cache import SpotterPhraseCache, default_spotter_phrases


@pytest.mark.asyncio
async def test_cache_stores_bytes_by_key():
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"wav")
    cache = SpotterPhraseCache(tts)
    phrases = {"left": "Coche a la izquierda"}
    await cache.warm(phrases)
    assert cache.get("left") == b"wav"
```

- [ ] **Step 3: Implementation**

```python
# backend/src/voice/spotter_cache.py
from __future__ import annotations

import json
from pathlib import Path


def default_spotter_phrases() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "data" / "spotter_phrases_es.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    standard = data.get("standard", {})
    mapping = {
        "proximity_left": "Coche a la izquierda.",
        "proximity_right": "Coche a la derecha.",
        "hold_line_left": standard.get("hold_line", "").replace("{side}", "izquierda"),
        "hold_line_right": standard.get("hold_line", "").replace("{side}", "derecha"),
        "clear_left": standard.get("clear_left", "Despejado izquierda"),
        "clear_right": standard.get("clear_right", "Despejado derecha"),
    }
    return {k: v for k, v in mapping.items() if v}


class SpotterPhraseCache:
    def __init__(self, tts) -> None:
        self._tts = tts
        self._bytes: dict[str, bytes] = {}

    async def warm(self, phrases: dict[str, str] | None = None) -> None:
        phrases = phrases or default_spotter_phrases()
        for key, text in phrases.items():
            self._bytes[key] = await self._tts.synthesize(text, cache_key=None)

    def get(self, key: str | None) -> bytes | None:
        if not key:
            return None
        return self._bytes.get(key)
```

- [ ] **Step 4–5: PASS + commit**

---

### Task 12: TTS manager + pygame player

**Files:**
- Create: `backend/src/voice/tts_manager.py`
- Modify: `backend/src/voice/player_pygame.py`
- Modify: `backend/pyproject.toml` (add `pygame>=2.5.0`)

- [ ] **Step 1: Add dependency**

```toml
# backend/pyproject.toml — add to dependencies
"pygame>=2.5.0",
```

Run: `cd backend && pip install pygame`

- [ ] **Step 2: TTS manager**

```python
# backend/src/voice/tts_manager.py
from __future__ import annotations


class TTSManager:
    def __init__(self, edge_service, spotter_cache) -> None:
        self._edge = edge_service
        self._cache = spotter_cache

    async def synthesize(self, text: str, *, cache_key: str | None = None) -> bytes:
        if cache_key:
            cached = self._cache.get(cache_key)
            if cached:
                return cached
        if self._edge is None:
            raise RuntimeError("Edge TTS unavailable")
        audio_bytes, _ = await self._edge.synthesize(text)
        return audio_bytes
```

- [ ] **Step 3: PygameAudioPlayer**

```python
# Append to backend/src/voice/player_pygame.py
import asyncio
import io
import pygame


class PygameAudioPlayer:
    def __init__(self) -> None:
        pygame.mixer.init()
        self._lock = asyncio.Lock()
        self._current_priority = "ENGINEER"

    async def play_bytes(self, data: bytes, *, priority: str) -> None:
        async with self._lock:
            if priority == "IMMEDIATE" and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            buf = io.BytesIO(data)
            pygame.mixer.music.load(buf)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.02)
```

- [ ] **Step 4: Wire in main.py** — replace MockAudioPlayer with PygameAudioPlayer; init SpotterPhraseCache + TTSManager; warm cache in lifespan startup task.

- [ ] **Step 5: Commit**

---

### Task 13: Ducking (pycaw + fallback flag)

**Files:**
- Create: `backend/src/voice/ducking.py`
- Modify: `backend/src/voice/service.py` (call duck on play)
- Modify: `backend/pyproject.toml` optional `pycaw`

- [ ] **Step 1: Implementation**

```python
# backend/src/voice/ducking.py
from __future__ import annotations

import logging

logger = logging.getLogger("vantare.ducking")


class DuckingController:
    def __init__(self, level: float = 0.2) -> None:
        self._level = level
        self._pycaw_ok = False
        try:
            from pycaw.pycaw import AudioUtilities  # noqa: F401
            self._pycaw_ok = True
        except Exception:
            logger.warning("pycaw unavailable — use Tauri ducking fallback")

    def duck_on(self) -> None:
        if not self._pycaw_ok:
            return
        # Implement session volume scalar via pycaw (LMU process search)
        # See frontend audio_duck.rs for parity target level

    def duck_off(self) -> None:
        if not self._pycaw_ok:
            return
```

Call `duck_on()` before `play_bytes`, `duck_off()` after in `voice_loop`.

- [ ] **Step 2–5: Manual test + commit**

---

## Hito 4 — Frontend integration

### Task 14: Config flag voiceBackendPlayback

**Files:**
- Modify: `backend/src/config.py`
- Modify: `backend/src/intelligence/engine.py` (`runtime_config_snapshot`)
- Modify: `frontend/src/store/config.ts`
- Test: extend `backend/tests/test_config_update_ack_ws.py`

- [ ] **Step 1: Backend exposes flag in config_ack**

Add `voiceBackendPlayback: settings.VOICE_BACKEND_PLAYBACK` to `runtime_config_snapshot()`.

- [ ] **Step 2: Frontend schema v4**

```typescript
// frontend/src/store/config.ts — add to AppConfig
voiceBackendPlayback: boolean;

// default
voiceBackendPlayback: true,
```

- [ ] **Step 3: ttsPlaybackGate skips alert TTS when flag true**

```typescript
// frontend/src/services/ttsPlaybackGate.ts
export function evaluateAlertTts(params: {
  voiceBackendPlayback?: boolean;
  // ...existing
}): TtsDecision {
  if (params.voiceBackendPlayback) {
    return { allow: false, reason: "backend_playback" };
  }
  // existing logic
}
```

- [ ] **Step 4: useWebSocket passes flag from config_ack + store**

- [ ] **Step 5: Commit**

---

### Task 15: Health + race tick metrics

**Files:**
- Modify: `backend/src/routers/health.py`

- [ ] **Add to response:**

```python
"race_loop": {
    "tick_count": getattr(getattr(request.app.state, "telemetry_hub", None), "tick_count", 0),
    "last_tick_age_s": time.monotonic() - hub.last_tick_monotonic if hub else None,
},
"voice": {
    "backend_playback": settings.VOICE_BACKEND_PLAYBACK,
    "queue_size": app.state.voice_queue._queue.qsize() if hasattr(app.state, "voice_queue") else 0,
},
```

- [ ] **Commit**

---

## Hito 5 — Slim release + doctor

### Task 16: Disable non-beta features via settings

**Files:**
- Modify: `backend/src/config.py`
- Modify: `backend/src/main.py`
- Modify: `backend/src/intelligence/engine.py`

- [ ] **Add flags:**

```python
BETA_SLIM: bool = True
ENABLE_CHROMA_RAG: bool = False  # gated by not BETA_SLIM
ENABLE_MQTT: bool = False
ENABLE_COMMENTARY_BATCH: bool = False
WHISPER_PRELOAD: str = "off"
```

- [ ] **Skip EventStore init when `BETA_SLIM`**
- [ ] **Set `engine.verbosity.enable_commentary_batch = False` when slim**
- [ ] **Commit**

---

### Task 17: doctor.ps1

**Files:**
- Create: `scripts/doctor.ps1`

- [ ] **Full script:**

```powershell
# scripts/doctor.ps1
$ErrorActionPreference = "Stop"
$log = Join-Path $env:TEMP "vantare-doctor-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
function Log($msg) { "$msg" | Tee-Object -FilePath $log -Append }

$backendRoot = "$PSScriptRoot\..\frontend\src-tauri\binaries\backend"
if (-not (Test-Path $backendRoot)) {
    $backendRoot = "$PSScriptRoot\..\backend\dist\backend"
}

Log "=== Vantare Doctor ==="
Log "Backend root: $backendRoot"

# 1. _internal exists
if (-not (Test-Path "$backendRoot\_internal")) { Log "FAIL: _internal missing"; exit 1 }
Log "OK: _internal"

# 2. Python import pygame
$py = Get-ChildItem "$backendRoot\_internal\python.exe" -ErrorAction SilentlyContinue
if ($py) {
    & $py.FullName -c "import pygame; pygame.mixer.init(); print('OK pygame')" 2>&1 | ForEach-Object { Log $_ }
} else {
    Log "WARN: bundled python.exe not found — dev mode"
}

# 3. Health endpoint
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:8008/health" -TimeoutSec 3
    Log "OK: health status=$($h.status) ticks=$($h.race_loop.tick_count)"
} catch {
    Log "FAIL: /health — $_"
    exit 1
}

Log "Doctor complete: $log"
exit 0
```

- [ ] **Commit**

---

### Task 18: Frontend audio test button

**Files:**
- Modify: `frontend/src/hooks/useWebSocket.ts` or settings panel component
- Add POST or WS event `test_audio` handled in backend `voice_loop`

- [ ] **Backend handler in websocket.py:**

```python
elif event == "test_audio":
    from src.voice.play_command import PlayCommand
    import uuid, time
    cmd = PlayCommand(
        id=str(uuid.uuid4()),
        text="Probando audio. ¿Me escuchás?",
        priority="NORMAL",
        category="engineer",
        event_id="test_audio",
        ttl_ms=10000,
        expires_at=time.monotonic() + 10,
    )
    await app.state.voice_queue.put(cmd)
```

- [ ] **UI button triggers event**
- [ ] **Commit**

---

## Hito 6 — E2E tests + beta gate

### Task 19: Spotter → queue integration test

**Files:**
- Test: `backend/tests/test_spotter_to_voice_queue.py`

- [ ] **Test:** Mock spotter proximity → AlertMessage via VoiceBridge → PlayCommand in queue with IMMEDIATE priority.

- [ ] **Commit**

---

### Task 20: Voice contract frontend tests update

**Files:**
- Modify: `frontend/src/__tests__/voiceContractMatrix.test.ts`

- [ ] **Add case:** when `voiceBackendPlayback=true`, `evaluateAlertTts` returns `backend_playback`.

- [ ] **Run:** `cd frontend && npm test -- voiceContractMatrix`

- [ ] **Commit**

---

### Task 21: Full backend test suite

- [ ] **Run:** `cd backend && python -m pytest -q`
- [ ] **Run:** `cd frontend && npm test -- --run`
- [ ] **Fix failures**
- [ ] **Commit:** `test: green suite after voice rearchitecture`

---

### Task 22: Manual beta checklist (document only)

- [ ] **Execute checklist in** [`docs/architecture/2026-06-07-rearchitecture-decisions-record.md`](../architecture/2026-06-07-rearchitecture-decisions-record.md) **§6 V1–V6**
- [ ] **Log results in** `.omo/evidence/voice-beta-smoke-YYYYMMDD.md`

---

## Hito 7 — Optional Fase 2-R1 (ONLY after metrics)

### Task 23: ProcessPool audio worker (gate document)

**Files:**
- Create: `docs/architecture/fase-2-r1-multiprocessing-gate.md`

- [ ] **Do NOT implement until:** p95 race_loop >40ms OR tick <18Hz documented in smoke evidence.

- [ ] **When triggered:** extract `voice_loop` to `multiprocessing.Process`, use `multiprocessing.Queue`, add `freeze_support()` in `main.py` entrypoint.

---

## Self-review (plan author)

| Spec requirement | Task |
|------------------|------|
| P0 CC-on-WS fix | Tasks 1–5 |
| Backend audio | Tasks 6–13 |
| Pre-cache spotter | Task 11 |
| Frontend no TTS | Task 14 |
| LLM same process | Unchanged engine; Task 16 disables commentary batch |
| Beta slim | Task 16 |
| doctor.ps1 | Task 17 |
| V1–V6 validation | Task 22 |
| Optional multiprocess | Task 23 (gated) |

**Placeholder scan:** No TBD sections.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-07-monolith-voice-beta-rearchitecture.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

**Which approach?**
