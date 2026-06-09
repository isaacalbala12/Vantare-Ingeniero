# Audit Gemini Backend Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir los hallazgos P0/P1 del informe `informe_auditoria.md` (concurrencia asyncio, persistencia de combustible, TTS Gemini, MQTT y bugs lógicos menores) sin refactorizar deuda de arquitectura (Ruff masivo, `sys.modules`, drift de 20 Hz).

**Architecture:** Mover todo I/O síncrono pesado (ChromaDB embeddings, HTTP Gemini) a `asyncio.to_thread`. Prefetch RAG en el engine antes de `build_prompt` para no bloquear el event loop. Autosave inmediato en `HistoryStore`. Cola MQTT de un solo worker con política “latest frame wins”. Contrato TTS homogéneo: texto vacío → `b""`.

**Tech Stack:** Python 3.12+, FastAPI, asyncio, pytest, pytest-asyncio, ChromaDB, google-genai, paho-mqtt

**Spec de referencia:** `informe_auditoria.md` (raíz del repo), verificado contra código en `backend/src/`.

**Pre-condiciones:**
- Ejecutar desde la raíz del repo: `cd backend`
- Entorno virtual activo con dependencias de `backend/requirements.txt`
- Los tests de ChromaDB son lentos (~60s la primera vez por SentenceTransformer); usar `-m "not slow"` solo si se añade marker; por defecto correr tests nuevos aislados

---

## Mapa de archivos

| Archivo | Responsabilidad del cambio |
|---------|---------------------------|
| `backend/src/routers/websocket.py` | `to_thread` en indexación RAG; cola MQTT; límite `pilot_question` |
| `backend/src/persistence/event_store.py` | Sin cambios de API pública (sigue sync); callers usan `to_thread` |
| `backend/src/intelligence/context_builder.py` | `prefetch_rag_context()` async + param `rag_context` en builders |
| `backend/src/intelligence/engine.py` | Await prefetch RAG antes de construir prompts |
| `backend/src/persistence/history_store.py` | Autosave tras cada `record_lap` |
| `backend/src/services/gemini_tts_service.py` | `_synthesize_sync` + `to_thread`; vacío → `b""`; fix import |
| `backend/src/services/mqtt_service.py` | Cola + worker “latest wins” |
| `backend/src/intelligence/llm_client.py` | Eliminar fallback muerto `reasoning_content` |
| `backend/tests/test_websocket_rag_index.py` | **Create** — no bloqueo del loop |
| `backend/tests/test_history_store.py` | **Create** — autosave |
| `backend/tests/test_gemini_tts_service.py` | **Create** — async + vacío |
| `backend/tests/test_mqtt_service.py` | **Modify** — cola/backpressure |
| `backend/tests/test_context_builder.py` | **Modify** — prefetch RAG |
| `backend/tests/test_websocket_pilot_question.py` | **Create** — límite longitud |

---

### Task 1: ChromaDB indexación sin bloquear el event loop

**Files:**
- Modify: `backend/src/routers/websocket.py:190-203`
- Create: `backend/tests/test_websocket_rag_index.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_websocket_rag_index.py`:

```python
"""Tests de indexación RAG async en websocket sidecar."""

import asyncio
import time

import pytest

from src.routers.websocket import _index_events_async


class _SlowEventStore:
    def __init__(self) -> None:
        self.calls = 0

    def store_events_batch(self, frames) -> None:
        self.calls += 1
        time.sleep(0.15)


@pytest.mark.asyncio
async def test_index_events_async_does_not_block_event_loop():
    """store_events_batch lento no debe congelar otras coroutines."""
    store = _SlowEventStore()
    frame = {"lap_number": 3, "session_type": "race"}
    events = [{"type": "lap_completed", "lap": 3}]

    tick_done = asyncio.Event()

    async def heartbeat():
        await asyncio.sleep(0.05)
        tick_done.set()

    heartbeat_task = asyncio.create_task(heartbeat())
    index_task = asyncio.create_task(_index_events_async(store, frame, events))

    await asyncio.wait_for(tick_done.wait(), timeout=0.12)
    await index_task

    assert store.calls == 1
    heartbeat_task.cancel()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_websocket_rag_index.py::test_index_events_async_does_not_block_event_loop -v`

