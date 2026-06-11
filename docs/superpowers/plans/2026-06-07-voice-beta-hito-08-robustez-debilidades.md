# Hito 8 — Revisión robustez: debilidades a reforzar

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **42→50 en orden**.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** Deuda post-beta + [`2026-05-22-ingeniero-robustez.md`](../../plans/2026-05-22-ingeniero-robustez.md) adaptado a ADR-004-R1  
> **Pre-requisito:** Hito 7 GATE ✅

**Goal:** Auditoría sistemática de puntos frágiles donde un cambio menor, config runtime, thread/async edge case o bundle stale puede romper spotter/ingeniero en pista. Convertir debilidades conocidas en **tests + gates + documentación**, no solo fixes ad hoc.

**Architecture:** Monolito in-process (`race_tick_loop` 20 Hz + `voice_loop` + LLM async). Robustez = invariantes verificables en arranque, runtime config, sync/async fronteras y empaquetado.

**Tech Stack:** pytest, Vitest, PowerShell, rg trace-the-flag.

---

## Protocolo anti-gap (OBLIGATORIO)

### A. Invariantes del hito

| ID | Invariante |
|----|------------|
| I1 | Ningún `@property` read-only del dominio voice/race se asigna directamente en lifespan o config sync |
| I2 | Flags `BETA_SLIM` gated en **arranque Y runtime** (`config_update` / `engine.apply_runtime_config`) |
| I3 | `VoiceBridge.send` encola desde sync **y** async context sin perder alertas |
| I4 | V5 PTT ejercita path real (`websocket` handler), no solo mock aislado |
| I5 | Test lifespan integración: `TestClient` + `/health` refleja wiring voice+raca |
| I6 | Bundle `_internal/src` no contiene dead code crítico (`spotter_eval_loop`) tras rebuild |
| I7 | `duck_lmu.exe` ausente → WARN documentado, build no falla silenciosamente |
| I8 | Matriz debilidades → test/gate/documento; **cero** items solo en prose |

### B. Inventario debilidades (matriz maestra)

| # | Debilidad | Severidad | Área | Task |
|---|-----------|-----------|------|------|
| D1 | Property assign crashea lifespan | P0 | main.py | 42 (audit) |
| D2 | Bundle src ≠ bytecode / copia stale | P0 | PyInstaller | 47 |
| D3 | BETA_SLIM bypass vía config WS | P1 | engine/config | 43 |
| D4 | VoiceBridge sin event loop pierde audio | P1 | voice/bridge | 44 |
| D5 | V5 test no representa PTT real | P1 | websocket | 45 |
| D6 | duck_lmu missing en release | P2 | native/electron | 46 |
| D7 | Hidden import drift en módulos nuevos | P2 | build | 48 |
| D8 | Lifespan wiring solo testeado estático | P1 | tests | 45 |
| D9 | `.env` secrets copiados al bundle | P2 | build | 49 |
| D10 | ProcessPool prematuro (GIL) | P3 | race | 50 (doc only) |
| D11 | Dead code confunde rebuild | P2 | websocket | 46 |
| D12 | Frontend doble TTS si gate bypass | P1 | frontend | 43 |

---

