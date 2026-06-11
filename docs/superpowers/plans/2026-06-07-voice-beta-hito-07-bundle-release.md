# Hito 7 — Empaquetado PyInstaller + smoke bundle (release verificable)

> **For agentic workers (Pi Agent / implementador):** Ejecutar tasks **36→41 en orden**.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)  
> **Plan maestro (referencia):** Post-Hito 6 — release Tauri/PyInstaller  
> **Decisiones ADR:** [`../../architecture/2026-06-07-rearchitecture-decisions-record.md`](../../architecture/2026-06-07-rearchitecture-decisions-record.md) §6 (V1, V6)  
> **Pre-requisito:** Hito 6 GATE ✅

**Goal:** Ningún instalador sale sin pasar smoke del **backend.exe empaquetado**. Cerrar el gap detectado en code review: la suite pytest green **no garantizaba** que el bundle arrancara (bug P0 `enable_commentary_batch` property assign).

**Architecture:** PyInstaller `--onedir` + Fase 2 copia `src/` → `_internal/src/` (fuente ≠ bytecode). Gates en build, doctor, verify-release y script dedicado `verify_bundle_startup.ps1`.

**Tech Stack:** PyInstaller, electron-builder, PowerShell, pytest (contratos estáticos).

**Shell:** PowerShell — usar `;` entre comandos.

---

## Protocolo anti-gap (OBLIGATORIO)

### A. Invariantes del hito

| ID | Invariante |
|----|------------|
| I1 | `build_backend.py` **falla** si `_internal/src/main.py` viola contratos lifespan |
| I2 | `verify_bundle_startup.ps1` spawn `backend.exe` → `/health` OK con `PygameAudioPlayer` + `race_loop.tick_count ≥ 1` |
| I3 | `verify-release.ps1` valida contrato `main.py` empaquetado **y** ejecuta bundle startup smoke |
| I4 | `doctor.ps1` valida contrato `main.py` en `_internal` antes de checks pygame |
| I5 | Tests estáticos `test_main_lifecycle_contract.py` + `test_beta_slim.py` en `verify_beta_gate.ps1` |
| I6 | Instalador NSIS generado **después** del fix lifespan (versión `package.json` coherente con setup.exe) |
| I7 | **Prohibido** marcar GATE sin pegar output literal de `verify_bundle_startup.ps1` |

### B. Trace-the-flag (antes de DONE)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
rg "verify_bundled_main|verify_bundle_startup|bundle_main_contract|set_enable_commentary_batch" backend scripts docs/superpowers/plans --glob "*.{py,ps1,md}"
rg "spotter_eval_loop|enable_commentary_batch = False" backend/src backend/dist frontend/release --glob "*.py"
```

### C. Segunda vía (bundle bypass)

| Riesgo | Mitigación en este hito |
|--------|-------------------------|
| Source OK, bundle stale | Rebuild obligatorio Task 39; verify post-copy |
| Parche manual win-unpacked | No cuenta como GATE — solo rebuild |
| Tauri `src-tauri/binaries` desactualizado | `build_backend.py` copia post-verify |

---

## Preconditions (BLOCKING)

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero\backend
python -m pytest tests/test_main_lifecycle_contract.py tests/test_beta_slim.py -v --tb=line
```

Expected: all PASSED

---

## Mapa debilidades → tasks (empaquetado)

| Debilidad | Evidencia histórica | Task |
|-----------|---------------------|------|
| Bundle crashea al arrancar | `AttributeError: enable_commentary_batch setter` | 36, 37 |
| Ningún hito exigía smoke PyInstaller | Code review Hito 6 | 38, 39 |
| Doctor no miraba main empaquetado | P0 en pista con exe viejo | 38 |
| Hidden imports voice/race incompletos | ImportError en bundle | 37 |
| Instalador 0.2.13 pre-fix | setup.exe stale | 39, 40 |

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Modify | `backend/build_backend.py` (`verify_bundled_main`, `HIDDEN_IMPORTS`) |
| Create | `scripts/verify_bundle_startup.ps1` |
| Modify | `scripts/verify-release.ps1` |
| Modify | `scripts/doctor.ps1` |
| Modify | `scripts/verify_beta_gate.ps1` (incluir lifecycle tests) |
| Create | `backend/tests/test_main_lifecycle_contract.py` |
| Modify | `frontend/electron-builder.yml` (duck_lmu filter — no bloquear build) |
| Create | `.omo/evidence/bundle-release-smoke-YYYYMMDD.md` |

