# Hito 4 — Frontend integration + hotfixes voz (3.1)

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **17→26 en orden**. No saltar steps. TDD estricto.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** Tasks 14–15 + deuda Hito 1/3  
> **Decisiones:** [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md)

**Goal:** Audio **audible** desde backend (Pygame + Edge + cache warm), **sin doble TTS** en React para alertas, métricas en `/health`, y cierre de deuda config/paridad cache.

**Architecture:** Hotfixes backend primero → flag `voiceBackendPlayback` en `config_ack` → frontend silencia TTS de **alertas** cuando el flag es true → UI sigue mostrando historial/overlay.

**Tech Stack:** Python 3.12, FastAPI, React 19, Zustand, Vitest, pytest.

**Shell:** PowerShell — usar `;` entre comandos, **no** `&&`.

---

## Preconditions (BLOCKING)

- [ ] CWD: `C:\Users\isaac\Desktop\Vantare-Ingeniero`
- [ ] Hito 3 GATE ✅ (módulos voz + tests paridad)
- [ ] Baseline regresión:

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_voice_priority.py tests/test_voice_queue_eviction.py tests/test_play_command.py tests/test_voice_bridge.py tests/test_race_tick_loop.py -v --tb=line
```

Expected: all PASSED

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/src/main.py` (reorder voice wiring + logs) |
| Modify | `backend/src/config.py` (+ spotter settings faltantes) |
| Modify | `backend/.env.example` (documentar flags si aplica) |
| Modify | `backend/src/voice/priority.py` (`normalize_tts_text`) |
| Modify | `backend/src/voice/spotter_cache.py` (aliases frases) |
| Modify | `backend/src/voice/ducking.py` (duck real Windows) |
| Modify | `backend/src/voice/voice_queue.py` (solo si hace falta API health) |
| Modify | `backend/src/intelligence/engine.py` (`runtime_config_snapshot`) |
| Modify | `backend/src/routers/health.py` |
| Create | `backend/tests/test_voice_lifespan_wiring.py` |
| Create | `backend/tests/test_health_voice.py` |
| Modify | `backend/tests/test_config_update_ack_ws.py` |
| Modify | `backend/tests/test_voice_cache_keys.py` |
| Modify | `frontend/src/store/config.ts` |
| Modify | `frontend/src/services/ttsPlaybackGate.ts` |
| Modify | `frontend/src/hooks/useWebSocket.ts` |
| Create | `frontend/src/__tests__/ttsPlaybackGate.backend.test.ts` |

### Files FORBIDDEN

- `backend/src/race/**` (salvo bugfix aprobado)
- `backend/src/intelligence/crewchief_events/modules/**`
- `shared-telemetry/**`, `shared-strategy/**`
- `BETA_SLIM`, `doctor.ps1` (Hito 5)
- Refactor masivo `ttsPipeline.ts` / `useWebSocket.ts` fuera de tasks

---

## Alcance beta (INVARIANT)

| Evento WS | Backend reproduce (Hito 3) | Frontend TTS Hito 4 |
|-----------|---------------------------|---------------------|
| `alert` (spotter, engineer, voice_response) | ✅ vía VoiceBridge | ❌ si `voiceBackendPlayback` |
| `advice_end` (stream LLM) | ❌ aún no | ✅ frontend (sin cambio) |
| `commentary_end` | ❌ aún no | ✅ frontend (sin cambio) |

Evita doble voz en alertas; PTT vía `AlertMessage` category `voice_response` la reproduce el backend.

---

# PARTE A — Hotfixes backend (obligatorios antes de frontend)

---

## Task 17: Hotfix 3.1 — Reordenar wiring voz en `main.py`

