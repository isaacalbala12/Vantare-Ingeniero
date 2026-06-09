# Plan: Quality Fixes + CrewChiefV4 Parity (Spotter & TTS)

## TL;DR

> **Quick Summary**: Corregir bugs críticos de seguridad y calidad de código en toda la app (Phase 1), luego implementar parity funcional con CrewChiefV4 en spotter y TTS (Phase 2). TDD obligatorio en cada tarea.
> 
> **Deliverables**:
> - Phase 1: 12 bugs críticos/altos corregidos, seguridad fortalecida, dead code eliminado
> - Phase 2: Spotter con state machine (clear/hold/three-wide/closing speed), TTS con volume boost y voz separada
> - Tests TDD para cada cambio
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES — 5 waves de 4-7 tareas cada una
> **Critical Path**: Sec1 → Sec7 → Sec8 → Par1 → Par5 (config UI)

---

## Context

### Original Request
> "Necesitamos hacer una revisión exhaustiva de toda la calidad de código de la app. Después de corregir la calidad revisaremos que la app se comporta EXACTAMENTE como CrewChiefV4 en la parte de spotter, tts y demás simplemente adaptado a un lenguaje mejor como python."

### Interview Summary
**Key Decisions**:
- **Orden**: Primero calidad (Phase 1), luego parity (Phase 2) — secuencial
- **Idioma spotter**: Español (mantener actual)
- **Speech recognition**: NO — fuera de scope
- **Parámetros spotter**: Configurables vía UI (car length, overlap delay, clear delay, gap frequency)
- **Tests**: TDD completo (RED-GREEN-REFACTOR) para cada tarea
- **Otro agente**: Sin restricciones

### Metis Review
**Identified Gaps** (addressed):
- File ownership: sin restricciones con otro agente ✓
- Draft actualizado con todas las decisiones de usuario ✓
- Scope hardening: MAYBE eliminado, EXCLUDE explícito ✓
- Test strategy documentado en draft ✓

---

## Work Objectives

### Core Objective
Corregir bugs críticos de seguridad/calidad en la app, luego implementar parity con CrewChiefV4 en spotter (state machine, clear, hold line, three wide, closing speed) y TTS (volume boost, voz separada), todo con TDD.

### Concrete Deliverables
- Phase 1: .env seguro, CORS restringido, CSP configurado, dead code eliminado, Gemini TTS arreglado, session_state propagado, double broadcasts eliminados, brake wear con flag
- Phase 2: Spotter con estados (clear/detected/still_there), hold your line, three wide, closing speed, gap frequency, parámetros UI, TTS volume boost, voz separada

### Definition of Done
- [ ] `ruff check backend/src/` — 0 errores
- [ ] `pytest backend/tests/` — todos pasando
- [ ] `bun test frontend/` — todos pasando
- [ ] `cargo check` (Windows) — compila
- [ ] `npx tsc --noEmit` — 0 errores
- [ ] `git ls-files backend/.env` — vacío (eliminado del tracking)
- [ ] Phase 2: Spotter state machine verificado con simulación de telemetría

### Must Have
- Phase 1: Eliminar .env de git, CORS restrictivo, CSP configurado, shell:allow-execute eliminado
- Phase 1: session_state propagado a evaluate_cycle, double broadcasts eliminados
- Phase 1: Dead code removido (appStore.ts, usePTT.ts, imports muertos)
- Phase 1: Gemini TTS con import correcto
- Phase 2: Spotter state machine con estados clear/car/still_there
- Phase 2: "Three wide" detection cuando hay coches a ambos lados
- Phase 2: "Hold your line" para overlap parcial
- Phase 2: Closing speed detection
- Phase 2: Parámetros spotter configurables en UI
- Phase 2: TTS volume boost configurable
- Phase 2: Voz separada spotter vs chief
- TDD: Cada tarea tiene su RED test antes del GREEN implementation

### Must NOT Have (Guardrails)
- NO implementar speech recognition
- NO cambiar protocolo WebSocket existente
- NO refactorizar funciones con CC ≥ 11 (solo bug fixes mínimos)
- NO cambiar shared-strategy/ o sidecar/ sin evidencia de necesidad
- NO cambiar idioma del spotter (español siempre)
- NO usar LLM para toggles del spotter (comandos directos)
- NO modificar mensajes existentes del spotter (solo añadir nuevos)
- NO reescribir frontend entero

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** — ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: SI (pytest + Vitest)
- **Automated tests**: TDD completo
- **Framework**: pytest + pytest-cov (backend), Vitest (frontend)
- **TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Security fixes**: Bash commands (git, grep, ruff)
- **Backend Python**: pytest + curl for API tests
- **Frontend TS**: Vitest + tsc --noEmit
- **Rust**: cargo check
- **Spotter**: Python scripts with simulated telemetry dicts
- **TTS**: curl GET /tts?text=... + verify response

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — Phase 1 Security + Config):
├── 1. Remove .env from git tracking [quick]
├── 2. Restrict CORS to specific origins [quick]
├── 3. Set CSP policy in Tauri [quick]
├── 4. Remove shell:allow-execute [quick]
├── 5. Remove dead store appStore.ts + orphan tests [quick]
├── 6. Remove dead hook usePTT.ts [quick]
├── 7. Fix Gemini TTS import bug [quick]

Wave 2 (Phase 1 — Behavioral Bugs + Dead Imports):
├── 8. Fix session_state not passed to evaluate_cycle [unspecified-high]
├── 9. Fix double interruption broadcasts on preemption [unspecified-high]
├── 10. Fix try-except-pass silent errors [quick]
├── 11. Run ruff auto-fix for dead imports + lint errors [quick]
├── 12. Fix Rust default_window_icon unwrap [quick]

Wave 3 (Phase 1 — Test Infrastructure + Brake Wear):
├── 13. Fix brake wear hardcoded to 0.0 + add available flag [deep]
├── 14. Create missing conftest.py for shared-telemetry [quick]
├── 15. Add TDD tests for engine.py (session_state, double broadcast) [unspecified-high]
├── 16. Add TDD tests for spotter.py [unspecified-high]
├── 17. Verify Phase 1 complete (ruff, pytest, cargo, tsc) [quick]

Wave 4 (Phase 2 — Spotter Parity Core):
├── 18. Benchmark existing spotter latency [quick]
├── 19. TDD: Spotter state machine (clear → car → still_there → clear) [deep]
├── 20. TDD: "Hold your line" detection (partial overlap) [deep]
├── 21. TDD: "Three wide" detection (both sides simultaneously) [deep]
├── 22. TDD: Closing speed detection [unspecified-high]
├── 23. TDD: Configurable spotter params + gap frequency [unspecified-high]

