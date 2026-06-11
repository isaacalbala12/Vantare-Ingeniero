# Hito 6 — E2E tests + beta gate (cierre beta)

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **30→35 en orden**.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** Tasks 19–22  
> **Decisiones ADR:** [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md) §6 (V1–V6)  
> **Pre-requisito:** Hito 5 GATE ✅

**Goal:** Cerrar la re-arquitectura voice beta con tests E2E spotter→cola, contrato frontend completo, tests de aceptación V1–V5 automatizados donde falten, suite green, script `verify_beta_gate`, y evidencia smoke V1–V6.

**Architecture:** Spotter → `VoiceBridge.send` → `PlayCommand` en `VoiceQueue` (IMMEDIATE) + WS alert; frontend no TTS cuando `voiceBackendPlayback`; `race_tick_loop` independiente de `voice_loop`.

**Tech Stack:** Python 3.12, pytest, Vitest, PowerShell.

**Shell:** PowerShell — usar `;` entre comandos.

---

## Protocolo anti-gap (OBLIGATORIO — leer antes de codear)

> Copiado del INDEX. Si incumples algún punto, **no marques task DONE**.

### A. Invariantes del hito (si alguna falla → task NO done)

| ID | Invariante |
|----|------------|
| I1 | Proximidad spotter IMMEDIATE → `VoiceQueue` con prioridad IMMEDIATE (no solo WS) |
| I2 | Con `voiceBackendPlayback=true`, **toda** alerta spotter/engineer → `evaluateAlertTts` = `backend_playback` |
| I3 | Crash/cancel de `voice_loop` **no** detiene `race_tick_loop` (V3) |
| I4 | N ticks de telemetría → spotter/CC eval **una vez por tick**, no por cliente WS (V4) |
| I5 | PTT concurrente no bloquea race tick >500 ms p95 en test sintético (V5) |
| I6 | `verify_beta_gate.ps1` exit 0 sin backend; doctor opcional con flag |
| I7 | **Prohibido** tests placeholder (`assert True`, `# TODO`, tests que no fallarían si quitas el código) |

### B. Antes de reportar DONE (cada task)

```powershell
# 1. Trace paths críticos (pegar output en entregable)
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
rg "VoiceBridge|voice_queue|race_tick_loop|voice_loop|evaluateAlertTts|voiceBackendPlayback" backend/src frontend/src --glob "*.{py,ts,tsx}" -l
```

```powershell
# 2. ¿Segunda vía que bypass el invariante?
#    (runtime config, .env, WS directo, AlertMessage duplicado)
rg "AlertMessage|broadcast_callback|enable_commentary_batch|VOICE_BACKEND_PLAYBACK" backend/src/routers/websocket.py backend/src/intelligence/engine.py
```

```powershell
# 3. GATE literal del task (no resumen)
```

### C. Plantilla de entregable al orquestador

```markdown
## Task NN — DONE
- Invariantes cubiertas: I?
- Archivos: ...
- rg trace: (N archivos listados)
- Segunda vía bypass: ninguna / (describir)
- Output GATE: (pegar últimas 10 líneas pytest/vitest)
- Tests placeholder: ninguno
```

---

## Preconditions (BLOCKING)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_beta_slim.py tests/test_test_audio_ws.py tests/test_voice_bridge.py tests/test_race_tick_loop.py -v --tb=line
```

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\frontend
npm test -- --run src/__tests__/ttsPlaybackGate.backend.test.ts src/__tests__/useWebSocket.backendPlayback.test.ts
```

Expected: all PASSED

---

## Mapa V1–V6 → tasks