Expected: **FAIL** — `TimeoutError` o `asyncio.TimeoutError` porque `time.sleep(0.15)` bloquea el loop y `heartbeat` no corre a los 50 ms.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/routers/websocket.py`, replace `_index_events_async` body:

```python
async def _index_events_async(event_store, frame: dict, events: list[dict]) -> None:
    """Indexa eventos en EventStore sin bloquear el event loop."""
    try:
        batches: list[tuple[dict, str, int]] = []
        for evt in events:
            event_type = evt.get("type", "unknown")
            lap = evt.get("lap", 1)
            batches.append((frame, event_type, lap))

        if batches:
            await asyncio.to_thread(event_store.store_events_batch, batches)
            logger.debug("Indexados %d eventos en EventStore", len(batches))
    except Exception as e:
        logger.warning("Error indexing events in EventStore: %s", e)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_websocket_rag_index.py::test_index_events_async_does_not_block_event_loop -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/routers/websocket.py backend/tests/test_websocket_rag_index.py
git commit -m "fix: offload ChromaDB batch indexing to thread pool"
```

---

### Task 2: RAG query en evaluate_cycle sin bloquear

**Files:**
- Modify: `backend/src/intelligence/context_builder.py:175-237,239-287,290-319`
- Modify: `backend/src/intelligence/engine.py:264-270,324-330,453-460`
- Modify: `backend/tests/test_context_builder.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_context_builder.py`:

```python
import asyncio
import time
from unittest.mock import MagicMock

import pytest

from src.intelligence import prompt_templates
from src.intelligence.context_builder import prefetch_rag_context


@pytest.mark.asyncio
async def test_prefetch_rag_context_does_not_block_event_loop():
    store = MagicMock()

    def slow_query(frame, top_k=5):
        time.sleep(0.12)
        return [{"lap": 1, "type": "lap_completed", "text": "lap 1 done"}]

    store.query = slow_query
    snapshot = {"lap_number": 2, "fuel_in_tank": 50.0}

    tick_done = asyncio.Event()

    async def heartbeat():
        await asyncio.sleep(0.05)
        tick_done.set()

    heartbeat_task = asyncio.create_task(heartbeat())
    rag_task = asyncio.create_task(prefetch_rag_context(snapshot, store, top_k=1))

    await asyncio.wait_for(tick_done.wait(), timeout=0.1)
    result = await rag_task

    assert result is not None
    assert "RECORDATORIO HISTÓRICO" in result
    heartbeat_task.cancel()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_context_builder.py::test_prefetch_rag_context_does_not_block_event_loop -v`

Expected: **FAIL** — `ImportError: cannot import name 'prefetch_rag_context'` or timeout.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/intelligence/context_builder.py`, add imports at top:

```python
import asyncio
```

Add function after `_build_rag_context`:

```python
async def prefetch_rag_context(
    snapshot: dict,
    event_store: Optional[Any] = None,
    top_k: int = 5,
) -> Optional[str]:
    """Consulta RAG en un hilo de background para no bloquear asyncio."""
    if event_store is None:
        return None
    return await asyncio.to_thread(_build_rag_context, snapshot, event_store, top_k)
```

Add parameter to `build_prompt` signature (after `strategy_service`):

```python
    rag_context: Optional[str] = None,
```

Replace RAG block inside `build_prompt` (lines ~224-227):

```python
    else:
        resolved_rag = rag_context
        if resolved_rag is None and event_store is not None:
            resolved_rag = _build_rag_context(snapshot, event_store)
        if resolved_rag:
            context_dict["rag_context"] = resolved_rag
```