Wave 5 (Phase 2 — UI Config + TTS Parity):
├── 24. Add spotter param fields to backend config [quick]
├── 25. Add spotter param fields to frontend Zustand store [quick]
├── 26. Build ConfigTab UI for spotter params [visual-engineering]
├── 27. TDD: TTS volume boost configurable [unspecified-high]
├── 28. TDD: Separate spotter voice selection [unspecified-high]
├── 29. Full regression: Phase 1 tests + Phase 2 tests [quick]

Wave FINAL (Verification):
├── F1. Plan compliance audit (oracle)
├── F2. Code quality review (unspecified-high)
├── F3. Real manual QA (unspecified-high)
├── F4. Scope fidelity check (deep)
```

### Dependency Matrix
- 1-7: independent — Wave 1 start
- 8: 5,6 (dead code cleanup first) — Wave 2
- 9: 8 (same module) — Wave 2
- 10: 5,6 — Wave 2
- 11: 10 (fixes first) — Wave 2
- 12: independent — Wave 2
- 13: 10 (lint fixes) — Wave 3
- 14: 11 — Wave 3
- 15: 8,9 (bugs fixed) — Wave 3
- 16: 10 (try-except fixed) — Wave 3
- 17: 1-16 — Wave 3
- 18: 17 (Phase 1 done) — Wave 4
- 19: 16 (spotter tests exist) — Wave 4
- 20: 19 (state machine) — Wave 4
- 21: 19 — Wave 4
- 22: 19 — Wave 4
- 23: 19 — Wave 4
- 24: 17 — Wave 5
- 25: 24 — Wave 5
- 26: 25 — Wave 5
- 27: 24 (backend config) — Wave 5
- 28: 24 — Wave 5
- 29: 19-28 — Wave 5

### Agent Dispatch Summary
- **Wave 1** (7 tasks): T1-T7 → `quick`
- **Wave 2** (5 tasks): T8-T9 → `unspecified-high`, T10-T12 → `quick`
- **Wave 3** (5 tasks): T13 → `deep`, T14 → `quick`, T15-T16 → `unspecified-high`, T17 → `quick`
- **Wave 4** (6 tasks): T18 → `quick`, T19-T21 → `deep`, T22-T23 → `unspecified-high`
- **Wave 5** (6 tasks): T24-T25 → `quick`, T26 → `visual-engineering`, T27-T28 → `unspecified-high`, T29 → `quick`
- **Final** (4 tasks): F1 → `oracle`, F2-F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

### Wave 1: Phase 1 — Security + Config (7 tareas paralelas)

- [ ] 1. **Remove .env from git tracking + create .env.example**

  **What to do**:
  - `git rm --cached backend/.env` para eliminar del tracking
  - Crear `backend/.env.example` con todas las keys documentadas (valores placeholder)
  - Añadir `backend/.env` al `.gitignore` raíz si no está ya (verificar `# .env` comment)
  - Añadir entrada en `.gitignore` con `backend/.env` específico
  - Verificar que `git ls-files backend/.env` devuelve vacío
  - TDD: Crear test que verifica que `.env` no está trackeado

  **Must NOT do**:
  - NO incluir API keys reales en `.env.example`
  - NO borrar el `.env` físico (solo del tracking de git)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed (git + file operations)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-7)

  **References**:
  - `backend/.env` — archivo a des-trackear
  - `.gitignore` raíz — donde añadir la entrada

  **Acceptance Criteria**:
  - [ ] `git ls-files backend/.env` → vacío
  - [ ] `backend/.env.example` existe con placeholder values
  - [ ] `.gitignore` contiene `backend/.env`
  - [ ] `pytest` pasa sin cambios en tests existentes

  **Commit**: YES
  - Message: `fix(security): remove .env from git tracking, create .env.example`
  - Files: `.gitignore`, `backend/.env.example`
  - Pre-commit: `git ls-files backend/.env` must be empty

- [ ] 2. **Restrict CORS to specific origins**

  **What to do**:
  - En `backend/src/main.py:260-271`, cambiar `allow_methods=["*"]` a `["GET", "POST"]`
  - Cambiar `allow_origins=["*"]` a `[settings.FRONTEND_ORIGIN]` o la IP del frontend
  - Añadir `FRONTEND_ORIGIN` al modelo `Settings` en `config.py`
  - TDD: Test que verifica OPTIONS request con origen válido recibe CORS headers
  - TDD: Test que verifica OPTIONS request con origen inválido es rechazado
  - TDD: Test que verifica `allow_methods` ya no incluye `*`

  **Must NOT do**:
  - NO romper el health check endpoint (test_health.py debe seguir pasando)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-7)

  **References**:
  - `backend/src/main.py:260-271` — CORS middleware config
  - `backend/src/config.py` — Settings class
  - `backend/tests/test_health.py` — health endpoint test

  **Acceptance Criteria**:
  - [ ] `ruff check backend/src/` — 0 errors
  - [ ] `pytest backend/tests/` — health tests pass
  - [ ] curl OPTIONS request with valid origin → `Access-Control-Allow-Origin` header presente
  - [ ] curl OPTIONS request with invalid origin → 403 o sin CORS headers

  **Commit**: YES (with Task 1 if same commit)
  - Pre-commit: `pytest backend/tests/test_health.py`

- [ ] 3. **Set CSP policy in Tauri config**

  **What to do**:
  - En `frontend/src-tauri/tauri.conf.json`, cambiar `"csp": null` a una política mínima
  - Política sugerida: `"default-src 'self'; connect-src 'self' ws://localhost:* http://localhost:*; script-src 'self'; style-src 'self' 'unsafe-inline'"`
  - TDD: Test que verifica `csp` ya no es `null` (grep en tauri.conf.json)

  **Must NOT do**:
  - NO usar `'unsafe-eval'` a menos que sea estrictamente necesario
  - NO bloquear conexiones WebSocket necesarias

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-2, 4-7)

  **References**:
  - `frontend/src-tauri/tauri.conf.json:28` — CSP field

  **Acceptance Criteria**:
  - [ ] `grep '"csp"' frontend/src-tauri/tauri.conf.json` → muestra `"csp": "default-src..."`
  - [ ] `cargo check` (Windows) compila

  **Commit**: YES
  - Pre-commit: `cargo check` (Windows)

- [ ] 4. **Remove shell:allow-execute from capabilities**

  **What to do**:
  - En `frontend/src-tauri/capabilities/default.json`, eliminar `"shell:allow-execute"`
  - Mantener `"shell:allow-spawn"` si existe para sidecars
  - TDD: Test que verifica `shell:allow-execute` NO está en permisos

  **Must NOT do**:
  - NO eliminar `shell:allow-spawn` (necesario para lanzar sidecars)
  - NO romper funcionalidad de spawn de backend/sidecar

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-7)

  **References**:
  - `frontend/src-tauri/capabilities/default.json`

  **Acceptance Criteria**:
  - [ ] `grep 'shell:allow-execute'` en capabilities → 0 matches
  - [ ] `cargo check` (Windows) compila

  **Commit**: YES
  - Pre-commit: `cargo check` (Windows)