| ID | Criterio ADR | Task | Automatizado |
|----|--------------|------|--------------|
| V1 | Spotter audible, UI cerrada, backend solo | 30, 31 | pytest + vitest |
| V2 | CC corre sin depender de WS | 32 | pytest (race loop) |
| V3 | Crash voice → race sigue | 32 | pytest |
| V4 | N clientes WS = 1 eval/tick | 32 | pytest |
| V5 | PTT no bloquea spotter >500 ms | 32 | pytest (sintético) |
| V6 | Deploy verificable doctor | 33, 35 | script + manual log |

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Create | `backend/tests/test_spotter_to_voice_queue.py` |
| Create | `backend/tests/test_acceptance_v2_v5.py` (V2–V5; nombre flexible) |
| Modify | `frontend/src/__tests__/voiceContractMatrix.test.ts` |
| Modify | `frontend/src/__tests__/fixtures/voiceContractCases.ts` (si hace falta VC-A06) |
| Create | `scripts/verify_beta_gate.ps1` |
| Modify | `scripts/verify_voice_contract.py` (opcional: incluir spotter→queue) |
| Create | `.omo/evidence/voice-beta-smoke-YYYYMMDD.md` |
| Fix | cualquier test bajo `backend/tests/` o `frontend/src/__tests__/` que falle en Task 34 |

### Files FORBIDDEN

- `crewchief_events/modules/**` (solo wiring existente)
- `shared-telemetry/**`, `shared-strategy/**`
- Segundo exe / supervisor / IPC
- **Task 23** Fase 2-R1 multiprocess (documento aparte, post-métricas)
- Refactors no relacionados con tests rojos

---

## Task 30: Spotter → VoiceQueue (E2E integración)

**Files:** `backend/tests/test_spotter_to_voice_queue.py`  
**Invariantes:** I1

### Step 1: Test que falla primero

Flujo completo:

1. `VoiceQueue` + `VoiceBridge(ws_broadcast=mock, voice_queue=q, enabled=True)`
2. `SpotterService(broadcast_callback=bridge.send)` con fixture `world_overlap_no_path_delta` o `side_by_side_gt3_hypercar`
3. `spotter.evaluate_tick(frame_to_spotter_tick(...))`
4. `await asyncio.sleep(0.05)` (bridge encola async)
5. Assert:
   - `q.qsize() >= 1`
   - cmd = dequeue o inspeccionar prioridad IMMEDIATE
   - `cmd.event_id` contiene `proximity` o payload equivalente
   - `cmd.priority == "IMMEDIATE"` (proximidad spotter)

Reutilizar fixtures de `tests/fixtures/spotter/` y patrón de `test_spotter_e2e.py`.

```python
# Esqueleto mínimo
@pytest.mark.asyncio
async def test_spotter_proximity_enqueues_immediate_play_command():
    q = VoiceQueue()
    ws_cb = MagicMock()
    bridge = VoiceBridge(ws_broadcast=ws_cb, voice_queue=q, enabled=True)
    spotter = SpotterService(broadcast_callback=bridge.send, proximity_threshold_m=3.0, enabled=True)
    frame = load_frame("world_overlap_no_path_delta")
    spotter.evaluate_tick(frame_to_spotter_tick(frame, advice=None))
    await asyncio.sleep(0.05)
    assert q.qsize() >= 1
    # inspeccionar prioridad IMMEDIATE
```

### Step 2: Implementar solo si el wiring ya existe (Hito 2) — **no tocar producción salvo bug**

Si el test falla por wiring roto, fix mínimo en `VoiceBridge` o `play_command_from_alert` (prioridad proximity).

### Step 3: pytest

```powershell
cd backend
python -m pytest tests/test_spotter_to_voice_queue.py -v --tb=short
```

### Step 4: Entregable anti-gap (plantilla §C)

---

## Task 31: Voice contract — `voiceBackendPlayback`

**Files:** `voiceContractMatrix.test.ts`, opcional `voiceContractCases.ts`  
**Invariantes:** I2

### Step 1: Añadir caso VC-A06 (o bloque dedicado)

```typescript
describe("invariant I6: voiceBackendPlayback silences frontend alert TTS", () => {
  it("VC-A06: backend_playback denies all alert categories", () => {
    for (const cat of ["proximity", "fuel", "engineer"]) {
      const d = evaluateAlertTts({
        message: "test",
        payload: { category: cat, service: cat === "proximity" ? "spotter" : "engineer" },
        speakOnlyWhenSpokenTo: false,
        spotterEnabled: true,
        engineerEnabled: true,
        voiceBackendPlayback: true,
      });
      expect(d.allow).toBe(false);
      expect(d.reason).toBe("backend_playback");
    }
  });
});
```