Add same `rag_context: Optional[str] = None` param to `build_prompt_for_question` and replace its RAG block (~274-277) with the same pattern.

In `backend/src/intelligence/engine.py`, before each `build_prompt` / `build_prompt_for_question` call that passes `event_store`, prefetch:

```python
event_store = self._get_event_store()
rag_context = await self.context_builder.prefetch_rag_context(
    snapshot, event_store
) if event_store else None
```

Then pass `rag_context=rag_context` into `build_prompt(...)` / `build_prompt_for_question(...)`.

Apply at all three call sites (~264, ~324, ~453).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_context_builder.py -v`

Expected: **PASS** (including new test and existing tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/context_builder.py backend/src/intelligence/engine.py backend/tests/test_context_builder.py
git commit -m "fix: prefetch RAG context off event loop in evaluate cycle"
```

---

### Task 3: HistoryStore autosave tras cada vuelta

**Files:**
- Modify: `backend/src/persistence/history_store.py:35-55`
- Create: `backend/tests/test_history_store.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_history_store.py`:

```python
"""Tests unitarios de HistoryStore (persistencia)."""

import json
import os

import pytest

from src.persistence import history_store as hs_mod
from src.persistence.history_store import HistoryStore


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    session_file = data_dir / "consumption_history.json"
    monkeypatch.setattr(hs_mod, "DATA_DIR", str(data_dir))
    monkeypatch.setattr(hs_mod, "SESSION_FILE", str(session_file))
    return HistoryStore(auto_load=False)


def test_record_lap_autosaves_to_disk(isolated_store):
    isolated_store.record_lap(lap=1, fuel_used=3.5, fuel_remaining=96.5, lap_time=120.5)

    assert os.path.exists(hs_mod.SESSION_FILE)
    with open(hs_mod.SESSION_FILE, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["lap"] == 1
    assert data[0]["consumption"] == 3.5


def test_record_lap_replace_updates_disk(isolated_store):
    isolated_store.record_lap(lap=2, fuel_used=3.0, fuel_remaining=90.0, lap_time=119.0)
    isolated_store.record_lap(lap=2, fuel_used=3.2, fuel_remaining=89.8, lap_time=118.5)

    with open(hs_mod.SESSION_FILE, encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["consumption"] == 3.2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_history_store.py -v`

Expected: **FAIL** — `FileNotFoundError` or empty file (no autosave).

- [ ] **Step 3: Write minimal implementation**

In `backend/src/persistence/history_store.py`, replace `record_lap`:

```python
    def record_lap(
        self,
        lap: int,
        fuel_used: float,
        fuel_remaining: float,
        lap_time: float,
    ) -> None:
        """Registra el consumo de una vuelta completada y persiste a disco."""
        record = {
            "lap": lap,
            "consumption": round(fuel_used, 3),
            "fuelRemaining": round(fuel_remaining, 2),
            "lapTime": round(lap_time, 2),
        }
        with self._lock:
            for i, existing in enumerate(self._history):
                if existing["lap"] == lap:
                    self._history[i] = record
                    break
            else:
                self._history.append(record)
        self.save()
```

Note: `save()` re-acquires the lock — safe because `threading.Lock` is not reentrant; release before calling `save()`:

```python
        with self._lock:
            for i, existing in enumerate(self._history):
                if existing["lap"] == lap:
                    self._history[i] = record
                    break
            else:
                self._history.append(record)
        self.save()
```