- [ ] 5. **Remove dead store appStore.ts + orphan tests**

  **What to do**:
  - Eliminar `frontend/src/store/appStore.ts` (no importado por ningún código)
  - Eliminar `frontend/src/__tests__/appStore.test.ts` (testea store muerta)
  - Verificar que ningún archivo importa de `./store/appStore` o `../store/appStore`
  - TDD: Verificar que `grep -r "store/appStore" frontend/src/` devuelve 0 (excepto el test eliminado)

  **Must NOT do**:
  - NO eliminar `store/config.ts` (el store real)
  - NO mover los tests de appStore.test.ts a configStore.test.ts (ya existen 20 tests)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6-7)

  **References**:
  - `frontend/src/store/appStore.ts` — dead store
  - `frontend/src/__tests__/appStore.test.ts` — orphan tests
  - `frontend/src/store/config.ts` — real store (keep)

  **Acceptance Criteria**:
  - [ ] `grep -r "store/appStore" frontend/src/` → 0 matches
  - [ ] `npx vitest run` — tests still pass (configStore tests intact)
  - [ ] `npx tsc --noEmit` — 0 errors

  **Commit**: YES
  - Pre-commit: `npx vitest run frontend/src/__tests__/configStore.test.ts`

- [ ] 6. **Remove dead hook usePTT.ts**

  **What to do**:
  - Eliminar `frontend/src/hooks/usePTT.ts` (no importado por ningún código activo)
  - Verificar que ningún archivo importa `usePTT` o `./usePTT`
  - TDD: Verificar que `grep -r "usePTT" frontend/src/` devuelve 0 (excepto readme/docs)

  **Must NOT do**:
  - NO eliminar `useAudioCapture.ts` (el hook activo para captura de audio)
  - NO eliminar `App.tsx` inline PTT logic (la implementación activa)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-5, 7)

  **References**:
  - `frontend/src/hooks/usePTT.ts` — dead hook
  - `frontend/src/hooks/useAudioCapture.ts` — active hook
  - `frontend/src/App.tsx` — inline PTT logic (active)

  **Acceptance Criteria**:
  - [ ] `grep -r "usePTT" frontend/src/ --include="*.ts" --include="*.tsx"` → 0 matches
  - [ ] `npx tsc --noEmit` — 0 errors

  **Commit**: YES (with Task 5)

- [ ] 7. **Fix Gemini TTS import bug**

  **What to do**:
  - En `backend/src/services/gemini_tts_service.py`, reemplazar import a nivel de módulo `from google.genai import types` con lazy import DENTRO del método `_get_client()`
  - Estructura: `try: import google.genai; self._client = google.genai.Client(api_key=self.api_key); except ImportError: logger.error(...); return None`
  - TDD: Test que importa gemini_tts_service SIN google.genai instalado → no crashea
  - TDD: Test que importa gemini_tts_service SIN GEMINI_API_KEY → no crashea

  **Must NOT do**:
  - NO cambiar la lógica de fallback del TTS router
  - NO eliminar la funcionalidad Gemini TTS existente

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-6)

  **References**:
  - `backend/src/services/gemini_tts_service.py:5-6` — import bug
  - `backend/src/services/gemini_tts_service.py:32` — `_get_client()` method
  - `backend/src/main.py:196` — pattern de try/except para google.genai

  **Acceptance Criteria**:
  - [ ] `import google.genai` NO está a nivel de módulo en gemini_tts_service.py
  - [ ] `python -c "from src.services.gemini_tts_service import GeminiTTSService"` sin google-genai instalado → no crashea
  - [ ] `ruff check backend/src/services/gemini_tts_service.py` — 0 errors

  **Commit**: YES
  - Pre-commit: `pytest backend/tests/ -k tts`

### Wave 2: Phase 1 — Behavioral Bugs + Dead Imports (5 tareas)

- [ ] 8. **Fix session_state not passed to evaluate_cycle**

  **What to do**:
  - En `backend/src/routers/websocket.py:strategy_sender_loop()`, modificar la llamada a `engine.evaluate_cycle(frame, advice)` para pasar también `session_state`
  - En `backend/src/intelligence/engine.py:evaluate_cycle()`, asegurar que `session_state` se propaga correctamente a `_to_dict()` y a la construcción de `session_dict`
  - TDD RED: Escribir test que mockea evaluate_cycle y verifica que session_state llega con los campos esperados
  - TDD GREEN: Implementar el pase de session_state
  - TDD REFACTOR: Verificar que los tests existentes siguen pasando

  **Must NOT do**:
  - NO cambiar la firma de evaluate_cycle (mantener `session_state=None` como default)
  - NO modificar el flujo de pilot questions (handle_pilot_question también debe pasar session_state)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (depende de Tasks 5-6 limpieza de dead code)
  - **Blocks**: Task 9 (double broadcast fix same module)
  - **Blocked By**: None (puede empezar en Wave 2 aunque Wave 1 no haya terminado)

  **References**:
  - `backend/src/routers/websocket.py` — línea donde se llama evaluate_cycle
  - `backend/src/intelligence/engine.py:188` — signature de evaluate_cycle
  - `backend/src/intelligence/engine.py:572-575` — handle_pilot_question session_state

  **Acceptance Criteria**:
  - [ ] Test verifica que session_state se pasa con `phase`, `weather_forecast`, `finish_criteria`
  - [ ] Test verifica que evaluate_cycle con `session_state=None` funciona (backward compat)
  - [ ] `pytest backend/tests/ -k engine` — todos pasan

  **Commit**: YES
  - Message: `fix(engine): propagate session_state to evaluate_cycle`

- [ ] 9. **Fix double interruption broadcasts on LLM preemption**

  **What to do**:
  - En `backend/src/intelligence/engine.py`, hay DOS lugares que envían mensajes de interrupción cuando se cancela un LLM:
    1. `cancel_current_llm()` (líneas 505-542) — envía AdviceEndMessage + AlertMessage
    2. `_run_llm_stream()` (líneas 399-419) — al atrapar CancelledError, TAMBIÉN envía los mismos mensajes
  - Solución: Añadir un flag `_cancel_broadcast_sent: bool` en el engine. cancel_current_llm() lo pone a True al enviar. _run_llm_stream() lo checkea antes de enviar duplicados.
  - TDD RED: Test que verifica que al preempt, solo se envía 1 AdviceEndMessage y 1 AlertMessage
  - TDD GREEN: Implementar flag de guardia
  - TDD REFACTOR: Verificar tests de preemption existentes

  **Must NOT do**:
  - NO eliminar el manejo de CancelledError en _run_llm_stream (necesario por si cancel_current_llm falla)
  - NO cambiar el flujo de cancelación normal

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocks**: Task 15 (test de engine)
  - **Blocked By**: Task 8 (mismo módulo engine.py)

  **References**:
  - `backend/src/intelligence/engine.py:505-542` — cancel_current_llm
  - `backend/src/intelligence/engine.py:399-419` — _run_llm_stream CancelledError handler
  - `backend/tests/test_engine.py` o test_preemption — tests existentes

  **Acceptance Criteria**:
  - [ ] Test de preemption cuenta mensajes: exactamente 1 AdviceEndMessage + 1 AlertMessage
  - [ ] Test de cancelación normal (sin preemption) sigue funcionando
  - [ ] `pytest backend/tests/ -k preempt` — pasa

  **Commit**: YES (with Task 8)
  - Pre-commit: `pytest backend/tests/ -k engine`

