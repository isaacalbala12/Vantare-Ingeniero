# Hito 3 — Audio real + deuda Hito 2 (paridad, cache, cola)

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **11→16 en orden**. No saltar steps. TDD estricto.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** [`2026-06-07-monolith-voice-beta-rearchitecture.md`](2026-06-07-monolith-voice-beta-rearchitecture.md) Tasks 11–13  
> **Decisiones:** [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md)

**Goal:** Reproducir audio spotter/ingeniero en el **backend** (Edge TTS + pygame), con pre-cache de frases spotter (<100 ms objetivo), ducking LMU, y **paridad de prioridad/cache** con el frontend.

**Architecture:** Corregir deuda Hito 2 (Tasks 11–13) → `SpotterPhraseCache` + `TTSManager` → `PygameAudioPlayer` sustituye `MockAudioPlayer` → `DuckingController` en `voice_loop`.

**Tech Stack:** Python 3.12, asyncio, edge-tts, pygame.mixer, pycaw (opcional Windows), pytest-asyncio.

**Shell:** PowerShell — usar `;` entre comandos, **no** `&&`.

**Referencia paridad frontend:** `frontend/src/services/spotterPhrases.ts` (`classifyTtsPriority`, `SPOTTER_PREFETCH_PHRASES`).

---

## Preconditions (BLOCKING)