**INVARIANT:** `advice_end` / `commentary_end` **siguen** en frontend TTS (no incluir en este loop).

### Step 2: vitest

```powershell
cd frontend
npm test -- --run src/__tests__/voiceContractMatrix.test.ts
```

### Step 3: verify_voice_contract sigue green

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
python scripts/verify_voice_contract.py
```

---

## Task 32: Tests aceptación ADR V2–V5

**Files:** `backend/tests/test_acceptance_v2_v5.py` (nombre sugerido)  
**Invariantes:** I3, I4, I5

Tests **reales** (no placeholder). Cada test debe **fallar** si quitas el comportamiento bajo prueba.

### V2 — CC en race loop sin WS

Verificar que `run_race_tick_once` / `race_tick_loop` invoca `crewchief_loop.on_frame` **sin** mensaje WS.

Base existente: `test_race_tick_loop.py`, `test_crewchief_tick_rate.py`, `test_race_loop_no_ws.py`.

Añadir test de integración corto (~2 s, no 60 s real):

```python
@pytest.mark.asyncio
async def test_v2_cc_evaluates_on_race_tick_without_websocket():
    """V2: CC suite corre en race tick, no en evaluate_cycle ni WS."""
    # Mock deps + contador on_frame; 3 ticks; assert call_count == 3
    # assert engine.evaluate_cycle NO fue invocado (ya cubierto en test_crewchief_tick_rate)
```

### V3 — voice_loop crash → race sigue

```python
@pytest.mark.asyncio
async def test_v3_voice_loop_crash_does_not_stop_race_tick():
    """V3: cancel voice_loop task; race_tick_loop sigue incrementando hub."""
    # Patrón: voice_loop con player que lanza excepción una vez
    # race_tick_loop mock 5 ticks en paralelo
    # assert hub.tick_count >= 5 tras cancel voice task
```

Si `voice_loop` no tiene try/except resilient, fix **mínimo** en `backend/src/voice/service.py` para log + continue (solo si test lo exige).

### V4 — una evaluación por tick con N clientes WS

```python
def test_v4_spotter_eval_once_per_tick_regardless_of_ws_clients():
    """V4: spotter.evaluate_tick llamado 1× por race tick (contador interno)."""
    # Instrumentar spotter con MagicMock evaluate_tick
    # Simular 3 race ticks vía run_race_tick_once
    # assert evaluate_tick.call_count == 3 (no 3×N)
```

Referencia: `test_ws_integration.py::test_multiple_clients_delta_isolation` (WS no debe duplicar eval spotter).

### V5 — PTT no bloquea race tick >500 ms

Test sintético (sin LLM real):

```python
@pytest.mark.asyncio
async def test_v5_pilot_question_does_not_block_race_tick_over_500ms():
    """V5: handle_pilot_question async no serializa race_tick >500ms p95."""
    # Mock LLM lento (asyncio.sleep 0.1) en paralelo con 10 race ticks @ 20Hz sim
    # Medir max delta entre ticks; assert p95 < 0.5s OR document skip con razón
```

Si no es viable sin refactor, implementar versión mínima: `handle_pilot_question` corre en `asyncio.create_task` desde WS (ya lo hace) + assert race tick no espera await del engine.

### Step: pytest

```powershell
python -m pytest tests/test_acceptance_v2_v5.py tests/test_race_tick_loop.py tests/test_race_loop_no_ws.py tests/test_crewchief_tick_rate.py -v
```

---

## Task 33: `scripts/verify_beta_gate.ps1`

**Files:** `scripts/verify_beta_gate.ps1`  
**Invariantes:** I6

Script que encadena gates automatizados (exit 0 = beta gate CI OK):

```powershell
# scripts/verify_beta_gate.ps1
param([switch]$WithDoctor)  # -WithDoctor requiere backend :8008