- [ ] 10. **Fix try-except-pass silent errors + add logging**

  **What to do**:
  - En `backend/src/intelligence/engine.py`, reemplazar los 4 `try-except-pass` con `try-except: logger.warning(...)`
    - Línea 130: weather_data falla → log "Weather data unavailable"
    - Línea 162: priority lookup → log "Priority lookup failed"
    - Línea 219: description lookup → log "Description lookup failed"
    - Línea 429: cancel cleanup → log "Cancel cleanup failed" (este es intencional, añadir log pero no cambiar flujo)
  - En `backend/src/intelligence/spotter.py:28`: evaluate_tick → log "Spotter tick evaluation failed"
  - NO cambiar el comportamiento (seguir con `pass` o `continue`), solo añadir logging
  - TDD: Mockear logger y verificar que se llama `logger.warning()` en los casos de error

  **Must NOT do**:
  - NO cambiar el flujo de control (seguir con pass/continue después del log)
  - NO añadir logging excesivo en hot paths (20Hz de spotter)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 8-9 si no tocan las mismas líneas exactas)
  - **Blocks**: Task 11 (ruff fix) mejor después de este
  - **Blocked By**: Tasks 5-6 (dead code cleanup)

  **References**:
  - `backend/src/intelligence/engine.py:130,162,219,429` — try-except-pass
  - `backend/src/intelligence/spotter.py:28` — try-except-pass en evaluate_tick

  **Acceptance Criteria**:
  - [ ] `grep -n "except.*:.*pass" backend/src/intelligence/engine.py backend/src/intelligence/spotter.py` → 0 matches (con logging añadido)
  - [ ] Test mockea logger y verifica `logger.warning` llamado
  - [ ] `pytest backend/tests/ -k spotter` — pasa

  **Commit**: YES (with Tasks 8-9)
  - Pre-commit: `pytest backend/tests/ -k spotter`

- [ ] 11. **Run ruff auto-fix for dead imports + lint errors**

  **What to do**:
  - Ejecutar `ruff check backend/src/ --select F401,F841 --fix` para imports muertos
  - Ejecutar `ruff check backend/src/ --fix` para el resto de errores (E402, F811, etc.)
  - Verificar manualmente que no se eliminaron imports necesarios (e.g., imports usados solo para type hints)
  - Verificar que `ruff check backend/src/ --quiet` da 0 errores
  - TDD: Test de regresión que verifica `ruff check backend/src/` da 0 errores

  **Must NOT do**:
  - NO eliminar imports necesarios para type hints (añadir `from __future__ import annotations` si es necesario)
  - NO modificar archivos frontend (solo backend)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Blocked By**: Task 10 (para evitar conflictos de modificación)

  **References**:
  - findings.md línea 68-79 — lista de 17 imports muertos
  - `backend/src/intelligence/engine.py:5` — `Dict`, `List` imports
  - `backend/src/services/gemini_tts_service.py:6` — `SpeechConfig`, `PrebuiltVoiceConfig`

  **Acceptance Criteria**:
  - [ ] `ruff check backend/src/ --select F401,F841 --quiet` → 0 matches
  - [ ] `ruff check backend/src/ --quiet` → 0 errores
  - [ ] `pytest backend/tests/` — todos pasan (no se eliminó nada necesario)

  **Commit**: YES (con Tasks 8-10, batch "quality fixes")
  - Pre-commit: `ruff check backend/src/ --quiet && pytest backend/tests/`

- [ ] 12. **Fix Rust default_window_icon unwrap**

  **What to do**:
  - En `frontend/src-tauri/src/main.rs:155`, cambiar `.unwrap()` por manejo de `Option`
  - Usar `unwrap_or_else(|| default_icon())` con un icono por defecto inline
  - Si no hay icono por defecto disponible, usar `if let Some(icon) = ...` y saltar el seteo
  - TDD: Verificar que `grep '\.unwrap()' main.rs` ya no muestra línea 155
  - TDD: Verificar que `cargo check` compila (Windows)

  **Must NOT do**:
  - NO cambiar la estructura del Tauri App
  - NO eliminar la funcionalidad de icono

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed (Rust)

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (con Tasks 8-11)

  **References**:
  - `frontend/src-tauri/src/main.rs:155` — `default_window_icon().unwrap()`

  **Acceptance Criteria**:
  - [ ] `grep '\.unwrap()' frontend/src-tauri/src/main.rs` — no muestra línea 155 (o es otro unwrap aceptable)
  - [ ] `cargo check` (Windows) — compila sin errores

  **Commit**: YES
  - Message: `fix(rust): handle default_window_icon None with fallback`
  - Pre-commit: `cargo check` (Windows)

### Wave 3: Phase 1 — Test Infrastructure + Brake Wear (5 tareas)

- [ ] 13. **Fix brake wear hardcoded to 0.0 + add available flag**

  **What to do**:
  - En `backend/src/intelligence/context_builder.py:58`, el default `brake_wear = [0, 0, 0, 0]` es silenciosamente incorrecto
  - Añadir un campo `brake_wear_available: bool` al contexto
  - Si el LMU REST API no devuelve datos de frenos, marcar como no disponible
  - Las estrategias downstream (shared-strategy) deben checkear `brake_wear_available` antes de usar brake_wear
  - TDD RED: Test que verifica que sin datos LMU, brake_wear_available=False
  - TDD GREEN: Implementar flag + propagación
  - TDD REFACTOR: Verificar que strategy sigue funcionando sin brake data

  **Must NOT do**:
  - NO inventar datos de frenos (es mejor saber que no están disponibles que tener datos falsos)
  - NO modificar shared-strategy/ o sidecar/

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None needed
  - **Note**: Requiere entender flujo de datos LMU REST API → context_builder → strategy

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Task 14)
  - **Blocked By**: Task 11 (ruff fixes applied first)

  **References**:
  - `backend/src/intelligence/context_builder.py:58` — brake_wear default
  - `backend/src/services/lmu_api.py` — LMU REST API (origen de datos)

  **Acceptance Criteria**:
  - [ ] Test: context_builder sin datos LMU → `brake_wear_available=False`
  - [ ] Test: context_builder con datos LMU mock → `brake_wear_available=True`
  - [ ] `pytest backend/tests/ -k context` — pasa

  **Commit**: YES
  - Message: `fix(strategy): add brake_wear_available flag, handle zero-wear gracefully`

