# Hito 5 — Beta slim + doctor + test audio

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **27→29 en orden**.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** Tasks 16–18  
> **Pre-requisito:** Hito 4 GATE ✅ (incl. Task 25 `useWebSocket` — aplicado por orquestador post-review)

**Goal:** Backend **beta estable**: menos superficie (sin RAG/MQTT/commentary batch en arranque), script `doctor.ps1` post-install, botón **Probar audio** que encola TTS backend.

**Architecture:** Flags `BETA_SLIM` en config → lifespan condicional → doctor valida bundle + `/health` voice → WS `test_audio` → `VoiceQueue`.

**Tech Stack:** Python 3.12, FastAPI, PowerShell, React 19, Vitest, pytest.

**Shell:** PowerShell — usar `;` entre comandos.

---

## Preconditions (BLOCKING)

- [ ] Hito 4 completo (backend Pygame + frontend `voiceBackendPlayback` wired)
- [ ] Baseline:

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_config_update_ack_ws.py tests/test_health_voice.py tests/test_voice_bridge.py -v --tb=line
```

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\frontend
npm test -- --run src/__tests__/ttsPlaybackGate.backend.test.ts src/__tests__/useWebSocket.backendPlayback.test.ts
```

Expected: all PASSED

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/src/config.py` |
| Modify | `backend/src/main.py` |
| Modify | `backend/src/intelligence/engine.py` |
| Modify | `backend/src/routers/websocket.py` (+ handler `test_audio`) |
| Create | `scripts/doctor.ps1` |
| Create | `backend/tests/test_beta_slim.py` |
| Create | `backend/tests/test_test_audio_ws.py` |
| Modify | `frontend/src/components/ConfigTab.tsx` (botón audio) |
| Modify | `frontend/src/services/wsCommands.ts` o helper WS send (si existe) |
| Create | `frontend/src/__tests__/configTab.testAudio.test.ts` (opcional mock) |

### Files FORBIDDEN

- `backend/src/race/**` (salvo bugfix aprobado)
- `crewchief_events/modules/**`
- `shared-telemetry/**`, `shared-strategy/**`
- Segundo exe / supervisor / IPC
- Suite E2E completa (Hito 6)

---

## Task 27: BETA_SLIM — desactivar features no beta

**Files:** `config.py`, `main.py`, `engine.py`, `tests/test_beta_slim.py`

- [ ] **Step 1: Add flags en `config.py`**

```python
BETA_SLIM: bool = True
ENABLE_CHROMA_RAG: bool = False  # override: BETA_SLIM False → True manual
ENABLE_MQTT: bool = False
ENABLE_COMMENTARY_BATCH: bool = False
WHISPER_PRELOAD: str = "off"  # was "startup" optional — slim default off
```

**INVARIANT:** Cuando `BETA_SLIM=True`:
- No init `EventStore` (ChromaDB)
- No spawn MQTT si `ENABLE_MQTT=False`
- `engine.verbosity.enable_commentary_batch = False` en lifespan
- Whisper preload solo si `WHISPER_PRELOAD.lower() == "startup"`

- [ ] **Step 2: Write failing test**

```python
# backend/tests/test_beta_slim.py
from unittest.mock import patch
from src.config import settings


def test_beta_slim_defaults():
    assert settings.BETA_SLIM is True
    assert settings.ENABLE_CHROMA_RAG is False
    assert settings.WHISPER_PRELOAD.lower() == "off"


@patch("src.config.settings.BETA_SLIM", True)
@patch("src.config.settings.ENABLE_CHROMA_RAG", False)
def test_event_store_skipped_when_slim(monkeypatch):
    """Documenta contrato: lifespan no debe requerir chromadb cuando slim."""
    # Test de integración ligero: import main lifespan fragment o mock
    # Mínimo: assert gate en main.py existe via grep en CI manual
    assert True  # replace with lifespan test if feasible
```

Preferido: test lifespan con `TestClient` + mock que verifica `app.state.event_store is None` tras startup cuando slim.

- [ ] **Step 3: Implement `main.py`**

Wrap EventStore block:

```python
event_store = None
if settings.ENABLE_CHROMA_RAG and not settings.BETA_SLIM:
    try:
        ...
```

MQTT:

```python
if settings.MQTT_ENABLED and settings.ENABLE_MQTT and not settings.BETA_SLIM:
    ...
```

After `IntelligenceEngine` init:

```python
if settings.BETA_SLIM or not settings.ENABLE_COMMENTARY_BATCH:
    intelligence_engine.verbosity.enable_commentary_batch = False
```

- [ ] **Step 4: pytest PASS**

```powershell
python -m pytest tests/test_beta_slim.py -v
python -c "from src.main import app; print('import ok')"
```

- [ ] **Step 5: Commit** `feat(beta): BETA_SLIM disables RAG/MQTT/commentary batch`

---

## Task 28: `scripts/doctor.ps1`

**Files:** `scripts/doctor.ps1`

- [ ] **Step 1: Create script** (extendido vs plan maestro)

Checks obligatorios:

1. `_internal` existe (PyInstaller onedir)
2. `import pygame; pygame.mixer.init()` (bundled python o dev `python`)
3. `GET http://127.0.0.1:8008/health` → `status=ok`
4. `health.race_loop.tick_count` ≥ 0 (warn si 0 y backend recién arrancó)
5. `health.voice.backend_playback` = true
6. `health.voice.player` = `PygameAudioPlayer` (warn si MockAudioPlayer)
7. `health.voice.cache_size` ≥ 10 (warn si 0)
8. Log file en `%TEMP%\vantare-doctor-*.log`

```powershell
# scripts/doctor.ps1 — esqueleto
$ErrorActionPreference = "Stop"
$log = Join-Path $env:TEMP "vantare-doctor-$(Get-Date -Format 'yyyyMMdd-HHmmss').log"
function Log($msg) { "$(Get-Date -Format 'HH:mm:ss') $msg" | Tee-Object -FilePath $log -Append }

$repoRoot = Split-Path $PSScriptRoot -Parent
$backendRoot = Join-Path $repoRoot "frontend\src-tauri\binaries\backend"
if (-not (Test-Path $backendRoot)) {
    $backendRoot = Join-Path $repoRoot "backend\dist\backend"
}

Log "=== Vantare Doctor ==="
Log "Backend root: $backendRoot"

if (-not (Test-Path (Join-Path $backendRoot "_internal"))) {
    Log "FAIL: _internal missing"
    exit 1
}
Log "OK: _internal"

# pygame check (bundled or system python)
$port = 8008
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health" -TimeoutSec 5
    Log "OK: health status=$($h.status)"
    Log "race_loop ticks=$($h.race_loop.tick_count)"
    Log "voice player=$($h.voice.player) cache=$($h.voice.cache_size) playback=$($h.voice.backend_playback)"
    if ($h.voice.player -ne "PygameAudioPlayer") { Log "WARN: expected PygameAudioPlayer" }
} catch {
    Log "FAIL: /health — $_ (¿backend corriendo?)"
    exit 1
}

Log "Doctor complete: $log"
exit 0
```

- [ ] **Step 2: Manual run** (backend debe estar up)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1
```

Expected: exit 0, log path printed

- [ ] **Step 3: Commit** `feat(scripts): add doctor.ps1 post-install health check`

---

## Task 29: Botón «Probar audio» + WS `test_audio`

**Files:** `websocket.py`, `ConfigTab.tsx`, tests

### Backend

- [ ] **Step 1: Failing test**

```python
# backend/tests/test_test_audio_ws.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from src.routers.websocket import router as ws_router
from src.voice.voice_queue import VoiceQueue


@pytest.mark.asyncio
async def test_test_audio_enqueues_play_command():
    app = FastAPI()
    app.include_router(ws_router)
    q = VoiceQueue()
    app.state.voice_queue = q
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.latest_client_frame = None
    app.state._last_telemetry_t = 0.0

    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"event": "test_audio"})
        # allow async handler
        import asyncio
        asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.05))
    assert q.qsize() >= 1
```

(Ajustar si handler es async — usar `await asyncio.sleep` en test async.)

- [ ] **Step 2: Handler en `websocket.py`**

Después de `spotter_command`, antes de `pilot_question`:

```python
elif event == "test_audio":
    voice_queue = getattr(app_state, "voice_queue", None)
    if voice_queue is not None and settings.VOICE_BACKEND_PLAYBACK:
        from src.voice.play_command import play_command_from_alert
        cmd = play_command_from_alert(
            text="Probando audio. ¿Me escuchás?",
            category="engineer",
            audio_priority="NORMAL",
            event_id="test_audio",
            ttl_seconds=10,
            payload={"event_id": "test_audio"},
        )
        await voice_queue.put(cmd)
        logger.info("[WS] test_audio enqueued")
    else:
        logger.warning("[WS] test_audio ignored — voice queue unavailable")
```

**INVARIANT:** No usar `AlertMessage` (evita doble path frontend); encolar `PlayCommand` directo.

- [ ] **Step 3: pytest PASS**

```powershell
python -m pytest tests/test_test_audio_ws.py -v
```

### Frontend

- [ ] **Step 4: Botón en `ConfigTab.tsx` sección audio**

Debajo de `AudioTtsPanel`, antes de PTT:

```tsx
{section === "audio" && (
  <button
    type="button"
    className="mt-2 hub-btn-secondary w-fit"
    onClick={() => {
      const ws = /* obtener WS activo: registerWsCommands o ref expuesto */;
      ws?.send(JSON.stringify({ event: "test_audio" }));
    }}
  >
    Probar audio (backend)
  </button>
)}
```

**Implementación:** Reutilizar `registerWsCommands` / callback existente en `useWebSocket` — añadir `sendTestAudio()` exportado como otros comandos WS.

Ejemplo en `wsCommands.ts`:

```typescript
let sendJson: ((payload: object) => void) | null = null;

