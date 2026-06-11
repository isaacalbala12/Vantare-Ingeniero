# Hito 2 — PlayCommand + voice_loop (in-process)

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **en orden 6→10**. No saltar steps. TDD estricto.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** [`2026-06-07-monolith-voice-beta-rearchitecture.md`](2026-06-07-monolith-voice-beta-rearchitecture.md) Tasks 6–10  
> **Decisiones:** [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md)

**Goal:** Cada `AlertMessage` (spotter/ingeniero) sigue yendo al WebSocket **y** encola un `PlayCommand` en `VoiceQueue`. Un `voice_loop` async consume la cola con `MockAudioPlayer` (sin audio real — Hito 3).

**Architecture:** `VoiceBridge.send` reemplaza `broadcast_sync` como callback de `SpotterService` e `IntelligenceEngine`. WS intacto; cola nueva en el mismo proceso.

**Tech Stack:** Python 3.12, asyncio, FastAPI lifespan, pytest-asyncio.

**Shell:** PowerShell en Windows — usar `;` entre comandos, **no** `&&`.

---

## Preconditions (BLOCKING)

- [ ] CWD: `C:\Users\isaac\Desktop\Vantare-Ingeniero`
- [ ] Hito 1 implementado (`backend/src/race/tick_loop.py` existe, `race_task` en lifespan)
- [ ] Baseline race tests green:

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_telemetry_hub.py tests/test_race_tick_loop.py tests/test_race_loop_no_ws.py tests/test_ws_telemetry_hub.py -v --tb=line
```

Expected: **4 files, all PASSED**

- [ ] Confirm CC fuera de WS (read-only):

```powershell
Select-String -Path src\routers\websocket.py -Pattern "crewchief_loop.on_frame"
```

Expected: **zero matches**

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Create | `backend/src/voice/__init__.py` |
| Create | `backend/src/voice/play_command.py` |
| Create | `backend/src/voice/voice_queue.py` |
| Create | `backend/src/voice/moderator.py` |
| Create | `backend/src/voice/bridge.py` |
| Create | `backend/src/voice/service.py` |
| Create | `backend/src/voice/player_pygame.py` |
| Create | `backend/tests/test_play_command.py` |
| Create | `backend/tests/test_voice_queue.py` |
| Create | `backend/tests/test_voice_moderator.py` |
| Create | `backend/tests/test_voice_bridge.py` |
| Create | `backend/tests/test_voice_loop.py` |
| Modify | `backend/src/main.py` (lifespan + shutdown only) |
| Modify | `backend/src/config.py` (add `VOICE_BACKEND_PLAYBACK`) |

### Files FORBIDDEN

- `backend/src/race/**` (salvo bugfix aprobado por orquestador)
- `backend/src/intelligence/crewchief_events/modules/**`
- `backend/src/intelligence/spotter.py`, `engine.py` (wiring vía callback en main, no editar lógica)
- `frontend/**`
- `shared-telemetry/**`, `shared-strategy/**`
- pygame real, pycaw, edge-tts synthesis (Hito 3)
- `supervisor.ps1`, segundo exe, IPC

---

## Correcciones orquestador (NO copiar bugs del plan maestro)

### 1. `PlayCommand.is_expired`

```python
# ❌ INCORRECTO (plan maestro)
return time.monotonic() if now is None else now > self.expires_at

# ✅ CORRECTO
def is_expired(self, now: float | None = None) -> bool:
    t = time.monotonic() if now is None else now
    return t > self.expires_at
```

### 2. `VoiceBridge.send` — un solo WS emit

`send_alert` **no** debe llamar `_ws_broadcast` otra vez. Solo encola:

```python
def send(self, message: BaseMessage) -> None:
    self._ws_broadcast(message)  # siempre una vez
    if not self.enabled or not isinstance(message, AlertMessage):
        return
    try:
        asyncio.get_running_loop().create_task(self._enqueue_alert(message))
    except RuntimeError:
        pass  # tests sin loop: WS ok, sin cola
```

### 3. `VoiceQueue` tie-breaker

No usar `PlayCommand` en la tupla de prioridad (comparación frágil). Usar secuencia monótona:

```python
await self._queue.put((rank, self._seq, cmd))  # self._seq += 1 each put
```

### 4. Orden lifespan en `main.py`

Crear `VoiceQueue` + `VoiceBridge` **antes** de `SpotterService` e `IntelligenceEngine`.

---

## Task 6: PlayCommand model

**Files:** `backend/src/voice/__init__.py`, `backend/src/voice/play_command.py`, `backend/tests/test_play_command.py`

- [ ] **Step 1: Write failing test**

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
    assert cmd.wav_cache_key == "proximity_left"
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


def test_engineer_voice_response_priority():
    cmd = play_command_from_alert(
        text="Respuesta piloto",
        category="engineer",
        audio_priority="NORMAL",
        event_id="ptt_reply",
        ttl_seconds=10,
        payload={"category": "voice_response"},
    )
    assert cmd.priority == "ENGINEER"
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_play_command.py -v
```

Expected: `ModuleNotFoundError: src.voice.play_command`

- [ ] **Step 3: Implement**

```python
# backend/src/voice/__init__.py
# Voice pipeline (PlayCommand queue + playback). Hito 2: in-process mock player.

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
        t = time.monotonic() if now is None else now
        return t > self.expires_at


def _map_priority(audio_priority: str, payload: dict | None) -> Priority:
    payload = payload or {}
    qc = str(payload.get("queue_class") or "").upper()
    if qc == "IMMEDIATE" or audio_priority.upper() in ("IMPORTANT", "IMMEDIATE", "CRITICAL", "HIGH"):
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

- [ ] **Step 4: Run — expect PASS (3 tests)**

- [ ] **Step 5: Commit** (solo si el usuario lo pide; si no, continuar)

```text
feat(voice): add PlayCommand contract
```

---

## Task 7: VoiceQueue with priority

**Files:** `backend/src/voice/voice_queue.py`, `backend/tests/test_voice_queue.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_voice_queue.py
import asyncio
import time

import pytest

from src.voice.play_command import PlayCommand
from src.voice.voice_queue import VoiceQueue


def _cmd(priority: str, event_id: str, *, expires_in: float = 5.0) -> PlayCommand:
    return PlayCommand(
        id=event_id,
        text=event_id,
        priority=priority,  # type: ignore[arg-type]
        category="spotter" if priority == "IMMEDIATE" else "engineer",
        event_id=event_id,
        ttl_ms=int(expires_in * 1000),
        expires_at=time.monotonic() + expires_in,
    )


@pytest.mark.asyncio
async def test_immediate_dequeued_before_normal():
    q = VoiceQueue(maxsize=16)
    await q.put(_cmd("NORMAL", "a"))
    await q.put(_cmd("IMMEDIATE", "b"))
    first = await q.get()
    assert first.event_id == "b"


@pytest.mark.asyncio
async def test_fifo_within_same_priority():
    q = VoiceQueue(maxsize=16)
    await q.put(_cmd("NORMAL", "first"))
    await q.put(_cmd("NORMAL", "second"))
    assert (await q.get()).event_id == "first"
    assert (await q.get()).event_id == "second"


@pytest.mark.asyncio
async def test_full_queue_drops_oldest():
    q = VoiceQueue(maxsize=2)
    await q.put(_cmd("NORMAL", "old"))
    await q.put(_cmd("NORMAL", "mid"))
    await q.put(_cmd("IMMEDIATE", "new"))
    assert (await q.get()).event_id == "new"
    assert q.qsize() == 1
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_voice_queue.py -v
```

- [ ] **Step 3: Implement**

```python
# backend/src/voice/voice_queue.py
from __future__ import annotations

import asyncio

from src.voice.play_command import PlayCommand

PRIORITY_RANK = {"IMMEDIATE": 0, "NORMAL": 1, "ENGINEER": 2}


class VoiceQueue:
    def __init__(self, maxsize: int = 16) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, PlayCommand]] = asyncio.PriorityQueue(
            maxsize=maxsize
        )
        self._seq = 0

    async def put(self, cmd: PlayCommand) -> None:
        rank = PRIORITY_RANK.get(cmd.priority, 9)
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._seq += 1
        await self._queue.put((rank, self._seq, cmd))

    async def get(self) -> PlayCommand:
        _, _, cmd = await self._queue.get()
        return cmd

    def qsize(self) -> int:
        return self._queue.qsize()
```

- [ ] **Step 4: PASS (3 tests)**

- [ ] **Step 5: Commit** `feat(voice): priority VoiceQueue with drop-oldest`

---

## Task 8: PlaybackModerator

**Files:** `backend/src/voice/moderator.py`, `backend/tests/test_voice_moderator.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_voice_moderator.py
import time

from src.voice.moderator import PlaybackModerator
from src.voice.play_command import PlayCommand


def _cmd(event_id: str, *, expires_at: float | None = None) -> PlayCommand:
    exp = time.monotonic() + 5 if expires_at is None else expires_at
    return PlayCommand(
        id="1",
        text="t",
        priority="NORMAL",
        category="engineer",
        event_id=event_id,
        ttl_ms=5000,
        expires_at=exp,
    )


def test_cooldown_blocks_duplicate_event():
    mod = PlaybackModerator(cooldown_s=2.0)
    now = time.monotonic()
    assert mod.should_play(_cmd("fuel_low"), now=now) is True
    mod.mark_played(_cmd("fuel_low"), now=now)
    assert mod.should_play(_cmd("fuel_low"), now=now + 0.5) is False


def test_expired_command_rejected():
    mod = PlaybackModerator()
    assert mod.should_play(_cmd("x", expires_at=time.monotonic() - 1)) is False


def test_different_event_ids_not_blocked():
    mod = PlaybackModerator(cooldown_s=2.0)
    now = time.monotonic()
    assert mod.should_play(_cmd("a"), now=now) is True
    mod.mark_played(_cmd("a"), now=now)
    assert mod.should_play(_cmd("b"), now=now + 0.1) is True
```

- [ ] **Step 2–3: Implement**

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

- [ ] **Step 4: PASS (3 tests)**

- [ ] **Step 5: Commit** `feat(voice): PlaybackModerator cooldown`

---

## Task 9: VoiceBridge — dual emit WS + queue

**Files:** `backend/src/voice/bridge.py`, `backend/tests/test_voice_bridge.py`, `backend/src/config.py`, `backend/src/main.py`

- [ ] **Step 1: Add config flag**

En `backend/src/config.py`, sección Spotter / Voz:

```python
VOICE_BACKEND_PLAYBACK: bool = True
```

- [ ] **Step 2: Write failing test**

```python
# backend/tests/test_voice_bridge.py
from unittest.mock import MagicMock

import pytest

from src.models.messages import AlertMessage
from src.voice.bridge import VoiceBridge
from src.voice.voice_queue import VoiceQueue


def _alert(**overrides) -> AlertMessage:
    base = dict(
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
    base.update(overrides)
    return AlertMessage(**base)


@pytest.mark.asyncio
async def test_alert_enqueues_play_command_and_broadcasts_once():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)
    await bridge._enqueue_alert(_alert())
    ws_cb.assert_not_called()  # enqueue alone does not WS
    assert q.qsize() == 1


def test_send_broadcasts_ws_and_schedules_enqueue():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)

    async def _run():
        bridge.send(_alert())
        await asyncio.sleep(0.05)
        assert ws_cb.call_count == 1
        assert q.qsize() == 1

    import asyncio
    asyncio.run(_run())


@pytest.mark.asyncio
async def test_disabled_skips_queue_but_still_ws_on_send():
    ws_cb = MagicMock()
    q = VoiceQueue()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=False)

    async def _run():
        bridge.send(_alert())
        await asyncio.sleep(0.02)

    import asyncio
    await _run()
    ws_cb.assert_called_once()
    assert q.qsize() == 0
```

- [ ] **Step 3: Implement bridge**

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
        self._ws_broadcast(message)
        if not self.enabled or not isinstance(message, AlertMessage):
            return
        try:
            import asyncio
            asyncio.get_running_loop().create_task(self._enqueue_alert(message))
        except RuntimeError:
            pass

    async def _enqueue_alert(self, alert: AlertMessage) -> None:
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

- [ ] **Step 4: Wire `main.py` lifespan**

**Insertar ANTES de `# 4. Instanciar SpotterService`:**

```python
    from src.voice.bridge import VoiceBridge
    from src.voice.voice_queue import VoiceQueue

    voice_queue = VoiceQueue()
    app.state.voice_queue = voice_queue
    voice_bridge = VoiceBridge(
        ws_broadcast=broadcast_sync,
        voice_queue=voice_queue,
        enabled=settings.VOICE_BACKEND_PLAYBACK,
    )
    app.state.voice_bridge = voice_bridge
    logger.info("VoiceBridge initialized (backend playback=%s)", settings.VOICE_BACKEND_PLAYBACK)
```

**Cambiar línea SpotterService:**

```python
    spotter_service = SpotterService(broadcast_callback=voice_bridge.send)
```

**Cambiar IntelligenceEngine:**

```python
    intelligence_engine = IntelligenceEngine(
        broadcast_callback=voice_bridge.send,
        ...
    )
```

**NO** tocar `race_tick_loop` wiring.

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_voice_bridge.py tests/test_play_command.py tests/test_voice_queue.py -v
```

- [ ] **Step 6: Commit** `feat(voice): VoiceBridge WS + queue wiring`

---

## Task 10: voice_loop + MockAudioPlayer

**Files:** `backend/src/voice/player_pygame.py`, `backend/src/voice/service.py`, `backend/tests/test_voice_loop.py`, `backend/src/main.py` (shutdown + voice_task)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_voice_loop.py
import asyncio
import time

import pytest

from src.voice.moderator import PlaybackModerator
from src.voice.play_command import PlayCommand
from src.voice.service import voice_loop
from src.voice.player_pygame import MockAudioPlayer
from src.voice.voice_queue import VoiceQueue


@pytest.mark.asyncio
async def test_voice_loop_plays_non_expired_command():
    q = VoiceQueue()
    player = MockAudioPlayer()
    mod = PlaybackModerator(cooldown_s=0.0)
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
    await asyncio.sleep(0.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert player.played == ["test"]


@pytest.mark.asyncio
async def test_voice_loop_skips_expired_command():
    q = VoiceQueue()
    player = MockAudioPlayer()
    mod = PlaybackModerator(cooldown_s=0.0)
    cmd = PlayCommand(
        id="1",
        text="late",
        priority="IMMEDIATE",
        category="spotter",
        event_id="late",
        ttl_ms=100,
        expires_at=time.monotonic() - 1,
    )
    await q.put(cmd)
    task = asyncio.create_task(voice_loop(q, player, mod, tts=None))
    await asyncio.sleep(0.08)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert player.played == []
```

- [ ] **Step 2: Implement**

```python
# backend/src/voice/player_pygame.py
from __future__ import annotations


class MockAudioPlayer:
    def __init__(self) -> None:
        self.played: list[str] = []

    async def play_text(self, text: str, *, priority: str) -> None:
        self.played.append(text)


class PygameAudioPlayer:
    """Real playback — Hito 3."""

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

- [ ] **Step 3: Wire lifespan (después de `race_task`)**

```python
    from src.voice.moderator import PlaybackModerator
    from src.voice.player_pygame import MockAudioPlayer
    from src.voice.service import voice_loop

    voice_player = MockAudioPlayer()
    app.state.voice_player = voice_player
    voice_moderator = PlaybackModerator()
    app.state.voice_moderator = voice_moderator
    voice_task = asyncio.create_task(
        voice_loop(voice_queue, voice_player, voice_moderator, tts=None)
    )
    app.state.voice_task = voice_task
    logger.info("voice_loop spawned (MockAudioPlayer, in-process)")
```

- [ ] **Step 4: Shutdown — cancel voice ANTES de race**

En bloque shutdown de `main.py`, **antes** de cancelar `race_task`:

```python
    voice_task = getattr(app.state, "voice_task", None)
    if voice_task:
        voice_task.cancel()
        with suppress(asyncio.CancelledError):
            await voice_task
```

- [ ] **Step 5: Import check**

```powershell
python -c "from src.main import app; print('import ok')"
```

- [ ] **Step 6: PASS voice_loop tests**

- [ ] **Step 7: Commit** `feat(voice): voice_loop with MockAudioPlayer`

---

## Hito 2 GATE (orquestador verifica al recibir PR)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_play_command.py tests/test_voice_queue.py tests/test_voice_moderator.py tests/test_voice_bridge.py tests/test_voice_loop.py tests/test_race_tick_loop.py -v
```

```powershell
Select-String -Path src\main.py -Pattern "VoiceBridge|voice_task|voice_queue"
```

Expected: matches present.

```powershell
Select-String -Path src\main.py -Pattern "broadcast_callback=broadcast_sync"
```

Expected: **zero matches** en lifespan (Spotter + Engine usan `voice_bridge.send`).

```powershell
python -c "from src.main import app; print('import ok')"
```

| Criterio | Test / check |
|----------|----------------|
| PlayCommand + TTL | test_play_command |
| Priority IMMEDIATE first | test_voice_queue |
| Cooldown + expired skip | test_voice_moderator |
| Alert → queue, WS once | test_voice_bridge |
| voice_loop consumes | test_voice_loop |
| race_loop no regresión | test_race_tick_loop |

---

## Failure modes

| Síntoma | Causa probable | Fix |
|---------|----------------|-----|
| UI sin alerts | `bridge.send` no llama `_ws_broadcast` | Task 9 |
| Alert doble en UI | `_enqueue_alert` también hace WS | corrección §2 |
| Cola vacía siempre | `enabled=False` o no hay loop en test sync | check config / asyncio.run |
| `TypeError` en PriorityQueue | PlayCommand en tupla sin seq | corrección §3 |
| `is_expired` bug | copiado del maestro | corrección §1 |
| Import main falla | voice_task antes de voice_queue | orden lifespan |
| Tests cuelgan | voice_loop sin cancel | patrón cancel en tests |

---

## DoD Hito 2 (implementador marca al terminar)

- [ ] 6 módulos en `backend/src/voice/`
- [ ] `VOICE_BACKEND_PLAYBACK` en config
- [ ] `VoiceBridge` wired; Spotter + Engine usan `voice_bridge.send`
- [ ] `voice_task` spawned y cancelled on shutdown (antes de race_task)
- [ ] GATE pytest green (6 test files arriba)
- [ ] Sin imports pygame/edge-tts reales
- [ ] Reportar al orquestador: diff + output GATE

---

## Entregable para orquestador

Al terminar, el implementador envía:

1. Output completo del comando GATE pytest
2. Output de los dos `Select-String` sobre `main.py`
3. Lista de archivos tocados (debe coincidir con ALLOWED)
4. Cualquier desviación documentada

**Orquestador:** si GATE ✅ → marcar Hito 2 en INDEX y redactar Hito 3 antes de asignar.