- [ ] 14. **Create missing conftest.py for shared-telemetry tests**

  **What to do**:
  - Crear `shared-telemetry/tests/conftest.py` con las factory functions necesarias:
    - `make_lmu_object_out()` — crea un mock de LMUObjectOut
    - `make_scoring_info()` — crea un mock de LMUScoringInfo
    - `make_vehicle_scoring()` — crea un mock de LMUVehicleScoring
    - `make_vehicle_telemetry()` — crea un mock de LMUVehicleTelemetry
  - Basarse en las estructuras de `shared-telemetry/shared_telemetry/pyLMUSharedMemory/lmu_data.py`
  - TDD RED: Verificar que los tests existentes fallan sin conftest
  - TDD GREEN: Crear conftest.py con las factory functions
  - TDD REFACTOR: Verificar que tests pasan

  **Must NOT do**:
  - NO modificar los test files existentes (solo crear el conftest faltante)
  - NO añadir fixtures complejas que no se necesiten

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Task 13)
  - **Blocked By**: Task 11

  **References**:
  - `shared-telemetry/tests/test_telemetry_reader.py:11-16` — imports que esperan conftest
  - `shared-telemetry/shared_telemetry/pyLMUSharedMemory/lmu_data.py` — estructuras ctypes
  - `shared-telemetry/shared_telemetry/pyLMUSharedMemory/lmu_enum.py` — enums

  **Acceptance Criteria**:
  - [ ] `shared-telemetry/tests/conftest.py` existe
  - [ ] `cd shared-telemetry && pip install -e . && pytest tests/ -v` — tests pasan
  - [ ] Las 4 factory functions existen y generan objetos válidos

  **Commit**: YES
  - Message: `test(telemetry): add conftest fixtures for shared-telemetry tests`

- [ ] 15. **Add TDD tests for engine.py (session_state, double broadcast)**

  **What to do**:
  - Escribir tests TDD para los bugs corregidos en Tasks 8 y 9:
    - `test_evaluate_cycle_with_session_state()` — verifica que session_state se pasa correctamente
    - `test_evaluate_cycle_without_session_state()` — verifica backward compat
    - `test_preemption_sends_single_interruption()` — verifica que solo 1 mensaje de interrupción se envía
  - Usar mocking de WebSocket broadcast para contar mensajes
  - TDD RED: Tests fallan (bugs aún sin fix)
  - TDD GREEN: Tests pasan (después de Tasks 8-9)
  - TDD REFACTOR: Verificar cobertura

  **Must NOT do**:
  - NO modificar engine.py (ya modificado en Tasks 8-9)
  - NO añadir dependencias externas

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 13-14, 16)
  - **Blocked By**: Tasks 8-9 (bugs deben estar fixeados para que tests pasen)

  **References**:
  - `backend/src/intelligence/engine.py` — código bajo test
  - `backend/tests/test_engine.py` — tests existentes (si existe)
  - `backend/tests/conftest.py` — fixtures compartidas

  **Acceptance Criteria**:
  - [ ] `test_evaluate_cycle_with_session_state` — verifica propagación
  - [ ] `test_preemption_sends_single_interruption` — verifica no duplicados
  - [ ] `pytest backend/tests/ -k engine —cov=src/intelligence/engine.py` — coverage ≥ 70%

  **Commit**: YES
  - Message: `test(engine): add TDD tests for session_state and preemption`

- [ ] 16. **Add TDD tests for spotter.py (all 8 detection categories)**

  **What to do**:
  - Añadir tests TDD para cada una de las 8 categorías de detección del spotter:
    1. Pit limiter enter/exit
    2. Gap ahead/behind
    3. Damage detection
    4. Lateral proximity (car left/right)
    5. Safety car / FCY
    6. Last lap
    7. Fuel critical
    8. Qualifying silence mode
  - Usar simulated telemetry dicts (mismo patrón que test_spotter.py existente)
  - TDD RED: Tests escritos primero
  - TDD GREEN: Verificar que pasan con implementación actual

  **Must NOT do**:
  - NO modificar spotter.py (tests deben pasar con código actual)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 13-15)
  - **Blocked By**: Task 10 (try-except fix en spotter.py)

  **References**:
  - `backend/src/intelligence/spotter.py` — código bajo test
  - `backend/tests/test_spotter.py` — tests existentes
  - `backend/tests/test_spotter_wave2.py` — tests existentes

  **Acceptance Criteria**:
  - [ ] Cada categoría tiene al menos 1 test TDD
  - [ ] `pytest backend/tests/ -k spotter --cov=src/intelligence/spotter.py` — coverage ≥ 90%

  **Commit**: YES
  - Message: `test(spotter): add TDD tests covering all 8 detection categories`

- [ ] 17. **Verify Phase 1 complete (ruff, pytest, cargo, tsc)**

  **What to do**:
  - Ejecutar suite completa de verificación:
    ```bash
    cd backend && ruff check src/ --quiet
    cd backend && pytest tests/ --cov=src/ --cov-fail-under=70
    cd frontend && npx vitest run
    cd frontend && npx tsc --noEmit
    cd frontend/src-tauri && cargo check
    git ls-files backend/.env
    grep -r "shell:allow-execute" frontend/src-tauri/capabilities/
    ```
  - Documentar resultados en `.omo/evidence/phase1-verification.txt`
  - Si algún paso falla, crear issue y referenciar a la tarea correspondiente

  **Must NOT do**:
  - NO modificar código en esta tarea (solo verificar)
  - NO ignorar fallos — cada fallo debe tener una tarea asignada

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Tasks 1-16

  **Acceptance Criteria**:
  - [ ] `ruff check backend/src/ --quiet` → 0 errores
  - [ ] `pytest backend/tests/` → todos pasan
  - [ ] `npx vitest run` → todos pasan
  - [ ] `npx tsc --noEmit` → 0 errores
  - [ ] `cargo check` (Windows) → compila
  - [ ] `git ls-files backend/.env` → vacío
  - [ ] Resultados guardados en `.omo/evidence/phase1-verification.txt`

  **Commit**: YES
  - Message: `chore(quality): Phase 1 verification complete`
  - Files: `.omo/evidence/phase1-verification.txt`

### Wave 4: Phase 2 — Spotter Parity Core (6 tareas)