(`save()` opens its own `with self._lock` block — correct as written above.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_history_store.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/persistence/history_store.py backend/tests/test_history_store.py
git commit -m "fix: autosave fuel history after each completed lap"
```

---

### Task 4: Gemini TTS no bloqueante + contrato TTS homogéneo

**Files:**
- Modify: `backend/src/services/gemini_tts_service.py`
- Create: `backend/tests/test_gemini_tts_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_gemini_tts_service.py`:

```python
"""Tests de GeminiTTSService (async offload + contrato vacío)."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from src.services.gemini_tts_service import GeminiTTSService


@pytest.mark.asyncio
async def test_synthesize_empty_text_returns_empty_bytes():
    svc = GeminiTTSService(api_key="test-key")
    result = await svc.synthesize("   ")
    assert result == b""


@pytest.mark.asyncio
async def test_synthesize_does_not_block_event_loop():
    svc = GeminiTTSService(api_key="test-key")

    def slow_sync(text: str) -> bytes:
        time.sleep(0.12)
        return b"RIFF...."

    tick_done = asyncio.Event()

    async def heartbeat():
        await asyncio.sleep(0.05)
        tick_done.set()

    with patch.object(GeminiTTSService, "_synthesize_sync", side_effect=slow_sync):
        heartbeat_task = asyncio.create_task(heartbeat())
        synth_task = asyncio.create_task(svc.synthesize("Hola piloto"))

        await asyncio.wait_for(tick_done.wait(), timeout=0.1)
        result = await synth_task

    assert result == b"RIFF...."
    heartbeat_task.cancel()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_gemini_tts_service.py -v`

Expected: **FAIL** — `ValueError: Texto vacío` and/or timeout on blocking test.

- [ ] **Step 3: Write minimal implementation**

Replace `backend/src/services/gemini_tts_service.py` with threaded sync path:

```python
import asyncio
import io
import logging
import wave

import google.genai
from google.genai import types

logger = logging.getLogger("vantare.gemini_tts")


class GeminiTTSService:
    """Servicio de síntesis de voz usando Gemini 3.1 Flash TTS (Google AI Studio, cloud)."""

    def __init__(self, api_key: str, voice_name: str = "Kore") -> None:
        self.api_key = api_key
        self.voice_name = voice_name
        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = google.genai.Client(api_key=self.api_key)
        return self._client

    def _synthesize_sync(self, text: str) -> bytes:
        if len(text) > 2000:
            logger.warning("Texto Gemini truncado de %d a 2000 caracteres", len(text))
            text = text[:1997] + "..."

        client = self._get_client()
        voice_config = types.VoiceConfig(
            prebuilt_voice=types.PrebuiltVoiceConfig(voice_name=self.voice_name)
        )
        response = client.models.generate_content(
            model="gemini-3.1-flash-tts-preview",
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(voice_config=voice_config),
            ),
        )

        if not response.candidates or not response.candidates[0].content.parts:
            raise ValueError("Respuesta vacía o sin audio")

        inline_data = response.candidates[0].content.parts[0].inline_data
        if not inline_data or inline_data.mime_type != "audio/pcm":
            mime = inline_data.mime_type if inline_data else "N/A"
            raise ValueError(f"Formato de audio no soportado: {mime}")

        pcm_data = inline_data.data
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(pcm_data)
        return wav_buffer.getvalue()

    async def synthesize(self, text: str) -> bytes:
        if not text or not text.strip():
            return b""
        return await asyncio.to_thread(self._synthesize_sync, text.strip())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_gemini_tts_service.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/gemini_tts_service.py backend/tests/test_gemini_tts_service.py
git commit -m "fix: run Gemini TTS in thread pool and return empty bytes for blank text"
```

---

### Task 5: MQTT backpressure (cola + latest frame wins)

**Files:**
- Modify: `backend/src/services/mqtt_service.py`
- Modify: `backend/src/routers/websocket.py:285-287`
- Modify: `backend/tests/test_mqtt_service.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_mqtt_service.py`:

```python
@pytest.mark.asyncio
async def test_enqueue_keeps_only_latest_frame(monkeypatch):
    monkeypatch.setattr("src.services.mqtt_service.settings.MQTT_ENABLED", True)
    svc = MqttService()
    publish_calls = []

    async def fake_publish(frame):
        publish_calls.append(dict(frame))
        await asyncio.sleep(0.05)

    svc.publish_telemetry = fake_publish  # type: ignore[method-assign]

    svc.enqueue_telemetry({"speed": 1})
    svc.enqueue_telemetry({"speed": 2})
    svc.enqueue_telemetry({"speed": 3})

    await asyncio.sleep(0.2)
    await svc.shutdown_worker()

    assert len(publish_calls) == 1
    assert publish_calls[0]["speed"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_mqtt_service.py::test_enqueue_keeps_only_latest_frame -v`

Expected: **FAIL** — `AttributeError: 'MqttService' object has no attribute 'enqueue_telemetry'`

- [ ] **Step 3: Write minimal implementation**

In `backend/src/services/mqtt_service.py`, extend class:

```python
class MqttService:
    def __init__(self) -> None:
        self._client: Any = None
        self._connected = False
        self._pending_frame: Optional[dict] = None
        self._worker_task: Optional[asyncio.Task] = None
        self._wake = asyncio.Event()

    def enqueue_telemetry(self, frame: dict) -> None:
        """Encola el frame más reciente; descarta frames anteriores no publicados."""
        if not self.enabled:
            return
        self._pending_frame = frame
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        if self._worker_task is None or self._worker_task.done():
            self._wake = asyncio.Event()
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            frame = self._pending_frame
            self._pending_frame = None
            if frame is None:
                continue
            try:
                await self.publish_telemetry(frame)
            except Exception as e:
                logger.warning("MQTT publish failed: %s", e)
            if self._pending_frame is not None:
                self._wake.set()

    async def shutdown_worker(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
```

Update `shutdown()` to call `await self.shutdown_worker()` — make `shutdown` async or add sync cancel. For lifespan in `main.py`, if `shutdown` is sync today, use:

```python
    def shutdown(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            self._worker_task = None
        # existing client disconnect...
```

In `backend/src/routers/websocket.py` line ~287, replace:

```python
asyncio.create_task(mqtt_svc.publish_telemetry(app_state.latest_client_frame))
```

with:

```python
mqtt_svc.enqueue_telemetry(app_state.latest_client_frame)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_mqtt_service.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/mqtt_service.py backend/src/routers/websocket.py backend/tests/test_mqtt_service.py
git commit -m "fix: MQTT telemetry queue with latest-frame-wins backpressure"
```

---

### Task 6: Eliminar código muerto en llm_client streaming

**Files:**
- Modify: `backend/src/intelligence/llm_client.py:293-300`
- Existing tests: `backend/tests/test_llm_client_advanced.py:303-320`

- [ ] **Step 1: Verify existing test covers behavior**

Run: `cd backend && python -m pytest tests/test_llm_client_advanced.py::TestAskStreamingText::test_ask_streaming_text_skips_reasoning -v`

Expected: **PASS** (baseline before change)

- [ ] **Step 2: Remove dead fallback**

In `backend/src/intelligence/llm_client.py`, replace lines 297-300:

```python
                            token = delta.get("content", "")
                            if not token:
                                token = delta.get("reasoning_content", "")
```

with:

```python
                            token = delta.get("content", "")
                            if not token:
                                continue
```

- [ ] **Step 3: Run tests to verify they still pass**

Run: `cd backend && python -m pytest tests/test_llm_client_advanced.py::TestAskStreamingText -v`

Expected: **PASS**

- [ ] **Step 4: Commit**

```bash
git add backend/src/intelligence/llm_client.py
git commit -m "fix: remove unreachable reasoning_content fallback in streaming"
```

---

### Task 7: Límite de longitud en pilot_question

**Files:**
- Modify: `backend/src/routers/websocket.py:343-353`
- Create: `backend/tests/test_websocket_pilot_question.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_websocket_pilot_question.py`:

```python
"""Tests de validación de pilot_question en websocket."""

from src.routers.websocket import _normalize_pilot_question


def test_normalize_pilot_question_truncates_long_input():
    long_q = "a" * 600
    result = _normalize_pilot_question(long_q)
    assert result is not None
    assert len(result) <= 512


def test_normalize_pilot_question_rejects_empty():
    assert _normalize_pilot_question("") is None
    assert _normalize_pilot_question("   ") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_websocket_pilot_question.py -v`

Expected: **FAIL** — `ImportError: cannot import name '_normalize_pilot_question'`

- [ ] **Step 3: Write minimal implementation**

In `backend/src/routers/websocket.py`, add constant and helper near top (after imports):

```python
MAX_PILOT_QUESTION_LEN = 512


def _normalize_pilot_question(question: str) -> str | None:
    cleaned = (question or "").strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_PILOT_QUESTION_LEN:
        logger.warning(
            "pilot_question truncado de %d a %d caracteres",
            len(cleaned),
            MAX_PILOT_QUESTION_LEN,
        )
        return cleaned[:MAX_PILOT_QUESTION_LEN]
    return cleaned
```

Replace pilot_question handler (~343-349):

```python
                elif event == "pilot_question":
                    raw_question = msg.get("data", {}).get("question", "")
                    question = _normalize_pilot_question(raw_question)
                    if question:
                        logger.info("[WS] Pregunta del piloto recibida: %s...", question[:80])
                        engine = getattr(app_state, "intelligence_engine", None)
                        if engine:
                            task = asyncio.create_task(_safe_handle_pilot_question(engine, question))
                            task.add_done_callback(active_subtasks.discard)
                            active_subtasks.add(task)
                        else:
                            logger.warning("[WS] IntelligenceEngine no disponible para procesar pregunta")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_websocket_pilot_question.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/routers/websocket.py backend/tests/test_websocket_pilot_question.py
git commit -m "fix: cap pilot_question length at 512 chars"
```

---

### Task 8: Verificación final de regresión

**Files:** (read-only)

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
cd backend && python -m pytest \
  tests/test_websocket_rag_index.py \
  tests/test_context_builder.py \
  tests/test_history_store.py \
  tests/test_gemini_tts_service.py \
  tests/test_mqtt_service.py \
  tests/test_llm_client_advanced.py::TestAskStreamingText \
  tests/test_websocket_pilot_question.py \
  -v
```

Expected: **All PASS**

- [ ] **Step 2: Run existing event store integration (optional, slow)**

Run: `cd backend && python -m pytest tests/test_event_store.py -v --timeout=120`

Expected: **PASS** (confirms ChromaDB still works after thread offload at call sites)

- [ ] **Step 3: Manual smoke checklist**

1. Arrancar backend: `cd backend && uvicorn src.main:app --port 8008`
2. Conectar sidecar/frontend; completar una vuelta → verificar `data/consumption_history.json` se actualiza sin reiniciar
3. Si `MQTT_ENABLED=true`, verificar un solo publish por ráfaga de frames (logs MQTT)
4. Si `TTS_BACKEND=gemini`, llamar `GET /tts?text=Hola` → audio WAV sin congelar telemetría

- [ ] **Step 4: Commit (only if doc/changelog requested)**

No commit required unless adding CHANGELOG entry per team convention.

---

## Self-Review

| Requisito del informe | Task |
|-----------------------|------|
| ChromaDB bloquea event loop (index) | Task 1 |
| ChromaDB bloquea event loop (query RAG) | Task 2 |
| HistoryStore sin autosave | Task 3 |
| Gemini TTS síncrono | Task 4 |
| MQTT spawn 20Hz sin límite | Task 5 |
| Código muerto reasoning_content | Task 6 |
| pilot_question sin límite | Task 7 |
| sys.modules DI | **Out of scope** (deuda arquitectura) |
| Ruff 1018 warnings | **Out of scope** |
| Sleep drift 20Hz | **Out of scope** |
| except Exception silenciado en event_store cleanup | **Out of scope** (mejora logging, no P0) |

**Placeholder scan:** No TBD/TODO/similar found.

**Type consistency:** `prefetch_rag_context` returns `Optional[str]`; passed as `rag_context=` into both builders; engine uses `await` consistently.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-09-audit-gemini-backend-fixes.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