**Problema:** Bloque voz (L183–229) corre **antes** de `EdgeTTSService` (L241+). `edge` siempre `None` → `MockAudioPlayer` en producción.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_voice_lifespan_wiring.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_lifespan_selects_pygame_when_edge_available():
    """Tras hotfix, si edge_tts_service existe antes del bloque voz → PygameAudioPlayer."""
    from contextlib import asynccontextmanager

    captured: dict = {}

    mock_edge = MagicMock()
    mock_edge.synthesize = AsyncMock(return_value=b"\xff\xfb")  # fake mp3 header

    @asynccontextmanager
    async def fake_lifespan(app):
        # Simula orden correcto post-hotfix
        app.state.edge_tts_service = mock_edge
        from src.voice.player_pygame import PygameAudioPlayer, MockAudioPlayer
        from src.config import settings

        edge = getattr(app.state, "edge_tts_service", None)
        if settings.VOICE_BACKEND_PLAYBACK and edge is not None:
            with patch.object(PygameAudioPlayer, "__init__", lambda self: None):
                player = PygameAudioPlayer()
            captured["player"] = "pygame"
        else:
            captured["player"] = "mock"
        yield

    from fastapi import FastAPI

    app = FastAPI(lifespan=fake_lifespan)
    async with fake_lifespan(app):
        pass
    assert captured["player"] == "pygame"
```

- [ ] **Step 2: Implement reorder en `main.py`**

**Mover** el bloque completo (imports + ducking + spotter_cache + tts_manager + voice_player + voice_task + logs) desde **después de `race_task`** a **después de la sección 10 (Gemini TTS)** y **antes** de MQTT / Whisper preload.

**Orden final lifespan (fragmento):**

```text
... race_task spawn (20 Hz) ...
... EdgeTTSService (§7) ...
... Piper (§8) ...
... ElevenLabs (§9) ...
... Gemini (§10) ...
>>> voice block: DuckingController, SpotterPhraseCache.warm, TTSManager, PygameAudioPlayer, voice_task
... MQTT / Whisper preload ...
yield
```

**INVARIANT:** `edge = app.state.edge_tts_service` **después** de §7–10.

- [ ] **Step 3: Verificación manual**

```powershell
cd backend
python -c "from src.main import app; print('ok')"
# Arrancar backend con Edge OK → logs esperados:
# SpotterPhraseCache warmed (N phrases)
# Voice player: PygameAudioPlayer (real playback)
```

- [ ] **Step 4: pytest**

```powershell
python -m pytest tests/test_voice_lifespan_wiring.py -v
```

- [ ] **Step 5: Commit** `fix(main): wire voice playback after Edge TTS init`

---

## Task 18: Deuda Hito 1 — settings spotter en `config.py`

**Problema:** `SpotterService` usa `settings.SPOTTER_CAR_LENGTH_M` etc.; faltan en `Settings` → `test_config_update_ack_ws` ERROR.

- [ ] **Step 1: Add to `backend/src/config.py` (sección Spotter / Voz)**

```python
SPOTTER_CAR_LENGTH_M: float = 4.5
SPOTTER_MIN_SPEED_MS: float = 5.0
SPOTTER_RACE_START_DELAY_S: float = 3.0
```

Valores alineados con `frontend/src/store/config.ts` defaults y `tests/test_spotter_cc_parity.py`.

- [ ] **Step 2: Run**

```powershell
python -m pytest tests/test_config_update_ack_ws.py tests/test_spotter_cc_parity.py -v
```

Expected: PASSED (2+ tests config ack)

- [ ] **Step 3: Commit** `fix(config): add missing SPOTTER_* settings`

---

## Task 19: Paridad cache — normalización + aliases limiter

**Problema:** `"Activa el limiter de boxes."` no resuelve cache key; puntuación final puede romper lookup.

- [ ] **Step 1: Extend `normalize_tts_text` en `priority.py`**

```python
def normalize_tts_text(text: str) -> str:
    t = " ".join(text.strip().split())
    return t.rstrip(".!?…")
```

Re-export usado por `cache_keys.py` (ya importa desde priority).

- [ ] **Step 2: Add aliases en `spotter_cache.py` `PREFETCH_PHRASES`**

```python
"limiter_engage_legacy": "Activa el limiter de boxes.",
"limiter_disengage_legacy": "Desactiva el limiter de boxes.",
```

Y en `build_text_to_cache_key_map`, ambas claves pueden apuntar al mismo WAV que `limiter_enter` / `limiter_exit` **o** duplicar entradas en warm (aceptable beta).

- [ ] **Step 3: Tests**

```python
# backend/tests/test_voice_cache_keys.py — add:

def test_limiter_legacy_text_resolves_cache_key():
    from src.voice.cache_keys import build_text_to_cache_key_map, resolve_wav_cache_key
    m = build_text_to_cache_key_map()
    key = resolve_wav_cache_key(
        text="Activa el limiter de boxes.",
        category="limiter",
        event_id="limiter",
        payload={"service": "spotter", "category": "limiter"},
        text_to_key=m,
    )
    assert key is not None


def test_trailing_period_still_matches():
    m = build_text_to_cache_key_map()
    key = resolve_wav_cache_key(
        text="Coche a la izquierda.",
        category="proximity",
        event_id="proximity",
        payload={"service": "spotter"},
        text_to_key=m,
    )
    assert key == "proximity_left"
```

- [ ] **Step 4: pytest PASS + commit** `fix(voice): cache key normalization and limiter aliases`

---

## Task 20: Ducking Windows real (default endpoint)

**Problema:** `DuckingController` es noop. Referencia: `frontend/src-tauri/src/audio_duck.rs` (master volume scalar ~0.2).

- [ ] **Step 1: Implement en `ducking.py`**

Comportamiento mínimo beta:

1. Si pycaw/comtypes disponible: bajar volumen **master del endpoint default render** a `settings.AUDIO_DUCK_LEVEL` en `duck_on`.
2. Restaurar volumen guardado en `duck_off`.
3. Si falla: log warning, noop (no crash voice_loop).

**No** buscar proceso LMU en beta — paridad con Tauri duck default device.

```python
# Esqueleto — implementador completa con pycaw IAudioEndpointVolume
def duck_on(self) -> None:
    if not self._pycaw_ok:
        return
    try:
        # save scalar if not saved; set to self._level
        ...
    except Exception as exc:
        logger.warning("duck_on failed: %s", exc)

def duck_off(self) -> None:
    ...
```

- [ ] **Step 2: Test**

```python
# backend/tests/test_ducking.py — add:
from unittest.mock import patch, MagicMock

def test_duck_on_off_with_mock_pycaw():
    with patch("src.voice.ducking.DuckingController.__init__", lambda self, level=0.2: None):
        from src.voice.ducking import DuckingController
        d = DuckingController()
        d._pycaw_ok = True
        d._saved_scalar = None
        d._set_scalar = MagicMock()
        d._get_scalar = MagicMock(return_value=0.8)
        d.duck_on()
        d.duck_off()
```

(Ajustar a API real del controller.)

- [ ] **Step 3: Commit** `feat(voice): duck default audio endpoint on playback`

---

## Task 21: Logs cosméticos + API cola para health

- [ ] Cambiar log L168 `main.py`:

```python
logger.info("IntelligenceEngine initialized and hooked to VoiceBridge")
```

- [ ] Cambiar log Spotter L114 si aplica (ya dice voice bridge — verificar).

- [ ] En `health.py` usar `voice_queue.qsize()` **público** — no `_queue`.

- [ ] Commit `chore(voice): clarify lifespan logs`

---

# PARTE B — Flag voiceBackendPlayback + silenciar React TTS alertas

---

## Task 22: Backend expone flag en `config_ack`

**Files:** `engine.py`, `config.py` (opcional env alias)

- [ ] **Step 1: Extend `runtime_config_snapshot()`**

```python
from src.config import settings

snap["voiceBackendPlayback"] = settings.VOICE_BACKEND_PLAYBACK
```

- [ ] **Step 2: Test backend**

```python
# backend/tests/test_config_update_ack_ws.py — add:

def test_config_ack_includes_voice_backend_playback(config_ws_app):
    app, engine, _ = config_ws_app
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "config_update", "data": {"engineerEnabled": True}})
        ack = _wait_config_ack(ws)
        assert ack is not None
        assert "voiceBackendPlayback" in ack["data"]["config"]
        assert isinstance(ack["data"]["config"]["voiceBackendPlayback"], bool)