- [ ] 18. **Benchmark existing spotter latency**

  **What to do**:
  - Ejecutar `python scripts/benchmark_spotter.py` (si existe) o crear benchmark inline
  - Medir: tiempo de `evaluate()` con 0, 10, 20, 50 competitors simulados
  - Medir: throughput (llamadas/segundo) con diferentes configuraciones
  - Guardar baseline en `.omo/evidence/spotter-baseline-{timestamp}.json`
  - TDD: Test que verifica que evaluate() se ejecuta en < 1ms con 20 competitors

  **Must NOT do**:
  - NO modificar spotter.py (solo medir baseline antes de cambios)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 19-23 siendo TDD)
  - **Blocked By**: Task 17 (Phase 1 verification complete)

  **References**:
  - `scripts/benchmark_spotter.py` — benchmark existente
  - `backend/src/intelligence/spotter.py` — código a benchmarkear

  **Acceptance Criteria**:
  - [ ] Benchmark produce resultados para 0, 10, 20, 50 competitors
  - [ ] Resultados guardados en `.omo/evidence/spotter-baseline-*.json`
  - [ ] evaluate() con 20 competitors < 1ms

  **Commit**: YES
  - Message: `bench(spotter): baseline latency measurement`
  - Files: `.omo/evidence/spotter-baseline-*.json`

- [ ] 19. **TDD: Spotter state machine (clear → car → still_there → clear)**

  **What to do**:
  - Implementar una state machine para el spotter con 3 estados:
    - `CLEAR` — ningún coche al lado (estado inicial)
    - `CAR_DETECTED` — coche detectado al lado, mensaje "Coche a la izquierda/derecha"
    - `STILL_THERE` — coche sigue al lado después de `overlap_delay` segundos
  - Transiciones:
    - `CLEAR` → `CAR_DETECTED`: proximidad detectada → emitir alerta
    - `CAR_DETECTED` → `STILL_THERE`: coche sigue al lado tras `overlap_delay` → "Todavía al lado"
    - `STILL_THERE` → `CLEAR`: coche se va → emitir "Clear" / "Vía libre"
    - `CAR_DETECTED` → `CLEAR`: coche se va antes del overlap_delay → "Clear" inmediato
  - TDD RED: Escribir tests para cada transición
  - TDD GREEN: Implementar SpotterStateMachine class
  - TDD REFACTOR: Integrar con SpotterService existente

  **Must NOT do**:
  - NO modificar la API pública de SpotterService
  - NO añadir dependencias externas
  - NO cambiar mensajes existentes en español

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO (bloquea Tasks 20-23)
  - **Blocks**: Tasks 20, 21, 22, 23 (dependen del state machine)
  - **Blocked By**: Task 18 (benchmark) si se quiere baseline

  **References**:
  - `backend/src/intelligence/spotter.py` — SpotterService a extender
  - `backend/src/intelligence/spotter_geometry.py` — detect_lateral_proximity
  - `backend/tests/test_spotter.py` — tests existentes

  **Acceptance Criteria**:
  - [ ] Test: CLEAR → CAR_DETECTED (proximity detectada)
  - [ ] Test: CAR_DETECTED → STILL_THERE (tras overlap_delay)
  - [ ] Test: STILL_THERE → CLEAR (coche se va)
  - [ ] Test: CAR_DETECTED → CLEAR (coche se va rápido)
  - [ ] Test: overlap_delay configurable
  - [ ] Test: clear_delay configurable (evitar flickering)
  - [ ] `pytest backend/tests/ -k spotter_state` — pasa
  - [ ] Latency overhead < 0.1ms (comparado con baseline)

  **Commit**: YES
  - Message: `feat(spotter): add state machine for clear/car/still_there transitions`

- [ ] 20. **TDD: "Hold your line" detection (partial overlap)**

  **What to do**:
  - Implementar detección de "hold your line": cuando un coche está parcialmente al lado (overlap < 50% del car length) pero no lo suficiente para adelantar
  - Usar el state machine de Task 19 + detección de overlap fraccional
  - Cuando `lateral_m < threshold` y `distance_m < car_length * 0.5` → "Mantén tu línea, coche a la [side]"
  - TDD RED: Test que verifica overlap parcial → mensaje de hold
  - TDD GREEN: Implementar en spotter_geometry.py
  - TDD REFACTOR: Integrar con state machine

  **Must NOT do**:
  - NO cambiar mensajes existentes
  - NO añadir dependencias

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Task 19

  **References**:
  - `backend/src/intelligence/spotter_geometry.py` — detect_lateral_proximity
  - `backend/src/intelligence/spotter.py` — SpotterService

  **Acceptance Criteria**:
  - [ ] Test: overlap parcial < 50% → "Mantén tu línea..."
  - [ ] Test: overlap completo ≥ 50% → mensaje normal "Coche a la..."
  - [ ] Test: sin overlap → no hay mensaje
  - [ ] Test: car_length configurable afecta detección

  **Commit**: YES
  - Message: `feat(spotter): add hold-your-line detection for partial overlap`

- [ ] 21. **TDD: "Three wide" detection (both sides simultaneously)**

  **What to do**:
  - Modificar `_eval_proximity()` en spotter.py para devolver TODOS los hits dentro del threshold (no solo el closest)
  - Si hay hits en BOTH `izquierda` y `derecha` simultáneamente → emitir "Tres en paralelo"
  - El state machine debe manejar "three wide" como un estado especial
  - TDD RED: Test con 2 competitors a ambos lados → "Tres en paralelo"
  - TDD GREEN: Implementar detección multi-hit
  - TDD REFACTOR: Verificar que single-side sigue funcionando

  **Must NOT do**:
  - NO eliminar funcionalidad single-side existente
  - NO añadir dependencias

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Task 19

  **References**:
  - `backend/src/intelligence/spotter.py:213-255` — _eval_proximity (solo closest hit)
  - `backend/src/intelligence/spotter_geometry.py:60-105` — detect_lateral_proximity

  **Acceptance Criteria**:
  - [ ] Test: 2 competitors, left + right → "Tres en paralelo"
  - [ ] Test: 1 competitor, solo left → "Coche a la izquierda"
  - [ ] Test: 1 competitor, solo right → "Coche a la derecha"
  - [ ] Test: 0 competitors → sin mensaje

  **Commit**: YES
  - Message: `feat(spotter): add three-wide detection (both sides)`

- [ ] 22. **TDD: Closing speed detection**

  **What to do**:
  - En `spotter_geometry.py`, calcular velocidad relativa entre player y competitor
  - Si `competitor.speed - player.speed > threshold` (e.g., 5 m/s) y está cerrándose → añadir "cerrándose rápido"
  - Mensaje: "Coche cerrándose rápido por la [side]"
  - TDD RED: Test que verifica closing speed → mensaje con advertencia
  - TDD GREEN: Implementar en detect_lateral_proximity o función separada
  - TDD REFACTOR: Verificar mensajes normales sin closing speed

  **Must NOT do**:
  - NO cambiar el comportamiento para competitors que no se cierran rápido
  - NO usar LLM para esto — puramente determinista

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Task 19 (state machine)

  **References**:
  - `backend/src/intelligence/spotter_geometry.py` — detect_lateral_proximity
  - `shared-strategy/src/shared_strategy/models.py` — TelemetryFrame (tiene campos de velocidad)

  **Acceptance Criteria**:
  - [ ] Test: competitor 10 m/s más rápido cerrándose → mensaje con "cerrándose rápido"
  - [ ] Test: competitor misma velocidad → mensaje normal
  - [ ] Test: threshold configurable

  **Commit**: YES
  - Message: `feat(spotter): add closing speed detection`