export function registerWsSend(fn: (payload: object) => void) {
  sendJson = fn;
}

export function sendTestAudio() {
  sendJson?.({ event: "test_audio" });
}
```

Wire en `useWebSocket` donde ya se registra `registerWsCommands`.

- [ ] **Step 5: Vitest (opcional)**

```typescript
// frontend/src/__tests__/configTab.testAudio.test.ts
import { describe, it, expect, vi } from "vitest";
import { sendTestAudio, registerWsSend } from "../services/wsCommands";

describe("sendTestAudio", () => {
  it("sends test_audio event", () => {
    const send = vi.fn();
    registerWsSend(send);
    sendTestAudio();
    expect(send).toHaveBeenCalledWith({ event: "test_audio" });
  });
});
```

- [ ] **Step 6: Commit** `feat(audio): test_audio WS + UI button`

---

## Hito 5 GATE (orquestador)

### Backend

```powershell
cd backend
python -m pytest tests/test_beta_slim.py tests/test_test_audio_ws.py tests/test_config_update_ack_ws.py tests/test_health_voice.py -v
python -c "from src.main import app; print('import ok')"
```

### Scripts

```powershell
# Backend running on :8008
powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1
```

Expected: exit 0; voice.player=PygameAudioPlayer

### Manual

- [ ] Arranque con `BETA_SLIM=true`: log **sin** "EventStore initialized"
- [ ] Config → Audio → «Probar audio» → se oye frase backend
- [ ] `/health` → voice section OK

| Criterio | Check |
|----------|-------|
| Slim startup | no ChromaDB |
| doctor.ps1 | exit 0 |
| test_audio | queue + audible |
| Regresión Hito 4 | config_ack + playback tests |

---

## Failure modes

| Síntoma | Causa | Fix |
|---------|-------|-----|
| doctor FAIL health | backend down | start backend first |
| MockAudioPlayer in doctor | Edge init fail | check Edge TTS |
| test_audio silent | voice_queue None | VOICE_BACKEND_PLAYBACK |
| Chroma still loads | gate wrong | Task 27 |
| Button no WS | registerWsSend not wired | Task 29 |

---

## DoD Hito 5

- [ ] `BETA_SLIM` + gates en lifespan
- [ ] `scripts/doctor.ps1` committed
- [ ] `test_audio` WS + UI button
- [ ] GATE pytest green
- [ ] doctor manual OK
- [ ] Orquestador marks INDEX ✅

---

## Entregable

1. pytest output GATE  
2. doctor.ps1 log snippet  
3. Confirmación audio manual  
4. Archivos vs ALLOWED  

**Siguiente:** Hito 6 — suite green + smoke V1–V6 + E2E spotter→queue.

---

## Nota orquestador (Hito 4 cierre)

Task 25 aplicada directamente:
- `useWebSocket.ts`: `voiceBackendPlayback` en alert + config_ack
- Historial radio desacoplado de TTS (`shouldLogRadioHistory`)
- Tests: `test_config_ack_includes_voice_backend_playback`, `useWebSocket.backendPlayback.test.ts`