### Files FORBIDDEN

- Sustituir PyInstaller por python-embed (ADR-005 — solo doc en Hito 8)
- `crewchief_events/modules/**` refactor
- Segundo exe / supervisor
- Commits unless user asks

---

## Task 36: Contratos lifespan en source (pytest estático)

**Files:** `backend/tests/test_main_lifecycle_contract.py`  
**Invariantes:** I5

### Step 1: Tests que fallan si regresa dead code

```python
def test_main_spawns_race_tick_not_spotter_eval_loop():
    text = _main_source()
    assert "race_tick_loop" in text
    assert "race_task = asyncio.create_task(race_tick_loop" in text
    assert "spotter_eval_loop" not in text

def test_main_uses_commentary_batch_setter_not_property_assign():
    text = _main_source()
    assert "set_enable_commentary_batch(False)" in text
    assert "enable_commentary_batch = False" not in text
```

### Step 2: pytest

```powershell
cd backend
python -m pytest tests/test_main_lifecycle_contract.py -v
```

### Step 3: Eliminar `spotter_eval_loop` de `websocket.py` si aún existe

```powershell
rg "spotter_eval_loop" backend/src
```

Expected: **no matches** en `backend/src/`

---

## Task 37: Gate en build PyInstaller

**Files:** `backend/build_backend.py`  
**Invariantes:** I1

### Step 1: `verify_bundled_main()` post Fase 2 copy

Llamar **después** de copiar `src/` → `_internal/src/`, **antes** de copiar a Tauri.

Required strings:
- `set_enable_commentary_batch(False)`
- `race_tick_loop`

Forbidden strings:
- `enable_commentary_batch = False`
- `spotter_eval_loop`

### Step 2: Hidden imports voice/race

Asegurar en `HIDDEN_IMPORTS`:

```
src.race.tick_loop
src.race.telemetry_hub
src.voice.bridge
src.voice.service
src.voice.player_pygame
src.voice.tts_manager
src.voice.spotter_cache
src.voice.play_command
src.voice.voice_queue
pygame
shared_telemetry
shared_strategy
```

### Step 3: Build local

```powershell
cd backend
python build_backend.py
```

Expected: `[+] Bundle main.py contract OK` antes de copiar a Tauri

---

## Task 38: Doctor + verify-release contrato bundle

**Files:** `scripts/doctor.ps1`, `scripts/verify-release.ps1`  
**Invariantes:** I3, I4

### Step 1: doctor.ps1 — bloque 1b

Tras detectar `_internal`, leer `_internal/src/main.py` y fallar con exit 1 si:
- falta `set_enable_commentary_batch(False)`
- existe `enable_commentary_batch = False`
- existe `spotter_eval_loop`

### Step 2: verify-release.ps1 — `bundle_main_contract`

En sección artifact checks, mismas reglas sobre `$bundleMain` (dist o tauri binaries).

### Step 3: verify-release llama `verify_bundle_startup.ps1` en smoke (sin `-Build`)

Antes de `release_smoke.py`, si existe `backend.exe`.

---

## Task 39: Script smoke bundle dedicado

**Files:** `scripts/verify_bundle_startup.ps1`  
**Invariantes:** I2

### Comportamiento

1. Resolver `backend.exe` en `backend/dist/backend/` o `frontend/release/win-unpacked/resources/backend/`
2. Validar contratos en `_internal/src/main.py`
3. Spawn con `HOST=127.0.0.1`, `PORT=8009`, `VANTARE_NATIVE_TELEMETRY=1`
4. Poll `/health` hasta 45s
5. Assert:
   - `status == "ok"`
   - `voice.player == "PygameAudioPlayer"`
   - `voice.backend_playback == true`
   - `race_loop.tick_count >= 1`