- [ ] 23. **TDD: Configurable spotter params + gap frequency**

  **What to do**:
  - Añadir parámetros configurables al SpotterService:
    - `car_length: float` (default 5.0m)
    - `overlap_delay: float` (default 2.0s) — tiempo para transición CAR_DETECTED→STILL_THERE
    - `clear_delay: float` (default 1.0s) — tiempo antes de emitir "clear"
    - `gap_frequency: float` (default 5.0s) — mínimo intervalo entre reportes de gap
    - `closing_speed_threshold: float` (default 5.0 m/s)
  - Añadir cooldown por categoría: `_last_alert_time: dict[str, float]` para evitar spam
  - TDD RED: Test que verifica cada parámetro afecta el comportamiento
  - TDD GREEN: Implementar parámetros + cooldown
  - TDD REFACTOR: Verificar backward compat

  **Must NOT do**:
  - NO cambiar default values que rompan comportamiento existente
  - NO añadir dependencias

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Task 19

  **References**:
  - `backend/src/intelligence/spotter.py` — SpotterService.__init__ params
  - `backend/src/config.py` — settings patron

  **Acceptance Criteria**:
  - [ ] Test: overlap_delay=5s → espera 5s antes de "still there"
  - [ ] Test: clear_delay=2s → espera 2s antes de "clear"
  - [ ] Test: gap_frequency=10s → gaps reportados cada 10s máximo
  - [ ] Test: closing_speed_threshold=20 → solo alerta si diff > 20 m/s
  - [ ] Test: default values = comportamiento actual

  **Commit**: YES
  - Message: `feat(spotter): add configurable gap frequency and spotter params`

### Wave 5: Phase 2 — UI Config + TTS Parity (6 tareas)

- [ ] 24. **Add spotter param fields to backend config**

  **What to do**:
  - En `backend/src/config.py`, anadir al modelo `Settings`:
    - `SPOTTER_CAR_LENGTH: float = 5.0`
    - `SPOTTER_OVERLAP_DELAY: float = 2.0`
    - `SPOTTER_CLEAR_DELAY: float = 1.0`
    - `SPOTTER_GAP_FREQUENCY: float = 5.0`
    - `SPOTTER_CLOSING_SPEED_THRESHOLD: float = 5.0`
    - `TTS_VOLUME_BOOST: float = 2.0` (default de CrewChiefV4)
    - `SPOTTER_VOICE: str = ""` (vacio = usar voz por defecto)
  - Asegurar que estos settings se leen de `.env` y tienen defaults
  - TDD: Test que verifica que los nuevos settings existen y tienen valores correctos

  **Must NOT do**:
  - NO cambiar settings existentes
  - NO romper carga de .env

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 25-28)
  - **Blocks**: Tasks 25, 26, 27, 28
  - **Blocked By**: Task 17 (Phase 1 complete)

  **References**:
  - `backend/src/config.py` — Settings class existente

  **Acceptance Criteria**:
  - [ ] `Settings().SPOTTER_CAR_LENGTH == 5.0`
  - [ ] `Settings().TTS_VOLUME_BOOST == 2.0`
  - [ ] `Settings().SPOTTER_VOICE == ""`
  - [ ] Todos los settings se pueden sobreescribir via .env

  **Commit**: YES
  - Message: `feat(config): add spotter parameters to backend settings`

- [ ] 25. **Add spotter param fields to frontend Zustand store**

  **What to do**:
  - En `frontend/src/store/config.ts`, anadir al tipo `AppConfig`:
    - `spotterCarLength: number`
    - `spotterOverlapDelay: number`
    - `spotterClearDelay: number`
    - `spotterGapFrequency: number`
    - `spotterClosingSpeedThreshold: number`
    - `ttsVolumeBoost: number`
    - `spotterVoice: string`
  - Valores default: mismos que backend
  - Asegurar que `loadSavedConfig()` los incluye y `saveConfig()` los serializa
  - TDD: Test que verifica los nuevos campos en estado inicial

  **Must NOT do**:
  - NO romper config existente (loadSavedConfig debe manejar migracion)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Task 24)
  - **Blocked By**: Task 24 (para consistencia de nombres)

  **References**:
  - `frontend/src/store/config.ts` — AppConfig, useAppStore

  **Acceptance Criteria**:
  - [ ] `AppConfig` tiene los 7 nuevos campos
  - [ ] `loadSavedConfig()` preserva config existente sin los nuevos campos
  - [ ] `npx tsc --noEmit` — 0 errores
  - [ ] `npx vitest run` — tests pasan

  **Commit**: YES
  - Message: `feat(config): add spotter params to frontend Zustand store`

- [ ] 26. **Build ConfigTab UI for spotter params**

  **What to do**:
  - En `frontend/src/components/ConfigTab.tsx`, anadir seccion "Spotter" con sliders/inputs:
    - `Car length (m)`: slider 2.0 - 10.0, step 0.5
    - `Overlap delay (s)`: slider 0.5 - 10.0, step 0.5
    - `Clear delay (s)`: slider 0.5 - 5.0, step 0.5
    - `Gap frequency (s)`: slider 1.0 - 30.0, step 1.0
    - `Closing speed threshold (m/s)`: slider 1.0 - 20.0, step 1.0
  - Conectar cada slider al store (useAppStore)
  - Los cambios deben enviarse al backend via WebSocket `config_update`
  - TDD: Test que verifica renderizado de los sliders

  **Must NOT do**:
  - NO eliminar configuraciones existentes en ConfigTab
  - NO cambiar estilo de componentes existentes

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: `frontend-responsive-design-standards` (para UI consistente)

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 24-25, 27-28)
  - **Blocked By**: Task 25 (store config)

  **References**:
  - `frontend/src/components/ConfigTab.tsx` — UI existente
  - `frontend/src/store/config.ts` — store

  **Acceptance Criteria**:
  - [ ] Seccion "Spotter" visible en ConfigTab
  - [ ] 5 sliders funcionales que actualizan el store
  - [ ] Cambios se envian al backend via WebSocket
  - [ ] `npx tsc --noEmit` — 0 errores

  **Commit**: YES
  - Message: `feat(ui): build spotter config UI in ConfigTab`