- [ ] CWD: `C:\Users\isaac\Desktop\Vantare-Ingeniero`
- [ ] **Hito 2 GATE ✅** (16 tests voz + wiring VoiceBridge)
- [ ] Baseline Hito 1+2 green:

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_play_command.py tests/test_voice_queue.py tests/test_voice_moderator.py tests/test_voice_bridge.py tests/test_voice_loop.py tests/test_race_tick_loop.py tests/test_telemetry_hub.py tests/test_race_loop_no_ws.py tests/test_ws_telemetry_hub.py -v --tb=line
```

Expected: **20 passed**

- [ ] Confirm voice wiring (read-only):

```powershell
Select-String -Path src\main.py -Pattern "VoiceBridge|voice_task|MockAudioPlayer"
```

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Create | `backend/src/voice/priority.py` |
| Create | `backend/src/voice/cache_keys.py` |
| Create | `backend/src/voice/spotter_cache.py` |
| Create | `backend/src/voice/tts_manager.py` |
| Create | `backend/src/voice/ducking.py` |
| Create | `backend/tests/test_voice_priority.py` |
| Create | `backend/tests/test_voice_cache_keys.py` |
| Create | `backend/tests/test_voice_queue_eviction.py` |
| Create | `backend/tests/test_spotter_cache.py` |
| Create | `backend/tests/test_tts_manager.py` |
| Create | `backend/tests/test_pygame_player.py` |
| Create | `backend/tests/test_ducking.py` |
| Modify | `backend/src/voice/play_command.py` |
| Modify | `backend/src/voice/voice_queue.py` |
| Modify | `backend/src/voice/bridge.py` |
| Modify | `backend/src/voice/player_pygame.py` |
| Modify | `backend/src/voice/service.py` |
| Modify | `backend/src/main.py` (lifespan: cache warm, pygame, ducking) |
| Modify | `backend/pyproject.toml` (+ `pygame>=2.5.0`; pycaw opcional) |

### Files FORBIDDEN

- `backend/src/race/**` (salvo bugfix aprobado)
- `backend/src/intelligence/crewchief_events/modules/**`
- `backend/src/intelligence/spotter.py`, `engine.py` (lógica; paridad vía `voice/priority.py`)
- `frontend/**` (Hito 4)
- `shared-telemetry/**`, `shared-strategy/**`
- Segundo proceso / supervisor / IPC

---

## Deuda Hito 2 (obligatoria antes de audio real)

| ID | Problema | Task |
|----|----------|------|
| P1 | `proximity` + `audio_priority="2"` → NORMAL en backend, IMMEDIATE en frontend | 11 |
| P1 | `wav_cache_key` solo si `category=="spotter"` (spotter real usa `proximity`, etc.) | 12 |
| P2 | Cola llena: `get_nowait()` elimina el **más prioritario**, no el más viejo | 13 |

---

## Task 11: Paridad `classify_tts_priority` (backend)

**Files:** `backend/src/voice/priority.py`, `backend/tests/test_voice_priority.py`, modificar `play_command.py`

**INVARIANT:** La lógica debe replicar `frontend/src/services/spotterPhrases.ts` → `classifyTtsPriority` (categorías, severity, numérico ≥3, regex de frases). **ENGINEER** sigue viniendo de `payload.category == "voice_response"` o `queue_class` en CC — no de este classifier.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_voice_priority.py
import pytest

from src.voice.priority import classify_tts_priority, map_alert_to_play_priority
from tests.fixtures.audio_trigger_matrix import SPOTTER_AUDIO_ROWS


@pytest.mark.parametrize("row", SPOTTER_AUDIO_ROWS, ids=lambda r: r.id)
def test_spotter_matrix_matches_frontend_expectation(row):
    if row.expect_tts_priority == "N/A":
        return
    got = classify_tts_priority(
        row.sample_message,
        {
            "category": row.category,
            "severity": row.severity,
            "audio_priority": row.audio_priority,
        },
    )
    assert got == row.expect_tts_priority


def test_proximity_audio_priority_2_is_immediate():
    assert classify_tts_priority("Coche a la derecha", {"category": "proximity", "audio_priority": "2"}) == "IMMEDIATE"


def test_gaps_low_priority_is_normal():
    assert classify_tts_priority("Coche a 0.3s delante", {"category": "gaps", "audio_priority": "1"}) == "NORMAL"


def test_map_alert_engineer_voice_response():
    from src.voice.play_command import play_command_from_alert

    cmd = play_command_from_alert(
        text="Respuesta",
        category="engineer",
        audio_priority="NORMAL",
        event_id="ptt",
        ttl_seconds=10,
        payload={"category": "voice_response"},
    )
    assert cmd.priority == "ENGINEER"


def test_map_alert_uses_classifier_not_only_strings():
    from src.voice.play_command import play_command_from_alert

    cmd = play_command_from_alert(
        text="Coche a la izquierda",
        category="proximity",
        audio_priority="2",
        event_id="proximity",
        ttl_seconds=2,
        payload={"category": "proximity"},
    )
    assert cmd.priority == "IMMEDIATE"
```

- [ ] **Step 2: Run — expect FAIL**

```powershell
python -m pytest tests/test_voice_priority.py -v
```

- [ ] **Step 3: Implement `priority.py`**

Portar reglas de `spotterPhrases.ts`:

```python
# backend/src/voice/priority.py
from __future__ import annotations

import re
from typing import Literal

PlayPriority = Literal["IMMEDIATE", "NORMAL"]

IMMEDIATE_CATEGORIES = frozenset({"proximity", "limiter", "fuel", "safety_car"})

IMMEDIATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^coche a la (izquierda|derecha)$", re.I),
    re.compile(r"^despejado (izquierda|derecha)$", re.I),
    re.compile(r"^tres coches de ancho$", re.I),
    re.compile(r"mant[eé]n la l[ií]nea", re.I),
    re.compile(r"viene r[aá]pido por", re.I),
    re.compile(r"hypercar", re.I),
    re.compile(r"doblando por la (izquierda|derecha)$", re.I),
    re.compile(r"adelantando por la (izquierda|derecha)$", re.I),
    re.compile(r"^sigue coche por (izquierda|derecha)", re.I),
    re.compile(r"pit limiter", re.I),
    re.compile(r"combustible cr[ií]tico", re.I),
    re.compile(r"safety car", re.I),
    re.compile(r"fcy activo", re.I),
    re.compile(r"última vuelta", re.I),
]


def normalize_tts_text(text: str) -> str:
    return " ".join(text.strip().split())


def classify_tts_priority(text: str, payload: dict | None = None) -> PlayPriority:
    payload = payload or {}
    category = str(payload.get("category") or "").lower()
    severity = str(payload.get("severity") or "").upper()
    raw = payload.get("audio_priority")
    as_num = int(raw) if isinstance(raw, int) else int(str(raw or "nan") if str(raw or "").isdigit() else -1)

    if category in IMMEDIATE_CATEGORIES:
        return "IMMEDIATE"
    if severity in ("CRITICAL", "HIGH"):
        return "IMMEDIATE"
    if as_num >= 3:
        return "IMMEDIATE"

    normalized = normalize_tts_text(text)
    if any(p.search(normalized) for p in IMMEDIATE_PATTERNS):
        return "IMMEDIATE"
    return "NORMAL"


def map_alert_to_play_priority(
    *,
    text: str,
    audio_priority: str,
    payload: dict | None,
) -> Literal["IMMEDIATE", "NORMAL", "ENGINEER"]:
    payload = payload or {}
    qc = str(payload.get("queue_class") or "").upper()
    if qc == "IMMEDIATE":
        return "IMMEDIATE"
    if str(payload.get("category") or "").lower() == "voice_response":
        return "ENGINEER"
    if audio_priority.upper() in ("IMPORTANT", "IMMEDIATE", "CRITICAL", "HIGH"):
        return "IMMEDIATE"
    if classify_tts_priority(text, payload) == "IMMEDIATE":
        return "IMMEDIATE"
    return "NORMAL"
```

- [ ] **Step 4: Refactor `play_command.py`**

Reemplazar `_map_priority` por import de `map_alert_to_play_priority`:

```python
from src.voice.priority import map_alert_to_play_priority

# inside play_command_from_alert:
priority = map_alert_to_play_priority(text=text, audio_priority=audio_priority, payload=payload)
```

- [ ] **Step 5: Run tests**

```powershell
python -m pytest tests/test_voice_priority.py tests/test_play_command.py -v
```

Expected: all PASSED (incl. `test_map_alert_uses_classifier_not_only_strings`)

- [ ] **Step 6: Commit** `fix(voice): parity classify_tts_priority with frontend`

---

## Task 12: `wav_cache_key` resoluble para spotter real

**Files:** `backend/src/voice/cache_keys.py`, `backend/tests/test_voice_cache_keys.py`, modificar `play_command.py` + `bridge.py`

**Problema:** Spotter nativo no pone `event_id` en payload; `category` es `proximity`, no `spotter`. CC sí pone `event_id` en payload.

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_voice_cache_keys.py
from src.voice.cache_keys import resolve_wav_cache_key, build_text_to_cache_key_map
from src.voice.play_command import play_command_from_alert


def test_cc_event_id_from_payload():
    key = resolve_wav_cache_key(
        text="Hold line",
        category="spotter",
        event_id="hold_line_left",
        payload={"event_id": "hold_line_left"},
    )
    assert key == "hold_line_left"


def test_proximity_resolves_by_normalized_text():
    mapping = build_text_to_cache_key_map()
    key = resolve_wav_cache_key(
        text="Coche a la izquierda",
        category="proximity",
        event_id="proximity",
        payload={"category": "proximity", "service": "spotter"},
        text_to_key=mapping,
    )
    assert key is not None
    assert "left" in key or key.startswith("proximity")


def test_play_command_sets_cache_key_for_proximity():
    cmd = play_command_from_alert(
        text="Coche a la derecha",
        category="proximity",
        audio_priority="2",
        event_id="proximity",
        ttl_seconds=2,
        payload={"category": "proximity", "service": "spotter"},
    )
    assert cmd.wav_cache_key is not None


def test_unknown_dynamic_text_no_cache_key():
    key = resolve_wav_cache_key(
        text="Coche a 0.3s delante",
        category="gaps",
        event_id="gaps",
        payload={},
        text_to_key={},
    )
    assert key is None
```

- [ ] **Step 2: Implement `cache_keys.py`**

```python
# backend/src/voice/cache_keys.py
from __future__ import annotations

from src.voice.priority import normalize_tts_text
from src.voice.spotter_cache import default_spotter_phrases  # Task 14; stub first if needed


def build_text_to_cache_key_map(phrases: dict[str, str] | None = None) -> dict[str, str]:
    phrases = phrases or default_spotter_phrases()
    out: dict[str, str] = {}
    for key, text in phrases.items():
        out[normalize_tts_text(text)] = key
    return out


def resolve_wav_cache_key(
    *,
    text: str,
    category: str,
    event_id: str,
    payload: dict | None,
    text_to_key: dict[str, str] | None = None,
) -> str | None:
    payload = payload or {}
    explicit = payload.get("event_id")
    if explicit:
        return str(explicit)
    if event_id and event_id not in (
        "proximity", "fuel", "gaps", "damage", "limiter", "safety_car", "session", "engineer", "spotter"
    ):
        return event_id
    if payload.get("service") == "spotter" or category in (
        "proximity", "limiter", "fuel", "safety_car", "damage", "session", "spotter"
    ):
        mapping = text_to_key or build_text_to_cache_key_map()
        return mapping.get(normalize_tts_text(text))
    return None
```

**Nota implementador:** Si Task 14 aún no existe, crear `default_spotter_phrases()` mínimo en `spotter_cache.py **antes** de Task 12 tests, o inline un dict de 3 frases en `cache_keys` y refactor en Task 14. Preferido: implementar `default_spotter_phrases()` en Task 12 stub → completar en Task 14.

- [ ] **Step 3: Update `play_command_from_alert`**

```python
from src.voice.cache_keys import resolve_wav_cache_key

cache_key = resolve_wav_cache_key(
    text=text,
    category=category,
    event_id=event_id,
    payload=payload,
)
```

- [ ] **Step 4: Update `bridge._enqueue_alert`**

Pasar `event_id` como hoy; `play_command_from_alert` ya resuelve cache internamente. Verificar que `event_id = str(payload.get("event_id") or alert.category)` se mantiene.

- [ ] **Step 5: pytest PASS**

```powershell
python -m pytest tests/test_voice_cache_keys.py tests/test_play_command.py -v
```

- [ ] **Step 6: Commit** `fix(voice): resolve wav_cache_key for native spotter alerts`

---

## Task 13: VoiceQueue eviction — descartar menor prioridad

**Files:** `backend/src/voice/voice_queue.py`, `backend/tests/test_voice_queue_eviction.py`, actualizar `test_voice_queue.py` si hace falta

- [ ] **Step 1: Write failing test (caso P2)**

```python
# backend/tests/test_voice_queue_eviction.py
import time

import pytest

from src.voice.play_command import PlayCommand
from src.voice.voice_queue import VoiceQueue


def _cmd(priority: str, event_id: str, seq_hint: int = 0) -> PlayCommand:
    base = time.monotonic() + 5 + seq_hint * 0.001
    return PlayCommand(
        id=event_id,
        text=event_id,
        priority=priority,  # type: ignore[arg-type]
        category="spotter" if priority == "IMMEDIATE" else "engineer",
        event_id=event_id,
        ttl_ms=5000,
        expires_at=base,
    )


@pytest.mark.asyncio
async def test_full_queue_drops_normal_not_immediate():
    q = VoiceQueue(maxsize=2)
    await q.put(_cmd("IMMEDIATE", "spot1"))
    await q.put(_cmd("IMMEDIATE", "spot2"))
    await q.put(_cmd("NORMAL", "engineer1"))
    first = await q.get()
    assert first.event_id in ("spot1", "spot2")
    assert first.priority == "IMMEDIATE"
    remaining = []
    while q.qsize():
        remaining.append((await q.get()).event_id)
    assert "engineer1" in remaining
    assert len(remaining) == 1


@pytest.mark.asyncio
async def test_full_queue_drops_oldest_among_same_priority():
    q = VoiceQueue(maxsize=2)
    await q.put(_cmd("NORMAL", "old"))
    await q.put(_cmd("NORMAL", "mid"))
    await q.put(_cmd("IMMEDIATE", "new"))
    assert (await q.get()).event_id == "new"
    assert (await q.get()).event_id == "mid"
    assert q.qsize() == 0
```

- [ ] **Step 2: Implement `_evict_one` en VoiceQueue**

Cuando `full()` antes de `put`:

1. Drenar cola a lista de tuplas `(rank, seq, cmd)`
2. Eliminar el item con **mayor** `(rank, seq)` = menor urgencia / más antiguo en empate
3. Re-encolar el resto
4. Encolar el nuevo cmd

```python
async def _evict_one(self) -> None:
    items: list[tuple[int, int, PlayCommand]] = []
    while not self._queue.empty():
        items.append(self._queue.get_nowait())
    if not items:
        return
    worst = max(range(len(items)), key=lambda i: (items[i][0], items[i][1]))
    del items[worst]
    for item in items:
        await self._queue.put(item)
```

Reemplazar bloque `get_nowait()` simple en `put()` por `await self._evict_one()`.

- [ ] **Step 3: pytest**

```powershell
python -m pytest tests/test_voice_queue.py tests/test_voice_queue_eviction.py -v
```

- [ ] **Step 4: Commit** `fix(voice): evict lowest-priority item when queue full`

---

## Task 14: SpotterPhraseCache (pre-cache startup)

**Files:** `backend/src/voice/spotter_cache.py`, `backend/tests/test_spotter_cache.py`

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_spotter_cache.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.voice.spotter_cache import SpotterPhraseCache, default_spotter_phrases


def test_default_phrases_non_empty():
    phrases = default_spotter_phrases()
    assert len(phrases) >= 10
    assert "proximity_left" in phrases or any("izquierda" in v.lower() for v in phrases.values())


@pytest.mark.asyncio
async def test_cache_stores_bytes_by_key():
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"mp3bytes")
    cache = SpotterPhraseCache(tts)
    phrases = {"proximity_left": "Coche a la izquierda"}
    await cache.warm(phrases)
    assert cache.get("proximity_left") == b"mp3bytes"
    tts.synthesize.assert_awaited_once()


@pytest.mark.asyncio
async def test_warm_skips_empty_text():
    tts = MagicMock()
    tts.synthesize = AsyncMock(return_value=b"x")
    cache = SpotterPhraseCache(tts)
    await cache.warm({"bad": ""})
    assert cache.get("bad") is None
```

- [ ] **Step 2: Implement**

```python
# backend/src/voice/spotter_cache.py
from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("vantare.spotter_cache")

# Alineado con frontend SPOTTER_PREFETCH_PHRASES + spotter_phrases_es.json
PREFETCH_PHRASES: dict[str, str] = {
    "proximity_left": "Coche a la izquierda",
    "proximity_right": "Coche a la derecha",
    "still_there_left": "Sigue coche por izquierda.",
    "still_there_right": "Sigue coche por derecha.",
    "hypercar_right": "Hypercar doblando por la derecha",
    "gt3_left": "GT3 adelantando por la izquierda",
    "clear_left": "Despejado izquierda",
    "clear_right": "Despejado derecha",
    "three_wide": "Tres coches de ancho",
    "hold_line_right": "Mantén la línea, coche por derecha.",
    "closing_fast_left": "¡Viene rápido por izquierda!",
    "limiter_enter": "Pit limiter no activado al entrar en boxes.",
    "limiter_exit": "Pit limiter no desactivado al salir de boxes.",
    "fuel_critical": "¡Combustible crítico! Menos de 1 vuelta restante.",
    "safety_car": "Safety car desplegado / FCY activo en pista.",
    "last_lap": "¡Última vuelta de la carrera!",
    "damage": "Daños detectados en el monoplaza.",
}


def default_spotter_phrases() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "data" / "spotter_phrases_es.json"
    phrases = dict(PREFETCH_PHRASES)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            std = data.get("standard", {})
            if std.get("clear_left"):
                phrases.setdefault("clear_left", std["clear_left"])
            if std.get("clear_right"):
                phrases.setdefault("clear_right", std["clear_right"])
            if std.get("fuel_critical"):
                phrases.setdefault("fuel_critical", std["fuel_critical"])
        except Exception as exc:
            logger.warning("Could not merge spotter_phrases_es.json: %s", exc)
    return {k: v for k, v in phrases.items() if v and v.strip()}


class SpotterPhraseCache:
    def __init__(self, tts) -> None:
        self._tts = tts
        self._bytes: dict[str, bytes] = {}

    async def warm(self, phrases: dict[str, str] | None = None) -> None:
        phrases = phrases or default_spotter_phrases()
        for key, text in phrases.items():
            if not text or not text.strip():
                continue
            self._bytes[key] = await self._tts.synthesize(text.strip())

    def get(self, key: str | None) -> bytes | None:
        if not key:
            return None
        return self._bytes.get(key)

    @property
    def size(self) -> int:
        return len(self._bytes)
```

- [ ] **Step 3: pytest PASS + commit** `feat(voice): SpotterPhraseCache prefetch`

---

## Task 15: TTSManager + PygameAudioPlayer + wiring

**Files:** `tts_manager.py`, `player_pygame.py`, `service.py`, `main.py`, `pyproject.toml`, tests

- [ ] **Step 1: Add dependency**

```toml
# backend/pyproject.toml dependencies
"pygame>=2.5.0",
```

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
pip install pygame
```

- [ ] **Step 2: TTSManager**

```python
# backend/src/voice/tts_manager.py
from __future__ import annotations

import logging

from src.voice.spotter_cache import SpotterPhraseCache

logger = logging.getLogger("vantare.tts_manager")


class TTSManager:
    """Edge TTS + lookup en SpotterPhraseCache."""

    def __init__(self, edge_service, spotter_cache: SpotterPhraseCache | None) -> None:
        self._edge = edge_service
        self._cache = spotter_cache

    async def synthesize(self, text: str, *, cache_key: str | None = None) -> bytes:
        if cache_key and self._cache:
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug("TTS cache hit key=%s", cache_key)
                return cached
        if self._edge is None:
            raise RuntimeError("Edge TTS unavailable")
        audio = await self._edge.synthesize(text)
        if not audio:
            raise RuntimeError("Empty TTS response")
        return audio
```

**Nota:** `EdgeTTSService.synthesize` devuelve `bytes` MP3 directamente (no tupla).

- [ ] **Step 3: PygameAudioPlayer** (ampliar `player_pygame.py`)

```python
import asyncio
import io
import logging

logger = logging.getLogger("vantare.pygame_player")

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore


class PygameAudioPlayer:
    def __init__(self) -> None:
        if pygame is None:
            raise RuntimeError("pygame not installed")
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._lock = asyncio.Lock()

    async def play_bytes(self, data: bytes, *, priority: str) -> None:
        async with self._lock:
            if priority == "IMMEDIATE" and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            buf = io.BytesIO(data)
            pygame.mixer.music.load(buf, namehint="alert.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.02)

    async def play_text(self, text: str, *, priority: str) -> None:
        logger.warning("play_text without bytes — mock fallback: %s", text[:40])
```

Mantener `MockAudioPlayer` para tests unitarios de `voice_loop`.

- [ ] **Step 4: Tests con mocks**

```python
# backend/tests/test_tts_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from src.voice.tts_manager import TTSManager
from src.voice.spotter_cache import SpotterPhraseCache


@pytest.mark.asyncio
async def test_cache_hit_skips_edge():
    edge = MagicMock()
    edge.synthesize = AsyncMock(return_value=b"live")
    cache = SpotterPhraseCache(edge)
    cache._bytes["k"] = b"cached"
    mgr = TTSManager(edge, cache)
    out = await mgr.synthesize("text", cache_key="k")
    assert out == b"cached"
    edge.synthesize.assert_not_called()


# backend/tests/test_pygame_player.py
import pytest
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_play_bytes_stops_immediate_when_busy():
    fake_mixer = MagicMock()
    fake_mixer.music.get_busy.side_effect = [True, True, False]
    with patch("src.voice.player_pygame.pygame") as pg:
        pg.mixer = fake_mixer
        from src.voice.player_pygame import PygameAudioPlayer

        player = PygameAudioPlayer()
        await player.play_bytes(b"data", priority="IMMEDIATE")
    fake_mixer.music.stop.assert_called_once()
```

- [ ] **Step 5: Wire `main.py`**

Reemplazar bloque MockAudioPlayer por:

```python
    spotter_cache = None
    tts_manager = None
    voice_player = None

    edge = getattr(app.state, "edge_tts_service", None)
    if settings.VOICE_BACKEND_PLAYBACK and edge is not None:
        from src.voice.spotter_cache import SpotterPhraseCache
        from src.voice.tts_manager import TTSManager
        from src.voice.player_pygame import PygameAudioPlayer

        spotter_cache = SpotterPhraseCache(edge)
        try:
            await spotter_cache.warm()
            logger.info("SpotterPhraseCache warmed (%d phrases)", spotter_cache.size)
        except Exception as exc:
            logger.warning("Spotter cache warm failed — live TTS only: %s", exc)
        tts_manager = TTSManager(edge, spotter_cache)
        voice_player = PygameAudioPlayer()
    else:
        from src.voice.player_pygame import MockAudioPlayer
        voice_player = MockAudioPlayer()
        logger.warning("Voice playback: MockAudioPlayer (edge=%s, flag=%s)", bool(edge), settings.VOICE_BACKEND_PLAYBACK)

    app.state.spotter_cache = spotter_cache
    app.state.tts_manager = tts_manager
    app.state.voice_player = voice_player

    voice_task = asyncio.create_task(
        voice_loop(voice_queue, voice_player, voice_moderator, tts=tts_manager)
    )
```

**INVARIANT:** `await spotter_cache.warm()` en lifespan **antes** de spawn `race_task` idealmente; mínimo antes de `voice_task`. Si warm es lento (>2s), usar `asyncio.create_task` warm pero log warning — preferido await en beta.

- [ ] **Step 6: pytest (sin red obligatoria en CI)**

```powershell
python -m pytest tests/test_tts_manager.py tests/test_pygame_player.py tests/test_voice_loop.py tests/test_spotter_cache.py -v
```

- [ ] **Step 7: Commit** `feat(voice): TTSManager + PygameAudioPlayer wired`

---

## Task 16: Ducking LMU (pycaw + fallback)

**Files:** `ducking.py`, modificar `service.py`, `pyproject.toml` optional

- [ ] **Step 1: Implement DuckingController**

```python
# backend/src/voice/ducking.py
from __future__ import annotations

import logging

from src.config import settings

logger = logging.getLogger("vantare.ducking")


class DuckingController:
    """Baja volumen LMU durante TTS. pycaw en Windows; noop si no disponible."""

    def __init__(self, level: float | None = None) -> None:
        self._level = level if level is not None else settings.AUDIO_DUCK_LEVEL
        self._pycaw_ok = False
        self._original_volume: float | None = None
        self._session = None
        try:
            from pycaw.pycaw import AudioUtilities  # noqa: F401

            self._pycaw_ok = True
        except Exception:
            logger.info("pycaw unavailable — ducking noop (Hito 4 Tauri fallback)")

    def duck_on(self) -> None:
        if not self._pycaw_ok:
            return
        # Buscar sesión LMU/Le Mans Ultimate y aplicar scalar self._level
        # Implementación mínima: log + TODO si proceso no encontrado
        logger.debug("duck_on level=%.2f", self._level)

    def duck_off(self) -> None:
        if not self._pycaw_ok:
            return
        logger.debug("duck_off")
```

Añadir en `[project.optional-dependencies]`:

```toml
windows = ["pycaw>=20240210"]
```

- [ ] **Step 2: Integrar en `voice_loop`**

```python
async def voice_loop(..., ducking: DuckingController | None = None) -> None:
    ...
            ducking.duck_on() if ducking else None
            try:
                # play bytes / text
            finally:
                if ducking:
                    ducking.duck_off()
```

- [ ] **Step 3: Tests**

```python
# backend/tests/test_ducking.py
from src.voice.ducking import DuckingController


def test_ducking_noop_without_pycaw():
    d = DuckingController(level=0.2)
    d.duck_on()
    d.duck_off()
```

- [ ] **Step 4: Wire main.py**

```python
    from src.voice.ducking import DuckingController
    ducking = DuckingController() if settings.VOICE_BACKEND_PLAYBACK else None
    app.state.ducking = ducking
    voice_task = asyncio.create_task(
        voice_loop(voice_queue, voice_player, voice_moderator, tts=tts_manager, ducking=ducking)
    )
```

- [ ] **Step 5: Commit** `feat(voice): ducking hook in voice_loop`

---

## Hito 3 GATE (orquestador MUST verify)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_voice_priority.py tests/test_voice_cache_keys.py tests/test_voice_queue.py tests/test_voice_queue_eviction.py tests/test_spotter_cache.py tests/test_tts_manager.py tests/test_pygame_player.py tests/test_ducking.py tests/test_play_command.py tests/test_voice_bridge.py tests/test_voice_loop.py tests/test_race_tick_loop.py -v
```

```powershell
Select-String -Path src\main.py -Pattern "SpotterPhraseCache|PygameAudioPlayer|TTSManager"
```

Expected: matches when Edge TTS available; Mock fallback log if not.

```powershell
Select-String -Path src\voice\play_command.py -Pattern "category == \"spotter\""
```

Expected: **zero matches** (cache key ya no usa solo esa condición).

```powershell
python -c "from src.main import app; print('import ok')"
```

| Criterio | Verificación |
|----------|--------------|
| Paridad spotter IMMEDIATE | test_voice_priority + matrix |
| Cache key proximity | test_voice_cache_keys |
| Evict NORMAL not IMMEDIATE | test_voice_queue_eviction |
| Pre-cache | test_spotter_cache |
| TTS cache hit | test_tts_manager |
| pygame play | test_pygame_player (mocked) |
| race_loop intact | test_race_tick_loop |

**Manual (Windows + Edge API key / red):**

1. Arrancar backend con `VOICE_BACKEND_PLAYBACK=true` y Edge TTS OK.
2. Log: `SpotterPhraseCache warmed (N phrases)` con N ≥ 10.
3. `POST` debug alert proximity (si existe `debug_ingest`) o simular vía test manual.
4. Oír MP3 por pygame (altavoz sistema) — opcional en CI.

---

## Failure modes

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Spotter suena tarde | prioridad NORMAL | Task 11 |
| Cache miss siempre | wav_cache_key None | Task 12 |
| Pierde alertas IMMEDIATE | eviction bug | Task 13 |
| pygame silent | mixer no init / MP3 codec | `pygame.mixer.init(frequency=44100)` |
| warm lento en startup | await sync 50 frases | limitar a PREFETCH_PHRASES ~17 |
| doble audio UI+backend | Hito 4 flag frontend | no arreglar aquí |
| pycaw no duck | LMU process name | log + Hito 4 fallback |

---

## DoD Hito 3

- [ ] Tasks 11–16 completas
- [ ] Deuda P1/P2 cerrada con tests
- [ ] `PygameAudioPlayer` en runtime cuando Edge OK
- [ ] `SpotterPhraseCache.warm()` en lifespan
- [ ] GATE pytest green
- [ ] Orquestador marks INDEX gate ✅

---

## Entregable para orquestador

1. Output GATE pytest completo  
2. Select-String results  
3. Lista archivos tocados vs ALLOWED  
4. Nota: ¿warm usó red? ¿pygame probado manualmente?  
5. Desviaciones documentadas  

**Orquestador:** si GATE ✅ → redactar Hito 4 (frontend `voiceBackendPlayback`, silenciar TTS React).

---

## Orquestador review checklist

- [ ] `classify_tts_priority` cubre `SPOTTER_AUDIO_ROWS` con `expect_tts_priority != N/A`
- [ ] No regresión VoiceBridge / race_loop
- [ ] `MockAudioPlayer` sigue en tests unitarios
- [ ] Sin tocar `crewchief_events/modules`
- [ ] pygame import lazy/guarded para dev sin display (CI usa mocks)