# 1. verify_voice_contract.py
# 2. pytest subset aceptación + spotter→queue + beta_slim + voice_bridge
# 3. frontend: npm test --run (voice + playback tests mínimo)
# 4. if ($WithDoctor) { doctor.ps1 }
# Log: %TEMP%\vantare-beta-gate-*.log
```

Subset pytest sugerido:

```
tests/test_spotter_to_voice_queue.py
tests/test_acceptance_v2_v5.py
tests/test_beta_slim.py
tests/test_voice_bridge.py
tests/test_config_update_ack_ws.py
tests/test_health_voice.py
tests/test_race_tick_loop.py
tests/test_race_loop_no_ws.py
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_beta_gate.ps1
# Expected: exit 0
```

---

## Task 34: Suite completa green

**Invariantes:** todas

### Step 1: Backend full suite

```powershell
cd backend
python -m pytest -q --tb=line
```

Fix **solo** tests rotos por la re-arquitectura. No silenciar con `@pytest.mark.skip` salvo deuda documentada en entregable.

### Step 2: Frontend full suite

```powershell
cd frontend
npm test -- --run
```

### Step 3: verify_beta_gate

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_beta_gate.ps1
```

Expected: exit 0

---

## Task 35: Evidencia smoke V1–V6 (documento)

**Files:** `.omo/evidence/voice-beta-smoke-YYYYMMDD.md`  
**Invariantes:** V6 manual

Plantilla obligatoria:

```markdown
# Voice Beta Smoke — YYYY-MM-DD

| ID | Resultado | Evidencia |
|----|-----------|-----------|
| V1 | PASS/FAIL | test_spotter_to_voice_queue + audio manual / cache p95 |
| V2 | PASS/FAIL | test_acceptance_v2_v5::test_v2_* |
| V3 | PASS/FAIL | test_v3_* |
| V4 | PASS/FAIL | test_v4_* |
| V5 | PASS/FAIL | test_v5_* o manual + razón |
| V6 | PASS/FAIL | doctor.ps1 log path + duración |

## Comandos ejecutados
(p pegar output verify_beta_gate)

## Audio manual (V1)
- [ ] Config → Probar audio (backend) audible
- [ ] Spotter proximity audible sin TTS frontend duplicado

## Notas / deuda post-beta
```

**Manual mínimo:** ejecutar `doctor.ps1` con backend up (`-WithDoctor` si implementado) y pegar log.

---

## Hito 6 GATE (orquestador)

### Automatizado

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_beta_gate.ps1
```

```powershell
cd backend; python -m pytest -q --tb=no
```

```powershell
cd frontend; npm test -- --run
```

### Manual (orquestador / piloto)

- [ ] V1 audio en pista o sim — spotter sin doble voz
- [ ] V6 doctor green con backend bundle

| Criterio | Check |
|----------|-------|
| spotter→queue IMMEDIATE | Task 30 |
| backend_playback contract | Task 31 |
| V2–V5 tests reales | Task 32 |
| verify_beta_gate.ps1 | Task 33 |
| Suite green | Task 34 |
| Smoke doc | Task 35 |

---

## Failure modes

| Síntoma | Causa | Fix |
|---------|-------|-----|
| qsize=0 tras spotter | bridge.send async timing | sleep + await bridge path |
| priority NORMAL not IMMEDIATE | play_command mapping | priority.py proximity |
| V3 test fail | voice_loop crash kills process | try/except en service.py |
| full suite red | tests legacy sidecar | fix o skip documentado |
| doctor fail | backend down | `-WithDoctor` opcional en gate |

---

## DoD Hito 6 (beta cerrada)

- [ ] `test_spotter_to_voice_queue.py` green
- [ ] VC-A06 / backend_playback en matrix
- [ ] V2–V5 tests sin placeholder
- [ ] `verify_beta_gate.ps1` exit 0
- [ ] `pytest -q` + `npm test --run` green
- [ ] `.omo/evidence/voice-beta-smoke-*.md` con V1–V6
- [ ] Orquestador marca INDEX ✅

---

## Post-Hito 6 (fuera de scope)

- **Task 23** (Fase 2-R1 ProcessPool): solo si smoke documenta p95 race_loop >40 ms
- Release Tauri / PyInstaller rebuild
- Commit final solo si usuario lo pide

---

## Nota orquestador (Hito 5 cierre)

Hotfixes post-review Hito 5 ya en main:
- Whisper/MQTT/commentary batch gated con `BETA_SLIM` en arranque **y** runtime
- `doctor.ps1` exit 1 sin `_internal`
- Tests slim reales (no `assert True`)