- [ ] 27. **TDD: TTS volume boost configurable**

  **What to do**:
  - En el frontend (`audioQueue.ts` o `useWebSocket.ts`), aplicar volume boost al crear el Audio element
  - `audio.volume = Math.min(1.0, config.ttsVolumeBoost * 0.5)` (normalizado)
  - TDD RED: Test que verifica que volumen cambia segun ttsVolumeBoost
  - TDD GREEN: Implementar en frontend
  - TDD REFACTOR: Verificar que LMU ducking sigue funcionando

  **Must NOT do**:
  - NO saturar el audio (volume > 1.0 debe ser capped)
  - NO modificar el pipeline de TTS backend (hacerlo en frontend)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 24-26)
  - **Blocked By**: Task 24 (config backend)

  **References**:
  - `frontend/src/services/audioQueue.ts` — Audio element creation
  - `frontend/src/store/config.ts` — ttsVolumeBoost field

  **Acceptance Criteria**:
  - [ ] Test: ttsVolumeBoost=2.0 -> audio.volume = min(1.0, 2.0*0.5) = 1.0
  - [ ] Test: ttsVolumeBoost=1.0 -> audio.volume = 0.5
  - [ ] Test: ttsVolumeBoost=0.0 -> audio.volume = 0.0
  - [ ] LMU ducking no se ve afectado

  **Commit**: YES
  - Message: `feat(tts): add configurable TTS volume boost`

- [ ] 28. **TDD: Separate spotter voice selection**

  **What to do**:
  - En `frontend/src/store/config.ts`, anadir campo `spotterVoice: string`
  - En `frontend/src/components/ConfigTab.tsx`, anadir dropdown de seleccion de voz
  - Las opciones deben venir del backend: incluir en config_update
  - Alternativa simple: usar el mismo backend TTS pero con una voz diferente
  - TDD RED: Test que verifica que spotterVoice afecta la URL del TTS request
  - TDD GREEN: Implementar
  - TDD REFACTOR: Verificar backward compat

  **Must NOT do**:
  - NO complicar: mantener mismo backend TTS, solo cambiar parametro de voz
  - NO requerir voces adicionales descargables (usar las existentes)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (con Tasks 24-27)
  - **Blocked By**: Task 24 (config backend)

  **References**:
  - `frontend/src/hooks/useWebSocket.ts` — TTS fetch pipeline
  - `frontend/src/store/config.ts` — AppConfig

  **Acceptance Criteria**:
  - [ ] dropdown de seleccion de voz en ConfigTab
  - [ ] spotterVoice se envia al backend en config_update
  - [ ] Al cambiar voz, los TTS requests usan la nueva voz

  **Commit**: YES
  - Message: `feat(tts): add separate spotter voice selection`

- [ ] 29. **Full regression: Phase 1 tests + Phase 2 tests**

  **What to do**:
  - Ejecutar suite completa:
    ```bash
    cd backend && ruff check src/ --quiet && pytest tests/ --cov=src/
    cd frontend && npx vitest run && npx tsc --noEmit
    cd frontend/src-tauri && cargo check
    ```
  - Verificar que NO hay regresion en tests Phase 1 despues de Phase 2
  - Verificar benchmark de spotter no ha empeorado vs baseline (Task 18)
  - Documentar resultados en `.omo/evidence/phase2-verification.txt`
  - Si hay regresion, crear issues

  **Must NOT do**:
  - NO modificar codigo en esta tarea
  - NO ignorar regresiones

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Blocked By**: Tasks 19-28

  **Acceptance Criteria**:
  - [ ] `ruff check backend/src/ --quiet` -> 0 errores
  - [ ] `pytest backend/tests/` -> todos pasan
  - [ ] `npx vitest run` -> todos pasan
  - [ ] `npx tsc --noEmit` -> 0 errores
  - [ ] `cargo check` (Windows) -> compila
  - [ ] Spotter latency no ha empeorado > 10% vs baseline

  **Commit**: YES
  - Message: `chore(quality): Phase 2 regression verification complete`
  - Files: `.omo/evidence/phase2-verification.txt`

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `ruff check backend/src/`, `pytest backend/tests/`, `bun test frontend/`, `npx tsc --noEmit`, `cargo check` (Windows). Review all changed files for: `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Ruff [N] | Build [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration (spotter + TTS working together). Test edge cases: empty state, invalid input, rapid spotter toggles. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 1**: `fix(security): remove .env from git tracking, create .env.example`
- **Task 2**: `fix(security): restrict CORS to specific origins`
- **Task 3**: `fix(security): set CSP policy in Tauri config`
- **Task 4**: `fix(security): remove shell:allow-execute from capabilities`
- **Task 5**: `chore(cleanup): remove dead store appStore.ts`
- **Task 6**: `chore(cleanup): remove dead hook usePTT.ts`
- **Task 7**: `fix(tts): add lazy import guard for google.genai in Gemini TTS`
- **Task 8**: `fix(engine): propagate session_state to evaluate_cycle`
- **Task 9**: `fix(engine): eliminate double interruption broadcasts on preemption`
- **Task 10**: `fix(quality): add logging to silent try-except-pass blocks`
- **Task 11**: `chore(lint): auto-fix dead imports with ruff`
- **Task 12**: `fix(rust): handle default_window_icon None with fallback`
- **Task 13**: `fix(strategy): add brake_wear_available flag, handle zero-wear gracefully`
- **Task 14**: `test(telemetry): add conftest fixtures for shared-telemetry tests`
- **Task 15**: `test(engine): add TDD tests for session_state and preemption`
- **Task 16**: `test(spotter): add TDD tests covering all 8 detection categories`
- **Task 17**: `chore(quality): Phase 1 verification suite`
- **Task 18**: `bench(spotter): baseline latency measurement`
- **Task 19**: `feat(spotter): add state machine for clear/car/still_there transitions`
- **Task 20**: `feat(spotter): add hold-your-line detection for partial overlap`
- **Task 21**: `feat(spotter): add three-wide detection (both sides)`
- **Task 22**: `feat(spotter): add closing speed detection`
- **Task 23**: `feat(spotter): add configurable gap frequency + params`
- **Task 24**: `feat(config): add spotter parameters to backend settings`
- **Task 25**: `feat(config): add spotter params to frontend Zustand store`
- **Task 26**: `feat(ui): build spotter config UI in ConfigTab`
- **Task 27**: `feat(tts): add configurable TTS volume boost`
- **Task 28**: `feat(tts): add separate spotter voice selection`
- **Task 29**: `chore(quality): Phase 2 regression verification`

---

## Success Criteria

### Final Verification Commands
```bash
# Backend quality
cd backend && ruff check src/ --quiet && pytest --cov=src/ --cov-fail-under=70

# Frontend quality
cd frontend && npx vitest run && npx tsc --noEmit

# Rust
cd frontend/src-tauri && cargo check 2>&1 | Select-String -NotMatch "blocked|waiting"

# Security
git ls-files backend/.env  # must be empty
```

### Final Checklist
- [ ] Phase 1: All 12 security/quality bugs verified and fixed
- [ ] Phase 2: Spotter state machine functional (clear/car/still_there)
- [ ] Phase 2: Hold your line, three wide, closing speed implemented
- [ ] Phase 2: Spotter params configurable in UI
- [ ] Phase 2: TTS volume boost + separate voice working
- [ ] All tests passing (backend + frontend)
- [ ] No regression in existing functionality