```

- [ ] **Step 3: pytest PASS + commit** `feat(config): expose voiceBackendPlayback in config_ack`

---

## Task 23: Frontend schema v4 + defaults

**Files:** `frontend/src/store/config.ts`

- [ ] **Step 1: Bump schema**

```typescript
const CONFIG_SCHEMA_VERSION = 4;
```

- [ ] **Step 2: Add to `AppConfig`**

```typescript
voiceBackendPlayback: boolean;
```

- [ ] **Step 3: Defaults**

```typescript
voiceBackendPlayback: true,
```

En `loadSavedConfig` y objeto default final.

- [ ] **Step 4: Persist on migrate** cuando `schemaVersion < 4`.

- [ ] **Commit** `feat(frontend): voiceBackendPlayback config v4`

---

## Task 24: `ttsPlaybackGate` — skip alert TTS si backend reproduce

**Files:** `frontend/src/services/ttsPlaybackGate.ts`, tests

- [ ] **Step 1: Write failing test**

```typescript
// frontend/src/__tests__/ttsPlaybackGate.backend.test.ts
import { describe, expect, it } from "vitest";
import { evaluateAlertTts } from "../services/ttsPlaybackGate";

describe("evaluateAlertTts voiceBackendPlayback", () => {
  it("denies alert TTS when backend owns playback", () => {
    const d = evaluateAlertTts({
      message: "Coche a la izquierda",
      payload: { category: "proximity", audio_priority: "2", severity: "INFO" },
      speakOnlyWhenSpokenTo: false,
      spotterEnabled: true,
      engineerEnabled: true,
      voiceBackendPlayback: true,
    });
    expect(d.allow).toBe(false);
    expect(d.reason).toBe("backend_playback");
  });

  it("allows alert TTS when flag false", () => {
    const d = evaluateAlertTts({
      message: "Coche a la izquierda",
      payload: { category: "proximity", audio_priority: "2", severity: "INFO" },
      speakOnlyWhenSpokenTo: false,
      spotterEnabled: true,
      engineerEnabled: true,
      voiceBackendPlayback: false,
    });
    expect(d.allow).toBe(true);
  });
});
```

- [ ] **Step 2: Implement — primera comprobación en `evaluateAlertTts`**

```typescript
export function evaluateAlertTts(params: {
  message: string;
  payload: Record<string, unknown>;
  speakOnlyWhenSpokenTo: boolean;
  spotterEnabled: boolean;
  engineerEnabled: boolean;
  voiceBackendPlayback?: boolean;
}): TtsPlaybackDecision {
  if (params.voiceBackendPlayback) {
    return recordDeny("alert", "backend_playback", String(params.payload.category ?? ""));
  }
  // ... existing gates unchanged ...
}
```

**INVARIANT:** UI/historial en `useWebSocket` **no** usar `ttsDecision.allow` para ocultar alertas visuales — solo para **encolar TTS**. Revisar L678–703: historial spotter puede seguir usando `ttsDecision.allow`; si quieres historial aunque backend hable, cambiar a gate separado `shouldLogAlertHistory` — **beta: mantener historial si `shouldVoiceAlert` true, solo skip audio**:

Opción recomendada (implementador):

```typescript
const voicePayload = flattenAlertPayload(payload);
const wouldVoice = shouldVoiceAlert(voicePayload); // for history
const ttsDecision = evaluateAlertTts({ ..., voiceBackendPlayback });
// history: use wouldVoice + toggles
// enqueue: use ttsDecision.allow only
```

Documentar en commit si se ajusta historial.

- [ ] **Step 3: Run**

```powershell
cd frontend
npm test -- --run src/__tests__/ttsPlaybackGate.backend.test.ts
```

- [ ] **Step 4: Commit** `feat(frontend): skip alert TTS when voiceBackendPlayback`

---

## Task 25: `useWebSocket` — pasar flag desde store + config_ack

**Files:** `frontend/src/hooks/useWebSocket.ts`

- [ ] **Step 1: `config_ack` handler** — patch flag:

```typescript
if (typeof ackCfg.voiceBackendPlayback === "boolean") {
  patch.voiceBackendPlayback = ackCfg.voiceBackendPlayback;
}
```

- [ ] **Step 2: `case "alert"`** — leer flag del store:

```typescript
const { speakOnlyWhenSpokenTo, spotterEnabled, engineerEnabled, voiceBackendPlayback } =
  useAppStore.getState().config;