6. Kill proceso en `finally`

### GATE

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_bundle_startup.ps1
```

Expected: `=== bundle startup OK ===` + exit 0

---

## Task 40: Rebuild desktop completo

**Files:** N/A (pipeline)  
**Invariantes:** I6

### Step 1: Build

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-desktop.ps1
```

### Step 2: Release gate con build

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1 -Build
```

O si build ya hecho:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

### Step 3: Coherencia versión

```powershell
Get-ChildItem frontend/release/*-setup.exe | Sort-Object LastWriteTime -Descending | Select-Object -First 1
(Get-Content frontend/package.json | ConvertFrom-Json).version
```

Expected: nombre setup incluye versión de package.json

---

## Task 41: Evidencia smoke bundle + manual V1

**Files:** `.omo/evidence/bundle-release-smoke-YYYYMMDD.md`  
**Invariantes:** V1 manual, V6

Plantilla:

```markdown
# Bundle Release Smoke — YYYY-MM-DD

## Automatizado
| Check | Resultado | Output |
|-------|-----------|--------|
| verify_bundled_main (build) | PASS/FAIL | (línea contract OK) |
| verify_bundle_startup.ps1 | PASS/FAIL | player=PygameAudioPlayer ticks=N |
| verify-release.ps1 | PASS/FAIL | report path |

## Manual (obligatorio pre-pista)
- [ ] Abrir `frontend/release/win-unpacked/Vantare Ingeniero IA.exe`
- [ ] Config → «Probar audio (backend)» audible
- [ ] `/health` desde bundle: backend_playback=true
- [ ] Spotter proximity sin doble TTS frontend

## doctor.ps1
```powershell
powershell -File scripts/doctor.ps1 -WithDoctor
```
(pegar log)

## Deuda conocida
- duck_lmu.exe: WARN si ausente (Hito 8)
- Fase 2-R1 ProcessPool: gated post-métricas p95
```

---

## Hito 7 GATE (orquestador)

### Automatizado (BLOCKING)

```powershell
cd backend
python -m pytest tests/test_main_lifecycle_contract.py tests/test_beta_slim.py -q
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify_bundle_startup.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-release.ps1
```

### Manual (BLOCKING para beta pista)

| Criterio | Check |
|----------|-------|
| Instalador post-fix | Task 40 |
| App empaquetada arranca | Task 41 |
| Audio backend audible | Task 41 manual |
| doctor green | `-WithDoctor` |

---

## Failure modes

| Síntoma | Causa | Fix |
|---------|-------|-----|
| `AttributeError` setter | property assign en main.py | `set_enable_commentary_batch(False)` |
| verify OK, app falla | win-unpacked parcheado a mano | Rebuild Task 40 |
| tick_count=0 | race_loop no wired en bundle | rebuild + verify_bundled_main |
| ImportError pygame/voice | hidden-import faltante | Task 37 |
| electron-builder duck warn | exe nativo no compilado | Hito 8 Task 46 |
| setup.exe versión vieja | no rebuild tras bump | Task 40 |

---

## DoD Hito 7

- [ ] `verify_bundled_main()` en build_backend.py
- [ ] `verify_bundle_startup.ps1` exit 0
- [ ] `verify-release.ps1` incluye bundle contract + startup
- [ ] `doctor.ps1` valida main empaquetado
- [ ] `test_main_lifecycle_contract.py` en beta gate
- [ ] `spotter_eval_loop` ausente en `backend/src/`
- [ ] setup.exe regenerado coherente con package.json
- [ ] Evidencia `.omo/evidence/bundle-release-smoke-*.md`
- [ ] Orquestador marca INDEX ✅

---

## Post-Hito 7

- Hito 8 — robustez/debilidades restantes
- Fase 2-R1 ProcessPool solo con métricas p95 en pista
- Evaluación python-embed (ADR-005 draft)