## Preconditions (BLOCKING)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_bundle_startup.ps1
```

```powershell
cd backend
python -m pytest tests/test_acceptance_v2_v5.py tests/test_config_sync_ws.py tests/test_beta_slim.py -q --tb=line
```

Expected: all PASSED

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Create | `backend/tests/test_property_assign_guard.py` |
| Create | `backend/tests/test_lifespan_integration.py` |
| Create | `backend/tests/test_voice_bridge_sync_context.py` |
| Modify | `backend/tests/test_acceptance_v2_v5.py` (V5 real path) |
| Modify | `backend/tests/test_config_sync_ws.py` (BETA_SLIM runtime) |
| Modify | `backend/src/voice/bridge.py` (solo si test D4 falla) |
| Modify | `backend/build_backend.py` (hash/mtime parity opcional) |
| Create | `scripts/build-duck-lmu.ps1` o doc build native |
| Modify | `frontend/electron-builder.yml` |
| Create | `docs/architecture/ADR-005-python-embed-eval.md` (draft) |
| Create | `.omo/evidence/robustez-debilidades-YYYYMMDD.md` |

### Files FORBIDDEN

- Activar ProcessPool / Fase 2-R1 en producción
- Refactor masivo `crewchief_events/modules/*`
- Mover LLM a proceso separado
- Commits unless user asks

---

## Task 42: Auditoría property vs setter

**Invariantes:** I1, D1

### Step 1: rg audit

```powershell
cd backend
rg "\.(verbosity|spotter|engine)\.\w+\s*=" src --glob "*.py"
rg "@property" src/intelligence src/voice src/race -A2
```

Lista blanca: asignaciones a `_private` attrs o setters explícitos (`set_*`).

### Step 2: Test guard

`backend/tests/test_property_assign_guard.py`:

- Escanea `main.py`, `engine.py` (config sync), `routers/websocket.py`
- Falla si encuentra patrones:
  - `enable_commentary_batch =`
  - `\.verbosity\.\w+ =` excepto via `set_`

### Step 3: pytest

```powershell
python -m pytest tests/test_property_assign_guard.py tests/test_main_lifecycle_contract.py -v
```

---

## Task 43: BETA_SLIM — trace runtime completo

**Invariantes:** I2, D3, D12

### Step 1: Trace-the-flag

```powershell
rg "BETA_SLIM|ENABLE_COMMENTARY_BATCH|ENABLE_MQTT|WHISPER|CHROMA|MQTT" backend/src --glob "*.py"
```

Por cada flag, documentar: **arranque** (`main.py`) + **runtime** (`engine.py`, `mqtt_service.py`, etc.).

### Step 2: Test runtime re-enable bloqueado

En `test_config_sync_ws.py` o `test_beta_slim.py`:

```python
@pytest.mark.asyncio
async def test_config_update_cannot_enable_commentary_batch_when_beta_slim():
    # settings.BETA_SLIM=True
    # enviar config_update enableCommentaryBatch=true
    # assert verbosity.enable_commentary_batch is False
```

Ya parcialmente en `engine.py:638` — test debe **fallar** si se quita el gate.

### Step 3: Frontend trace

```powershell
rg "voiceBackendPlayback|evaluateAlertTts|backend_playback" frontend/src
```

Assert: ningún path alert TTS bypass cuando `voiceBackendPlayback=true`.

---

## Task 44: VoiceBridge sync context

**Invariantes:** I3, D4

### Step 1: Test

`backend/tests/test_voice_bridge_sync_context.py`:

```python
def test_voice_bridge_send_from_sync_context_enqueues():
    # Sin asyncio loop activo (thread o sync test)
    # bridge.send(AlertMessage(...))
    # assert queue tiene PlayCommand (asyncio.run path)
```

### Step 2: Implementación mínima (si falla)

En `bridge.py`:

```python
except RuntimeError:
    asyncio.run(self._enqueue_alert(message))
```

Con log debug (ya presente). Verificar que no anida loops en pytest-asyncio.

### Step 3: pytest

```powershell
python -m pytest tests/test_voice_bridge_sync_context.py tests/test_voice_bridge.py -v
```

---

## Task 45: V5 + lifespan integración

**Invariantes:** I4, I5, D5, D8

### Step 1: Reforzar V5

Ampliar `test_acceptance_v2_v5.py::test_v5_*`:

- Medir `time.monotonic()` entre ticks durante PTT
- Assert p95 inter-tick < 500 ms (5 ticks mínimo)
- Opcional: importar handler WS y disparar mensaje PTT mientras corre `race_tick_loop` en background task

### Step 2: Lifespan integration test

`backend/tests/test_lifespan_integration.py`:

```python
from fastapi.testclient import TestClient
from src.main import app

def test_lifespan_health_voice_and_race_loop():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["voice"]["backend_playback"] is True
        assert body["race_loop"]["tick_count"] >= 0
        # Tras sleep corto, tick_count sube
```

Usar mocks/fixtures para no requerir LMU ni pygame hardware si tests lo permiten; skip documentado si pygame bloquea CI.

### Step 3: pytest

```powershell
python -m pytest tests/test_lifespan_integration.py tests/test_acceptance_v2_v5.py::test_v5_pilot_question_does_not_block_race_tick -v
```

---

## Task 46: duck_lmu + dead code bundle

**Invariantes:** I6, I7, D6, D11

### Step 1: electron-builder optional native

En `electron-builder.yml`, `extraResources` para `duck_lmu.exe` con `filter` — build **WARN** si falta, no error opaco.

Documentar en `scripts/build-duck-lmu.ps1`:

```powershell
cd native/duck_lmu
cargo build --release
```

### Step 2: Post-rebuild rg bundle

```powershell
rg "spotter_eval_loop" frontend/release/win-unpacked/resources/backend/_internal/src
rg "spotter_eval_loop" backend/dist/backend/_internal/src
```

Expected: **no matches**

### Step 3: Evidencia WARN duck

Si exe ausente, registrar en evidencia Task 50 con impacto (ducking LMU vía pycaw fallback).

---

## Task 47: Paridad source ↔ bundle

**Invariantes:** D2

### Step 1: Script check (build_backend o verify-release)

Comparar mtime o hash SHA256 de archivos críticos:

```
src/main.py ↔ _internal/src/main.py
src/voice/bridge.py ↔ _internal/src/voice/bridge.py
src/race/tick_loop.py ↔ _internal/src/race/tick_loop.py
```

Fallar verify-release si source más nuevo que bundle **y** no se pasó `-Build`.

### Step 2: Integrar en verify-release.ps1

Step `bundle_freshness`: WARN si `main.py` source mtime > bundled mtime.

---

## Task 48: Hidden import drift guard

**Invariantes:** D7

### Step 1: Test estático

```python
# tests/test_build_hidden_imports.py
VOICE_RACE_MODULES = ["src.voice.bridge", "src.race.tick_loop", ...]
def test_hidden_imports_cover_voice_race():
    text = Path("build_backend.py").read_text()
    for mod in VOICE_RACE_MODULES:
        assert mod in text
```

### Step 2: pytest

```powershell
python -m pytest tests/test_build_hidden_imports.py -v
```

---

## Task 49: Seguridad bundle .env

**Invariantes:** D9

### Step 1: Documentar riesgo

En evidencia y ADR note: `build_backend.py` copia `.env` al bundle — **no incluir secrets de prod** en builds release.

### Step 2: WARN en build

Si `.env` contiene `OPENAI_API_KEY=` no vacío, print WARN (no fail en dev).

Opcional: usar `.env.example` only en CI release.

---

## Task 50: Documentación deuda + evidencia cierre

**Invariantes:** I8, D10

### Step 1: ADR-005 draft

`docs/architecture/ADR-005-python-embed-eval.md`:

- Problema Fase 2 PyInstaller (copia manual src)
- Alternativa python-embed + pip
- Criterios migración (bundle size, startup, CI)
- **No implementar** en beta

### Step 2: Matriz cierre

`.omo/evidence/robustez-debilidades-YYYYMMDD.md`:

| Debilidad | Mitigación | Test/Gate | Estado |
|-----------|------------|-----------|--------|
| D1 | setter audit | test_property_assign_guard | PASS/FAIL |
| ... | ... | ... | ... |

Cada fila D1–D12 debe tener enlace a test o script.

### Step 3: ProcessPool (D10)

Documentar gate: activar Fase 2-R1 solo si smoke pista documenta `race_loop` p95 > 40 ms sostenido.

---

## Hito 8 GATE (orquestador)

### Automatizado (BLOCKING)

```powershell
cd backend
python -m pytest tests/test_property_assign_guard.py tests/test_voice_bridge_sync_context.py tests/test_lifespan_integration.py tests/test_build_hidden_imports.py tests/test_acceptance_v2_v5.py tests/test_config_sync_ws.py tests/test_beta_slim.py -q --tb=line
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_beta_gate.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

### Trace final

```powershell
rg "spotter_eval_loop|enable_commentary_batch = False" backend/src backend/dist frontend/release --glob "*.py" 2>$null
```

Expected: zero en `backend/src/`; zero en bundle post-rebuild

---

## Failure modes

| Síntoma | Debilidad | Fix Task |
|---------|-----------|----------|
| Crash al arrancar bundle | D1 | 42 |
| Feature funciona en dev, falla en exe | D2 | 47 + rebuild |
| Commentary batch vuelve tras config | D3 | 43 |
| Spotter WS sí, sin audio | D4 | 44 |
| PTT congela spotter en pista | D5 | 45 + métricas |
| Build warn duck ignorado | D6 | 46 |
| Nuevo módulo voice ImportError | D7 | 48 |
| `/health` mentira vs runtime | D8 | 45 |
| API keys en instalador | D9 | 49 |

---

## DoD Hito 8 (robustez beta)

- [ ] Matriz D1–D12 con test/gate cada una
- [ ] `test_property_assign_guard.py` green
- [ ] `test_voice_bridge_sync_context.py` green
- [ ] `test_lifespan_integration.py` green (o skip CI documentado)
- [ ] V5 con assert timing p95
- [ ] BETA_SLIM runtime test green
- [ ] `test_build_hidden_imports.py` green
- [ ] Bundle sin `spotter_eval_loop`
- [ ] ADR-005 draft commiteable
- [ ] `.omo/evidence/robustez-debilidades-*.md` completo
- [ ] `verify_beta_gate.ps1` + `verify-release.ps1` exit 0
- [ ] Orquestador marca INDEX ✅

---

## Post-Hito 8 (beta estable — operación)

| Item | Cuándo |
|------|--------|
| Audio manual pista V1 completo | Antes de distribuir beta |
| `doctor.ps1 -WithDoctor` en sesión real | Cada release |
| Fase 2-R1 ProcessPool | Solo si p95 race_loop > 40 ms |
| Migración python-embed | Post-beta, ADR-005 |
| RAG/ChromaDB en pista | Fuera beta (BETA_SLIM) |

---

## Referencias cruzadas

- [`2026-06-07-voice-beta-hito-07-bundle-release.md`](2026-06-07-voice-beta-hito-07-bundle-release.md) — empaquetado
- [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md) — P0–P2 originales
- [`../../plans/2026-05-22-ingeniero-robustez.md`](../../plans/2026-05-22-ingeniero-robustez.md) — plan histórico engine