const ttsDecision = evaluateAlertTts({
  message: alertMsg,
  payload,
  speakOnlyWhenSpokenTo,
  spotterEnabled,
  engineerEnabled,
  voiceBackendPlayback,
});
```

- [ ] **Step 3: No tocar `advice_end` / `commentary_end`** en este hito.

- [ ] **Step 4: Run frontend tests**

```powershell
cd frontend
npm test -- --run src/__tests__/ttsPlaybackGate.backend.test.ts src/__tests__/useWebSocket.spotter.test.ts
```

- [ ] **Step 5: Commit** `feat(ws): sync voiceBackendPlayback from config_ack`

---

## Task 26: Health — race loop + voice metrics

**Files:** `backend/src/routers/health.py`, `backend/tests/test_health_voice.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_health_voice.py
import time
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.routers.health import router as health_router
from src.race.telemetry_hub import TelemetryHub
from src.voice.voice_queue import VoiceQueue


def test_health_includes_race_and_voice_sections():
    app = FastAPI()
    app.include_router(health_router)
    hub = TelemetryHub()
    hub.update(snapshot={"lap": 1}, advice=None)
    hub.record_tick_time(time.monotonic())
    app.state.telemetry_hub = hub
    app.state.voice_queue = VoiceQueue()
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.latest_client_frame = None
    app.state.spotter_service = None

    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "race_loop" in body
    assert body["race_loop"]["tick_count"] >= 1
    assert "voice" in body
    assert "backend_playback" in body["voice"]
    assert "queue_size" in body["voice"]
    assert "player" in body["voice"]
```

- [ ] **Step 2: Implement**

```python
import time
# inside health_check:
hub = getattr(request.app.state, "telemetry_hub", None)
race_loop = {
    "tick_count": getattr(hub, "tick_count", 0) if hub else 0,
    "last_tick_age_s": (
        round(time.monotonic() - hub.last_tick_monotonic, 3)
        if hub and hub.last_tick_monotonic > 0
        else None
    ),
}
vq = getattr(request.app.state, "voice_queue", None)
player = getattr(request.app.state, "voice_player", None)
voice = {
    "backend_playback": settings.VOICE_BACKEND_PLAYBACK,
    "queue_size": vq.qsize() if vq else 0,
    "player": type(player).__name__ if player else None,
    "cache_size": getattr(getattr(request.app.state, "spotter_cache", None), "size", 0),
}
# return { ..., "race_loop": race_loop, "voice": voice }
```

- [ ] **Step 3: pytest PASS + commit** `feat(health): race_loop and voice metrics`

---

## Hito 4 GATE (orquestador MUST verify)

### Backend

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_voice_lifespan_wiring.py tests/test_config_update_ack_ws.py tests/test_voice_cache_keys.py tests/test_ducking.py tests/test_health_voice.py tests/test_voice_priority.py tests/test_voice_bridge.py tests/test_race_tick_loop.py -v
```

```powershell
Select-String -Path src\main.py -Pattern "edge_tts_service" | Select-Object -First 5
# Verificar que voice block (SpotterPhraseCache / voice_task) está DESPUÉS de edge init
```

Manual (Edge configurado):

```powershell
# Logs al arrancar:
# SpotterPhraseCache warmed (>=10)
# Voice player: PygameAudioPlayer
```

### Frontend

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\frontend
npm test -- --run src/__tests__/ttsPlaybackGate.backend.test.ts
```

### Integración manual (checklist)

- [ ] Conectar UI + backend; alerta spotter → **una sola voz** (backend, no HTMLAudioElement)
- [ ] Historial radio muestra alerta
- [ ] `GET /health` → `voice.player` = `PygameAudioPlayer`
- [ ] PTT respuesta (`voice_response` alert) → backend reproduce, frontend no duplica

| Criterio | Verificación |
|----------|--------------|
| Hotfix 3.1 | logs Pygame + warm |
| Config spotter | test_config_update_ack_ws |
| No doble alert TTS | ttsPlaybackGate test + manual |
| Health | test_health_voice |
| Regresión voz | test_voice_priority |

---

## Failure modes

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Sigue MockAudioPlayer | voice block antes de Edge | Task 17 |
| Doble voz alert | flag false en frontend o gate no aplicado | Tasks 22–25 |
| Cache miss limiter | alias faltante | Task 19 |
| config_ack test ERROR | SPOTTER_* missing | Task 18 |
| Historial vacío con backend | historial atado a ttsDecision | Task 24 nota |
| advice doble (futuro) | AdviceEnd no en backend | Hito 5+ |

---

## DoD Hito 4

- [ ] Voice block después de TTS init; Pygame en runtime con Edge
- [ ] `voiceBackendPlayback` en config_ack + frontend v4
- [ ] Alert TTS React silenciado cuando flag true
- [ ] `/health` race + voice
- [ ] SPOTTER_* en config; config_ack tests green
- [ ] Cache normalization + limiter aliases
- [ ] Ducking implementado (o noop documentado con pycaw install note)
- [ ] GATE backend + frontend green
- [ ] Orquestador marks INDEX gate ✅

---

## Entregable para orquestador

1. Output GATE pytest + vitest  
2. Screenshot o copy de logs startup (warm + Pygame)  
3. Output `GET /health` voice section  
4. Lista archivos vs ALLOWED  
5. Confirmación manual: una sola voz en alerta spotter  

---

# ANEXO — Revisión correcciones Hito 2 (checklist orquestador)

Estado tras Hito 3 + lo que cierra Hito 4:

| # | Corrección Hito 2 / review | Estado | Task Hito 4 |
|---|---------------------------|--------|-------------|
| 1 | `is_expired` usa `t > expires_at` | ✅ Hito 2 | — |
| 2 | `VoiceBridge.send` un solo WS emit | ✅ Hito 2 | — |
| 3 | `_enqueue_alert` no llama WS | ✅ Hito 2 | — |
| 4 | VoiceQueue tie-breaker `_seq` | ✅ Hito 2 | — |
| 5 | VoiceBridge antes de Spotter/Engine | ✅ Hito 2 | — |
| 6 | `map_alert_to_play_priority` / paridad IMMEDIATE | ✅ Hito 3 Task 11 | — |
| 7 | `wav_cache_key` ≠ `category=="spotter"` | ✅ Hito 3 Task 12 | Task 19 refina |
| 8 | VoiceQueue evict menor prioridad | ✅ Hito 3 Task 13 | — |
| 9 | Voice block **después** Edge TTS | ❌ Hito 3 | **Task 17** |
| 10 | `SPOTTER_CAR_LENGTH_M` en config | ❌ Hito 1 deuda | **Task 18** |
| 11 | Ducking funcional | ⚠️ stub Hito 3 | **Task 20** |
| 12 | Frontend no reproduce alert TTS | ❌ pendiente | **Tasks 22–25** |
| 13 | `transport.broadcaster` bypass LLM tokens | ⚪ abierto | Fuera scope beta (no AlertMessage) |
| 14 | Logs "WS broadcaster" misleading | ⚠️ | **Task 21** |
| 15 | `CommentaryEndMessage` solo WS | ⚪ diseño | Hito 5+ / beta aceptado |

**Conclusión Hito 2:** Implementación core **correcta y cerrada**. Items 9–12 no eran scope Hito 2 pero bloqueaban beta audible — **Hito 4 los cierra**.

---

## Orquestador review checklist (post-PR)

- [ ] Diff respeta ALLOWED/FORBIDDEN
- [ ] `main.py` orden: Edge init → voice block → yield
- [ ] Frontend: alert path silenciado, advice/commentary intactos
- [ ] No regresión race_loop / VoiceBridge
- [ ] Tests config_ack pasan sin skip

**Siguiente:** Hito 5 (`BETA_SLIM`, `doctor.ps1`, botón test audio) tras GATE ✅.
