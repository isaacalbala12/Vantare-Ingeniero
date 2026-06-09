# Plan: Evolución CrewChiefV4 — Vantare-Ingeniero

## TL;DR

> **Quick Summary**: Implementar 28 features clave de CrewChiefV4 en Vantare-Ingeniero, divididas en 3 releases autónomos. Patrón híbrido: LLM para lenguaje natural, backend para ejecución determinista. TDD + Agent QA.
>
> **Deliverables**: 3 releases funcionales independientes
> - R1: Spotter avanzado (6) + Audio/Voces (5) = 11 features (+ 3 tareas infraestructura)
> - R2: Competidores (4) + Estrategia/Pista (3) + MQTT (1) = 8 features
> - R3: Eventos adicionales (5) + Configuración (2) + SDK/Debug (2) = 9 features
>
> **Estimated Effort**: XL (28 features, 3 releases)
> **Parallel Execution**: YES — 4 waves por release
> **Critical Path**: R1 → R2 → R3 (cada release es autónomo pero secuencial)

---

## Context

### Original Request
Evolucionar Vantare-Ingeniero como evolución lógica comercial de CrewChiefV4, juntando su madurez funcional (~10 años, 450+ archivos) con LLM, RAG, y stack moderno (FastAPI+Tauri+React). Análisis feature-por-feature del documento `docs/crewchief-comparison.md`.

### Interview Summary
**Key Discussions**:
- Recorrimos todas las secciones (3.1 a 3.13) del doc de comparación
- El usuario decidió implementar 26 features y saltar 11 áreas
- Patrón híbrido: LLM para entender intención, backend para ejecución determinista
- "Spot"/"Don't spot" va por comando directo (sin LLM, <100ms)
- Pit Management (P0 en CC) se salta por ahora

**Research Findings**:
- `shared-strategy/` tiene spatial delta tracking, fuel/tyre/brake/hybrid/competitor engines
- `spotter.py` tiene 8 condiciones deterministas a 20Hz
- `IntelligenceEngine` tiene 12 triggers con prioridades
- NO existe sistema de comandos estructurados
- NO existe pit management
- El endpoint `/transcribe` es placeholder
- `lmu_api.py` solo LEE datos (polling), no escribe

### Metis Review
**Identified Gaps** (addressed):
- **26 features sin división** → 3 releases autónomos (R1, R2, R3)
- **Latencia Spot/Don't spot** → Comando directo sin LLM (<100ms)
- **Pit Management P0 saltado** → Confirmado, pospuesto
- **FlagsMonitor duplica SafetyCarTrigger** → FlagsMonitor REEMPLAZA
- **Audio ducking multiplataforma** → Solo Windows
- **Multiclase sin código existente** → Build from scratch, no extensión
- **Build from scratch vs extensiones** → Clasificado en cada tarea

---

## Work Objectives

### Core Objective
Implementar 28 features de CrewChiefV4 en Vantare-Ingeniero mediante 3 releases progresivos, usando patrón híbrido LLM+determinista y TDD.

### Concrete Deliverables
- R1: SpotterService mejorado + AudioSystem ampliado
- R2: CompetitorTracker completo + TrackSpline system + MQTT publishing
- R3: FlagsMonitor, MulticlassWarnings, DriverSwaps, Penalties, PushNow + Config profiles + Auto-update + Dummy server + Traces

### Definition of Done
- [ ] Cada release: todos los tests TDD pasan (RED → GREEN)
- [ ] Cada release: Agent QA scenarios ejecutados y evidencias capturadas
- [ ] R3 final: `bun test` + `pytest` + smoke test pasan

### Must Have
- Spotter multiclase funcional (R1)
- Audio ducking en Windows (R1)
- FlagsMonitor reemplaza SafetyCarTrigger (R3)
- TDD para toda lógica determinista
- Agent QA scenarios verificables para cada feature

### Must NOT Have (Guardrails)
- NO modificar `engine.py` cycle de triggers (solo añadir triggers)
- NO refactorizar `shared-strategy/` existente (solo extender modelos)
- NO tocar `shared-telemetry/` (excepto añadir campos si faltan)
- NO modificar protocolo WebSocket existente en `websocket.py`
- NO implementar ConditionsMonitor, FrozenOrderMonitor, AlarmClock
- NO implementar Pit Management
- NO implementar Overlays in-game/VR
- NO usar LLM para toggles de spotter (comando directo)

---

## Verification Strategy (MANDATORY)

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (Pytest backend + Vitest frontend)
- **Automated tests**: TDD (RED-GREEN-REFACTOR) para lógica determinista; tests de integración con mocks para LLM/audio/WS
- **Framework**: Pytest (backend), Vitest (frontend)
- **TDD workflow**: Cada feature → test fallido (RED) → implementación mínima (GREEN) → refactor

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Frontend/UI**: Playwright — Navigate, interact, assert DOM, screenshot
- **API/Backend**: Bash (curl) — Send requests, assert status + response fields
- **Library/Module**: Bash (python -c) — Import, call functions, compare output
- **Spotter/20Hz**: Python script with simulated telemetry frames — assert alert output
- **Audio (ducking)**: PowerShell script checking volume before/after — assert reduction
- **MQTT**: mosquitto_sub + python publisher — assert message receipt

---

## Execution Strategy

### Release Structure
```
R1 (Waves 1-4) → Spotter (6) + Audio/Voces (5) = 11 features
R2 (Waves 5-7) → Competidores (4) + Pista (3) + MQTT (1) = 8 features
R3 (Waves 8-10) → Eventos (5) + Config (2) + Debug (2) = 9 features
```

Cada release termina con su propia Final Verification Wave. El release N+1 NO empieza hasta que R1 está completamente verificado.

### Parallel Execution Waves

```
Wave 1 (Start Immediately — foundation + types + benchmarks):
├── Task 1: Benchmark spotter latencia actual
├── Task 2: Tyre dimensions + class models (Pydantic)
├── Task 3: Colloquial time formatter utility
└── Task 4: Swear words config toggle

Wave 2 (After Wave 1 — spotter core, MAX PARALLEL):
├── Task 5: Car-left/car-right XYZ detection
├── Task 6: Spotter off durante calificación
├── Task 7: Spotter multiclase
├── Task 8: Exclusión coches parados/en boxes
├── Task 9: Dimensiones reales del coche
└── Task 10: "Spot"/"Don't spot" comando directo

Wave 3 (After Wave 2 — audio, MAX PARALLEL):
├── Task 11: Audio ducking (Windows)
├── Task 12: Fuzzy matching de nombres
├── Task 13: Pearls of Wisdom (sistema dedicado)
└── Task 14: Agregar juramentos opcionales al prompt

Wave 4 (R1 Final Verification):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality + test pass (unspecified-high)
├── Task F3: Real manual QA — scenarios (unspecified-high)
└── Task F4: Scope fidelity (deep)

--- R1 COMPLETE → R2 START ---

Wave 5 (Start R2 — competitor models + track data):
├── Task 15: Competitor query models + LLM tool calls
├── Task 16: Competitor monitoring engine
├── Task 17: Multi-class competitor filtering
├── Task 18: Track vs classification distinction
└── Task 19: Track spline data structures

Wave 6 (After Wave 5 — strategy + MQTT, MAX PARALLEL):
├── Task 20: Attack/defense per corner (Spatial Delta Arrays)
├── Task 21: Corner names + landmarks system
├── Task 22: MQTT telemetry publishing
└── Task 23: Integrar competitor queries en engine + websocket

Wave 7 (R2 Final Verification):
├── Task F5: Plan compliance audit (oracle)
├── Task F6: Code quality + test pass (unspecified-high)
├── Task F7: Real manual QA — scenarios (unspecified-high)
└── Task F8: Scope fidelity (deep)

--- R2 COMPLETE → R3 START ---

Wave 8 (Start R3 — events core, MAX PARALLEL):
├── Task 24: FlagsMonitor (reemplaza SafetyCarTrigger)
├── Task 25: MulticlassWarnings engine
├── Task 26: DriverSwaps detection (endurance)
├── Task 27: Penalties monitor
└── Task 28: PushNow + SessionEndMessages

Wave 9 (After Wave 8 — config + debug, MAX PARALLEL):
├── Task 29: Sistema de perfiles de configuración
├── Task 30: Auto-update system
├── Task 31: LMU REST API dummy server
└── Task 32: Trace recording + playback system

Wave 10 (R3 Final Verification):
├── Task F9: Plan compliance audit (oracle)
├── Task F10: Code quality + full test suite (unspecified-high)
├── Task F11: Complete QA — all scenarios (unspecified-high)
└── Task F12: Scope fidelity (deep)
→ Present results → Get explicit user okay

Critical Path: Task 1 → Task 5 → Wave 2 → Wave 3 → F1-F4 → R2 → F5-F8 → R3 → F9-F12 → user okay
```

### Dependency Matrix
- **Wave 1**: 1, 2, 3, 4 — No deps (pueden empezar inmediato)
- **Wave 2**: 5, 6, 7, 8, 9, 10 — Deps: 1 (benchmark), 2 (models)
- **Wave 3**: 11, 12, 13, 14 — Deps: 2 (models for names)
- **Wave 4 (FINAL)**: F1-F4 — Deps: Waves 1-3 completas
- **Wave 5**: 15, 16, 17, 18, 19 — No deps de R1 (release autónomo)
- **Wave 6**: 20, 21, 22, 23 — Deps: 15, 19
- **Wave 7 (FINAL)**: F5-F8 — Deps: Waves 5-6 completas
- **Wave 8**: 24, 25, 26, 27, 28 — No deps de R2 (release autónomo)
- **Wave 9**: 29, 30, 31, 32 — Deps: 28 (trace playback necesita eventos)
- **Wave 10 (FINAL)**: F9-F12 — Deps: Waves 8-9 completas

---

## TODOs

### RELEASE 1 — Spotter (6) + Audio (5)

#### Wave 1: Foundation + Benchmarks + Utilities

- [ ] 1. **Benchmark spotter latencia actual**

  **What to do**:
  - Crear script de benchmark que ejecute `SpotterService.evaluate()` con 10,000 ticks de telemetría simulada
  - Medir tiempo promedio por tick, p99, throughput
  - Guardar resultado como baseline en `.omo/benchmarks/spotter-baseline.json`
  - El benchmark debe ejecutarse ANTES de cualquier cambio en spotter.py

  **Must NOT do**:
  - NO modificar spotter.py (solo leer y medir)
  - NO eliminar el benchmark después (debe ser repetible)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1, with tasks 2, 3, 4)
  - **Blocks**: Tasks 5-9 (spotter improvements depend on benchmark)

  **References**:
  - `backend/src/intelligence/spotter.py:36-148` — SpotterService.evaluate() method to benchmark
  - `shared-strategy/src/shared_strategy/models.py:TelemetryFrame` — TelemetryFrame model for simulated data

  **Acceptance Criteria**:
  - [ ] Script exists: `scripts/benchmark_spotter.py`
  - [ ] Output: `.omo/benchmarks/spotter-baseline.json` with avg_ms, p99_ms, throughput_hz

  **QA Scenarios**:
  ```
  Scenario: Benchmark runs successfully
    Tool: Bash (python)
    Preconditions: benchmark script exists, existing spotter.py unchanged
    Steps:
      1. Run `python scripts/benchmark_spotter.py --output .omo/benchmarks/spotter-baseline.json`
      2. Assert exit code 0
      3. Read output JSON
    Expected Result: avg_ms < 1.0, p99_ms < 2.0, throughput_hz > 1000
    Evidence: .omo/evidence/task-1-benchmark.json

  Scenario: Benchmark is repeatable
    Tool: Bash (python)
    Preconditions: same as above
    Steps:
      1. Run benchmark twice
      2. Compare results — variance < 10%
    Expected Result: Consistent measurements
    Evidence: .omo/evidence/task-1-repeatable.json
  ```

  **Commit**: YES (groups with tasks 2-4)
  - Message: `perf(spotter): add latency benchmark for spotter evaluation`
  - Files: `scripts/benchmark_spotter.py`
  - Pre-commit: `python scripts/benchmark_spotter.py`

- [ ] 2. **Modelos Pydantic: dimensiones neumáticos + clases**

  **What to do**:
  - Añadir a `shared-strategy/src/shared_strategy/models.py`:
    - `TyreDimensions`: width_mm, diameter_mm, compound_type (enum)
    - `CarDimensions`: width_m, length_m, wheelbase_m, tyre_data[TyreDimensions x4]
    - `VehicleClassInfo`: class_name, typical_width_m
  - Añadir lookup table básica: clase → dimensiones típicas (Hypercar=2.0m, GT3=2.05m, LMP2=1.9m)
  - El `SpotterService` debe poder recibir estas dimensiones para calcular proximidad

  **Must NOT do**:
  - NO tocar modelos existentes (RaceState, TelemetryFrame, etc.)
  - NO añadir datos de coches reales (solo tabla básica)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1, with tasks 1, 3, 4)
  - **Blocks**: Tasks 5, 7, 9 (spotter XYZ + multiclass + dimensions)

  **References**:
  - `shared-strategy/src/shared_strategy/models.py:1-233` — Existing models pattern
  - `shared-telemetry/shared_telemetry/models.py:VehicleData.class_name` — Class names from LMU

  **Acceptance Criteria**:
  - [ ] `TyreDimensions` model exists with width_mm, diameter_mm, compound_type
  - [ ] `VehicleClassInfo` has lookup: Hypercar→2.0m, GT3→2.05m
  - [ ] SpotterService accepts dimensions parameter
  - [ ] TDD: tests pass for all new models

  **QA Scenarios**:
  ```
  Scenario: Dimensions lookup works
    Tool: Bash (python)
    Preconditions: new models imported
    Steps:
      1. Run `python -c "from shared_strategy.models import VehicleClassInfo; v=VehicleClassInfo(); print(v.get_width('Hypercar'))"`
    Expected Result: 2.0
    Evidence: .omo/evidence/task-2-dimensions.json

  Scenario: Unknown class returns default
    Tool: Bash (python)
    Preconditions: same
    Steps:
      1. Query 'Unknown' class
    Expected Result: default 2.0m
    Evidence: .omo/evidence/task-2-default.json
  ```

  **Commit**: YES (groups with tasks 1-4)
  - Message: `feat(models): add tyre dimensions and vehicle class models`
  - Files: `shared-strategy/src/shared_strategy/models.py`
  - Pre-commit: `pytest shared-strategy/tests/`

- [ ] 3. **Formateador de tiempo coloquial**

  **What to do**:
  - Crear `backend/src/intelligence/time_format.py` con funciones:
    - `format_laptime(seconds, colloquial=True)` → "26.5" (sin minutos si <60s), "1:26.5" (con minutos)
    - `format_time_remaining(seconds)` → "media hora", "45 segundos", "2 horas 15 minutos"
    - `format_fuel(amount_litres)` → "26 punto 5", "ciento veinte"
  - Inspirado en `ColloquialTime.cs` de CC

  **Must NOT do**:
  - NO modificar ticker.py existente
  - NO modificar prompt_templates.py (aún)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1, with tasks 1, 2, 4)
  - **Blocks**: Task 14 (swear toggle needs time format)

  **References**:
  - `backend/src/intelligence/ticker.py:_format_time()` — Existing time format
  - `backend/src/intelligence/prompt_templates.py:SYSTEM_PROMPT_TICKER` — Where formatted text goes

  **Acceptance Criteria**:
  - [ ] `format_laptime(92.5)` → "1:32.5"
  - [ ] `format_laptime(26.5)` → "26.5"
  - [ ] `format_time_remaining(7200)` → "2 horas"
  - [ ] `format_fuel(26.5)` → "26 punto 5"
  - [ ] TDD: tests pass

  **QA Scenarios**:
  ```
  Scenario: Lap time under 60 seconds
    Tool: Bash (python)
    Steps: python -c "from backend.src.intelligence.time_format import format_laptime; print(format_laptime(26.5))"
    Expected Result: "26.5"
    Evidence: .omo/evidence/task-3-laptime-short.json

  Scenario: Lap time over 60 seconds
    Tool: Bash (python)
    Steps: python -c "from backend.src.intelligence.time_format import format_laptime; print(format_laptime(92.5))"
    Expected Result: "1:32.5"
    Evidence: .omo/evidence/task-3-laptime-long.json
  ```

  **Commit**: YES (groups with tasks 1-4)
  - Message: `feat(format): add colloquial time and fuel formatter`
  - Files: `backend/src/intelligence/time_format.py`
  - Pre-commit: `pytest backend/tests/ -k time_format`

- [ ] 4. **Toggle de juramentos opcionales**

  **What to do**:
  - Añadir propiedad `USE_SWEARY_MESSAGES` a `config.py:Settings`
  - Añadir campo `swearyMessages` al frontend config store (`config.ts`)
  - Añadir toggle en `ConfigTab.tsx` (pestaña Voz o nueva pestaña)
  - En `prompt_templates.py:SYSTEM_PROMPT_TICKER`: añadir instrucción condicional "You MAY use colorful language" o "Keep it clean"
  - En `render()`, pasar la flag para modificar el prompt

  **Must NOT do**:
  - NO añadir juramentos hardcodeados (el LLM genera naturalmente)
  - NO persistir en localStorage (se guarda con el perfil ya existente)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: none needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 1, with tasks 1, 2, 3)
  - **Blocks**: Task 14 (pearls of wisdom integration)

  **References**:
  - `backend/src/config.py:Settings` — Config pattern
  - `frontend/src/store/config.ts:AppConfig` — Config store pattern
  - `frontend/src/components/ConfigTab.tsx` — UI pattern
  - `backend/src/intelligence/prompt_templates.py:render()` — Where prompt is modified

  **Acceptance Criteria**:
  - [ ] `config.py` has USE_SWEARY_MESSAGES (default False)
  - [ ] Frontend has toggle in ConfigTab
  - [ ] Prompt changes based on toggle
  - [ ] TDD: tests verify prompt content differs

  **QA Scenarios**:
  ```
  Scenario: Non-sweary prompt generated
    Tool: Bash (python)
    Preconditions: USE_SWEARY_MESSAGES=False
    Steps: python -c "from backend.src.intelligence.prompt_templates import render; print(render({'sweary': False}, 'FAST'))"
    Expected Result: Prompt does NOT contain authorization for profanity
    Evidence: .omo/evidence/task-4-clean.json

  Scenario: Sweary prompt generated
    Tool: Bash (python)
    Preconditions: USE_SWEARY_MESSAGES=True
    Steps: python -c "from backend.src.intelligence.prompt_templates import render; print(render({'sweary': True}, 'FAST'))"
    Expected Result: Prompt contains language authorization
    Evidence: .omo/evidence/task-4-sweary.json
  ```

  **Commit**: YES (groups with tasks 1-4)
  - Message: `feat(config): add sweary messages toggle`
  - Files: `backend/src/config.py`, `frontend/src/store/config.ts`, `frontend/src/components/ConfigTab.tsx`, `backend/src/intelligence/prompt_templates.py`
  - Pre-commit: `pytest backend/ && bun test frontend/`


#### Wave 2: Spotter Core (MAX PARALLEL)

- [ ] 5. **Car-left/car-right por coordenadas XYZ**

  **What to do**:
  - Añadir nueva condición en `SpotterService.evaluate()`: detección de proximidad lateral usando `pos_x`, `pos_y`, `pos_z` del `TelemetryFrame`
  - Calcular distancia lateral entre player y cada competitor: `sqrt(dx² + dz²)` (ignorar Y para altura)
  - Si distancia lateral < umbral (configurable, default 3.0m) → emitir "car left" o "car right"
  - Determinar izquierda/derecha comparando coordenada X local (relativa al vector de dirección del player)
  - Usar `CarDimensions.typical_width_m` del modelo añadido en Task 2 para ajustar umbral
  - Añadir propiedad `SPOTTER_PROXIMITY_THRESHOLD_M` (default 3.0m)

  **Must NOT do**:
  - NO modificar condiciones existentes del spotter (solo añadir)
  - NO usar LLM para esta detección
  - NO superar 5ms por tick de evaluación

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: none needed

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2, with tasks 6, 7, 8, 9)
  - **Blocked By**: Task 1 (benchmark), Task 2 (dimensions model)

  **References**:
  - `backend/src/intelligence/spotter.py:36-148` — Pattern for adding new conditions
  - `shared-strategy/src/shared_strategy/models.py:TelemetryFrame.pos_x/y/z` — Coordinates
  - `shared-strategy/src/shared_strategy/models.py:CompetitorTelemetry` — Competitor data

  **Acceptance Criteria**:
  - [ ] New condition: lateral proximity detection
  - [ ] Returns "car left" / "car right" with direction
  - [ ] Threshold configurable via settings
  - [ ] TDD: tests with simulated positions verify left/right
  - [ ] Benchmark: avg_ms no aumenta más de 0.5ms sobre baseline

  **QA Scenarios**:
  ```
  Scenario: Car detected to the right
    Tool: Bash (python)
    Preconditions: Benchmark baseline exists
    Steps:
      1. Run python script with player at (0,0,0) facing +Z, competitor at (3,0,5)
    Expected Result: Alert with "derecha" and proximity distance
    Evidence: .omo/evidence/task-5-right.json

  Scenario: Car detected to the left
    Tool: Bash (python)
    Steps: Run with competitor at (-3,0,5)
    Expected Result: Alert with "izquierda"
    Evidence: .omo/evidence/task-5-left.json

  Scenario: No alert when car is far
    Tool: Bash (python)
    Steps: Run with competitor at (10,0,20)
    Expected Result: No alert
    Evidence: .omo/evidence/task-5-far.json
  ```

  **Commit**: YES (groups with tasks 6-9)
  - Message: `feat(spotter): add car-left/car-right XYZ proximity detection`
  - Files: `backend/src/intelligence/spotter.py`, `backend/src/config.py`
  - Pre-commit: `python scripts/benchmark_spotter.py && pytest backend/tests/ -k spotter`

- [ ] 6. **Spotter off durante calificación**

  **What to do**:
  - Añadir propiedad `SPOTTER_OFF_QUALIFYING` (default True) a `config.py:Settings`
  - En `SpotterService.evaluate()`, si está activa y `session_type == 2` (qualifying), NO emitir alertas de spotter (excepto safety car + fuel critical)
  - Añadir toggle en frontend `ConfigTab.tsx`

  **Must NOT do**:
  - NO afectar SafetyCarTrigger y FuelCriticalTrigger (siguen activos)

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2, with tasks 5, 7, 8, 9)
  - **Blocked By**: Task 1 (benchmark)

  **References**:
  - `backend/src/intelligence/spotter.py:evaluate()` — Where to add session_type check
  - `shared-telemetry/shared_telemetry/models.py:SessionData.session_type` — 2 = qualifying

  **Acceptance Criteria**:
  - [ ] Spotter off in qualifying when SPOTTER_OFF_QUALIFYING=True
  - [ ] SC + Fuel alerts still fire in qualifying
  - [ ] Frontend toggle in ConfigTab
  - [ ] TDD: tests verify spotter silence in quali, alerts in race

  **QA Scenarios**:
  ```
  Scenario: Spotter silent in qualifying
    Tool: Bash (python)
    Preconditions: SPOTTER_OFF_QUALIFYING=True, session_type=2
    Steps: Run evaluate() with gap < 0.5s condition
    Expected Result: No alert emitted
    Evidence: .omo/evidence/task-6-quali-silent.json
  ```

  **Commit**: YES (groups with tasks 5-9)
  - Message: `feat(spotter): add spotter-off-during-qualifying toggle`
  - Files: `backend/src/intelligence/spotter.py`, `backend/src/config.py`, `frontend/src/store/config.ts`, `frontend/src/components/ConfigTab.tsx`
  - Pre-commit: `pytest backend/tests/ -k spotter`

- [ ] 7. **Spotter multiclase**

  **What to do**:
  - En `SpotterService.evaluate()`, añadir filtrado por clase del vehículo
  - **Misma clase**: reportar normal (car left/right)
  - **Clase más rápida**: "Hypercar doblando por la derecha"
  - **Clase más lenta**: "GT3 adelantando por la izquierda" (estás doblando)
  - Usar `VehicleClassInfo` de Task 2 para ordenar clases por velocidad

  **Must NOT do**:
  - NO eliminar reporte genérico "car left/right" (fallback)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2, with tasks 5, 6, 8, 9)
  - **Blocked By**: Task 2 (vehicle class models)

  **References**:
  - `shared-telemetry/shared_telemetry/models.py:VehicleData.class_name` — Class name per vehicle
  - `shared-strategy/src/shared_strategy/models.py:CompetitorTelemetry.driver_class` — Class in competitor data

  **Acceptance Criteria**:
  - [ ] Spotter distinguishes same-class vs different-class proximity
  - [ ] Reports "X doblando" when faster class approaching
  - [ ] Reports "X adelantando" when lapping slower class
  - [ ] Fallback: generic "car left/right" if class unknown
  - [ ] TDD: tests with mixed classes

  **QA Scenarios**:
  ```
  Scenario: GT3 being lapped by Hypercar
    Tool: Bash (python)
    Steps: Player in GT3, Hypercar at right
    Expected Result: "Hypercar doblando por la derecha"
    Evidence: .omo/evidence/task-7-lapping.json
  ```

  **Commit**: YES (groups with tasks 5-9)
  - Message: `feat(spotter): add multiclass awareness to spotter`
  - Files: `backend/src/intelligence/spotter.py`, `shared-strategy/src/shared_strategy/models.py`
  - Pre-commit: `pytest backend/tests/ -k spotter`

- [ ] 8. **Exclusión de coches parados/en boxes**

  **What to do**:
  - En `SpotterService.evaluate()`, ignorar:
    - Competidores con `in_pits == True`
    - Competidores con `speed < 5 km/h` durante > 5s (coche parado/abandonado)
  - Añadir propiedad `SPOTTER_EXCLUDE_STOPPED` (default True)

  **Must NOT do**:
  - NO eliminar alertas de fuel/SC para coches parados

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2, with tasks 5, 6, 7, 9)
  - **Blocked By**: Task 1 (benchmark)

  **References**:
  - `shared-strategy/src/shared_strategy/models.py:CompetitorTelemetry.in_pits`
  - `shared-strategy/src/shared_strategy/models.py:TelemetryFrame.speed`

  **Acceptance Criteria**:
  - [ ] Pitted competitors excluded from spotter alerts
  - [ ] Stationary competitors (speed < 5 km/h) excluded after 5s
  - [ ] TDD: tests verify exclusion

  **QA Scenarios**:
  ```
  Scenario: Pitted competitor ignored
    Tool: Bash (python)
    Steps: competitor in_pits=True, within 2m
    Expected Result: No proximity alert
    Evidence: .omo/evidence/task-8-pit.json
  ```

  **Commit**: YES (groups with tasks 5-9)
  - Message: `feat(spotter): exclude pitted and stationary cars`
  - Files: `backend/src/intelligence/spotter.py`
  - Pre-commit: `pytest backend/tests/ -k spotter`

- [ ] 9. **Dimensiones reales del coche**

  **What to do**:
  - Enriquecer `VehicleClassInfo` con datos de dimensiones por modelo LMU
  - Lookup table: nombre_vehículo → width_m, length_m
  - Spotter usa ancho real para ajustar umbral de proximidad
  - ~20 vehículos principales de LMU

  **Must NOT do**:
  - NO requerir datos exactos 3D (ancho típico por clase es suficiente)

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2, with tasks 5, 6, 7, 8)
  - **Blocked By**: Task 2 (VehicleClassInfo model)

  **References**:
  - `shared-telemetry/shared_telemetry/models.py:VehicleData.vehicle_name`

  **Acceptance Criteria**:
  - [ ] Vehicle lookup table for 20+ LMU vehicles
  - [ ] Spotter uses per-vehicle width for threshold
  - [ ] Unknown vehicle falls back to class-average
  - [ ] TDD: tests verify threshold adjustment

  **QA Scenarios**:
  ```
  Scenario: Known vehicle returns correct width
    Tool: Bash (python)
    Steps: Query 'Ferrari 499P' width
    Expected Result: 2.0 (Hypercar width)
    Evidence: .omo/evidence/task-9-known.json
  ```

  **Commit**: YES (groups with tasks 5-9)
  - Message: `feat(spotter): add real vehicle dimensions for proximity`
  - Files: `shared-strategy/src/shared_strategy/models.py`, `backend/src/intelligence/spotter.py`
  - Pre-commit: `pytest shared-strategy/tests/`

- [ ] 10. **"Spot" / "Don't spot" — comando directo (sin LLM)**

  **What to do**:
  - En `App.tsx`, antes de enviar al LLM, detectar comandos "spot"/"don't spot"/"deja de espiar"
  - Si coincide → enviar `{event: "spotter_command", data: {action: "enable"/"disable"}}` por WebSocket
  - En `websocket.py`, handler para `spotter_command` que togglea `SpotterService.enabled`
  - Latencia objetivo: <100ms

  **Must NOT do**:
  - NO pasar por LLM (latencia inaceptable)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 2, with tasks 5, 6, 7, 8, 9)
  - **Blocked By**: Task 1 (benchmark)

  **References**:
  - `frontend/src/App.tsx:handlePTTEnd()` — Speech processing entry
  - `backend/src/routers/websocket.py:websocket_endpoint()` — WS message routing
  - `backend/src/intelligence/spotter.py:SpotterService` — Enabled flag

  **Acceptance Criteria**:
  - [ ] "Spot"/"Don't spot" recognized in frontend without LLM
  - [ ] WS message `spotter_command` sent to backend
  - [ ] Backend toggles SpotterService.enabled
  - [ ] Latency < 100ms
  - [ ] TDD: tests verify command routing

  **QA Scenarios**:
  ```
  Scenario: "Don't spot" disables spotter
    Tool: Playwright + Bash
    Steps: Simulate "don't spot" → verify spotter disabled
    Expected Result: No spotter alerts after disable
    Evidence: .omo/evidence/task-10-disable.json
  ```

  **Commit**: YES (groups with tasks 5-9)
  - Message: `feat(spotter): add spot/dont-spot direct voice command`
  - Files: `frontend/src/App.tsx`, `backend/src/routers/websocket.py`, `backend/src/intelligence/spotter.py`
  - Pre-commit: `bun test frontend/ && pytest backend/tests/ -k spotter`

#### Wave 3: Audio System (MAX PARALLEL)

- [ ] 11. **Audio ducking (Windows)**

  **What to do**:
  - En Tauri Rust, añadir comando `duck_lmu(active: bool)`:
    - `active=true`: bajar volumen de LMU a 30%
    - `active=false`: restaurar volumen original
  - Usar `winapi` crate para `IAudioEndpointVolume`
  - Integrar con `audioQueue.ts`: inicio TTS → duck, fin TTS → unduck
  - Propiedad `AUDIO_DUCK_LEVEL` (default 0.3)

  **Must NOT do**:
  - NO implementar para otras plataformas

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3, with tasks 12, 13, 14)

  **References**:
  - `frontend/src/services/audioQueue.ts` — TTS queue
  - `frontend/src-tauri/src/main.rs` — Tauri commands

  **Acceptance Criteria**:
  - [ ] Tauri command `duck_lmu` (Windows only)
  - [ ] Volume reduces to AUDIO_DUCK_LEVEL on TTS start
  - [ ] Volume restores on TTS end
  - [ ] Graceful if LMU not running
  - [ ] TDD: Rust tests + mock integration

  **QA Scenarios**:
  ```
  Scenario: Volume ducks on TTS start
    Tool: PowerShell
    Steps: Measure LMU volume before/during/after TTS
    Expected Result: 100% → 30% → 100%
    Evidence: .omo/evidence/task-11-duck.json
  ```

  **Commit**: YES (groups with tasks 11-14)
  - Message: `feat(audio): add Windows audio ducking for LMU`
  - Files: `frontend/src-tauri/src/commands.rs`, `frontend/src/services/audioQueue.ts`, `frontend/src/App.tsx`
  - Pre-commit: `bun test frontend/`

- [ ] 12. **Fuzzy matching de nombres de pilotos**

  **What to do**:
  - Crear `backend/src/intelligence/driver_names.py`:
    - `normalize_name(name)` → sin acentos, mayúsculas
    - `fuzzy_match(spoken, known, threshold=0.8)` → mejor match
    - `get_driver_by_partial(spoken, known)` → búsqueda por apellido
    - Caché por sesión

  **Must NOT do**:
  - NO requerir dependencias externas

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3, with tasks 11, 13, 14)

  **References**:
  - `shared-telemetry/shared_telemetry/models.py:VehicleData.driver_name`

  **Acceptance Criteria**:
  - [ ] `normalize_name` handles accents, case
  - [ ] `fuzzy_match("perez", ["Pérez", "Hamilton"])` → ("Pérez", >0.8)
  - [ ] `get_driver_by_partial("alonso", drivers)` → matching driver
  - [ ] TDD: tests with Spanish names

  **QA Scenarios**:
  ```
  Scenario: Accented name matched
    Tool: Bash (python)
    Steps: fuzzy_match('perez', ['Pérez', 'Hamilton'])
    Expected Result: ("Pérez", score > 0.8)
    Evidence: .omo/evidence/task-12-accent.json
  ```

  **Commit**: YES (groups with tasks 11-14)
  - Message: `feat(audio): add fuzzy driver name matching`
  - Files: `backend/src/intelligence/driver_names.py`
  - Pre-commit: `pytest backend/tests/ -k driver_names`

- [ ] 13. **Perlas de Sabiduría — sistema dedicado**

  **What to do**:
  - Crear `backend/src/intelligence/pearls_of_wisdom.py`:
    - `PearlType` enum: STANDARD, COMEBACK, FAST_LAP, OVERTAKE
    - Lista de mensajes temáticos por tipo
    - `get_pearl(event_type, context)` → mensaje contextual
    - Eventos: overtake, fast lap, position gained, good save
    - Hook en `IntelligenceEngine.evaluate_cycle()`
    - Max 2 perlas por carrera

  **Must NOT do**:
  - NO usar LLM para generar perlas (predefinidas = baja latencia)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3, with tasks 11, 12, 14)
  - **Blocked By**: Task 4 (swear toggle)

  **References**:
  - `backend/src/intelligence/engine.py:evaluate_cycle()` — Event hook

  **Acceptance Criteria**:
  - [ ] 4+ pearl types with 3+ messages each
  - [ ] Overtake → pearl fired
  - [ ] Fast lap → pearl fired
  - [ ] Max 2 per race
  - [ ] Respects sweary toggle
  - [ ] TDD: tests verify firing conditions

  **QA Scenarios**:
  ```
  Scenario: Fast lap triggers pearl
    Tool: Bash (python)
    Steps: Call on_event(FAST_LAP)
    Expected Result: Pearl message returned
    Evidence: .omo/evidence/task-13-fastlap.json
  ```

  **Commit**: YES (groups with tasks 11-14)
  - Message: `feat(audio): add dedicated pearls of wisdom system`
  - Files: `backend/src/intelligence/pearls_of_wisdom.py`, `backend/src/intelligence/engine.py`
  - Pre-commit: `pytest backend/tests/ -k pearls`

- [ ] 14. **Integrar formateo coloquial + juramentos en prompt/perlas**

  **What to do**:
  - Integrar `time_format.py` (Task 3) en `prompt_templates.py:render()`
  - TTS text usa "26.5" en vez de "1:26.5" para vueltas < 60s
  - Juramentos (Task 4) afectan perlas de sabiduría (Task 13)

  **Must NOT do**:
  - NO modificar sistema de ticker
  - NO cambiar formato JSON de telemetría

  **Recommended Agent Profile**:
  - **Category**: `quick`

  **Parallelization**:
  - **Can Run In Parallel**: YES (Wave 3, with tasks 11, 12, 13)
  - **Blocked By**: Tasks 3, 4, 13

  **Acceptance Criteria**:
  - [ ] Colloquial time used in TTS: "26.5" not "1:26.5"
  - [ ] Sweary toggle affects pearls
  - [ ] TDD: tests verify format

  **Commit**: YES (groups with tasks 11-14)
  - Message: `feat(audio): integrate colloquial time and swear toggle`
  - Files: `backend/src/intelligence/prompt_templates.py`, `backend/src/intelligence/pearls_of_wisdom.py`
  - Pre-commit: `pytest backend/tests/`


### RELEASE 2 — Competidores (4) + Pista (3) + MQTT (1)

#### Wave 5: Competitor Models + Track Data

- [ ] 15. **Modelos de consulta de competidores + tool calls LLM**

  **What to do**: Crear `CompetitorQuery/Response` Pydantic models. Añadir tool call `query_competitor` en prompt_templates. Parsear en llm_client para resolver consultas desde `CompetitorTrackerState`. Handlers: `query_by_name` (fuzzy), `query_by_position`, `query_class`.
  **Blocked By**: Task 12 (fuzzy matching), Task 2 (class models)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 16, 17, 18, 19)
  **TDD**: Tests para query resolution by name and position
  **QA**: `POST /ask "¿Qué tal va Pérez?"` → response con posición/gap/última vuelta
  **Commit**: `feat(competitors): add competitor query tool calls`

- [ ] 16. **Motor de monitoreo de competidores**

  **What to do**: Extender `competitors.py` con `start_monitoring(index)`, `stop_monitoring(index)`, `get_monitored()`. Eventos: pit entry/exit, position change, gap change. Max 3 monitored. Tool call `monitor_competitor`/`unmonitor_competitor`.
  **Blocked By**: Task 15
  **Agent**: `unspecified-high` | **Parallel**: YES (with 15, 17, 18, 19)
  **TDD**: Tests para lifecycle de monitoreo
  **QA**: `start_monitoring(5)` → driver 5 en lista. `stop_monitoring(5)` → quitado.
  **Commit**: `feat(competitors): add driver monitoring system`

- [ ] 17. **Filtrado multiclase de competidores**

  **What to do**: Añadir `filter_by_class`, `classify_gap`, `get_nearest_in_class` en competitors.py. Mejorar `_format_riv()` en ticker para mostrar clase.
  **Blocked By**: Task 2 (class models)
  **Agent**: `quick` | **Parallel**: YES (with 15, 16, 18, 19)
  **TDD**: Tests verify correct class filtering
  **QA**: Filtrar "GT3" → solo GT3 en resultados
  **Commit**: `feat(competitors): add multiclass competitor filtering`

- [ ] 18. **Distinción pista vs clasificación**

  **What to do**: Añadir `order_on_track()` (por lap_distance) y `order_in_classification()` (por standing_position). LLM puede diferenciar en respuestas. Campo `track_position` en `CompetitorPace`.
  **Blocked By**: Task 15
  **Agent**: `quick` | **Parallel**: YES (with 15, 16, 17, 19)
  **TDD**: Tests verify both orderings differ with pitted drivers
  **QA**: Comparar track order vs classification → diferentes ordenaciones
  **Commit**: `feat(competitors): add track vs classification distinction`

- [ ] 19. **Estructuras de datos de splines de pista**

  **What to do**: Crear `track_spline.py` con `TrackSplinePoint(distance, radius, banking, is_corner, name)`, `TrackSpline(points[], name)`, `TrackSplineManager(load, get_by_distance, get_nearest_corner)`. Datos para 5+ pistas LMU.
  **Blocked By**: Nothing
  **Agent**: `unspecified-low` | **Parallel**: YES (with 15, 16, 17, 18)
  **TDD**: Tests verify distance → corner name lookup
  **QA**: Query spa spline a 4500m → "Blanchimont"
  **Commit**: `feat(track): add track spline data structures`

#### Wave 6: Strategy + MQTT (MAX PARALLEL)

- [ ] 20. **Ataque/defensa por curvas con Spatial Delta Arrays**

  **What to do**: Usar SpatialDeltaArrays ya existentes (fuel, tyre, brake) para identificar curvas donde el piloto está ganando/perdiendo tiempo. `analyze_sectors(telemetry, state, track_spline)` → sectores donde atacar/defender. LLM recibe análisis como contexto.
  **Blocked By**: Task 19 (track splines)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 21, 22, 23)
  **TDD**: Tests para detección de sectores ganados/perdidos
  **QA**: Corner donde delta > 0.3s → LLM sugiere ataque/defensa
  **Commit**: `feat(strategy): add attack/defend per corner analysis`

- [ ] 21. **Nombres de curvas + landmarks**

  **What to do**: Usar `TrackSpline` (Task 19) para traducir distancias a nombres de curvas en mensajes del LLM. "Estás perdiendo tiempo en Blanchimont" en vez de "estás perdiendo tiempo en el km 4.5".
  **Blocked By**: Task 19
  **Agent**: `quick` | **Parallel**: YES (with 20, 22, 23)
  **TDD**: Tests verify distance → corner name
  **QA**: Paso 4500m → "Blanchimont"
  **Commit**: `feat(track): add corner name translation`

- [ ] 22. **Publicación MQTT de telemetría**

  **What to do**: Crear `backend/src/services/mqtt_service.py` con publicador asíncrono. Usar `paho-mqtt` o `gmqtt`. Publicar telemetría seleccionable (fuel, tyres, position, speed) a broker configurable. Propiedades: `MQTT_ENABLED`, `MQTT_BROKER`, `MQTT_PORT`, `MQTT_TOPIC`.
  **Blocked By**: Nothing (release 2 independiente)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 20, 21, 23)
  **TDD**: Tests con mock MQTT broker
  **QA**: `mosquitto_sub -t vantare/telemetry` → recibe mensajes JSON
  **Commit**: `feat(mqtt): add MQTT telemetry publishing`

- [ ] 23. **Integrar consultas de competidores en engine + websocket**

  **What to do**: Conectar Tasks 15-18 con IntelligenceEngine. El LLM puede invocar `query_competitor` tool call. Respuesta estructurada se inyecta en la conversación. WebSocket transmite respuestas de consulta.
  **Blocked By**: Tasks 15-18
  **Agent**: `unspecified-high` | **Parallel**: YES (with 20, 21, 22)
  **TDD**: End-to-end: pregunta por WS → tool call → respuesta en WS
  **QA**: WS send `pilot_question: "¿Qué tal va Pérez?"` → WS recibe respuesta con datos
  **Commit**: `feat(competitors): integrate queries in engine + websocket`

### RELEASE 3 — Eventos (5) + Config (2) + Debug (2)

#### Wave 8: Events Core (MAX PARALLEL)

- [ ] 24. **FlagsMonitor (reemplaza SafetyCarTrigger)**

  **What to do**: Crear `backend/src/intelligence/flags_monitor.py`. Monitoriza: bandera verde (race start/end), amarilla (local/full course yellow — LMU ya expone `yellow_flag_state`), roja (session stopped), azul (blue flag — coche más rápido detrás). Eliminar `SafetyCarTrigger` y reemplazar por `FlagsMonitorTrigger` que maneja todo. FCY/SC siguen siendo CRITICAL.
  **Blocked By**: Nothing (release 3 independiente)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 25, 26, 27, 28)
  **TDD**: Tests para cada tipo de bandera
  **QA**: Simular yellow flag → trigger dispara. Simular blue flag → aviso "coche más rápido detrás"
  **Commit**: `feat(events): add flags monitor, replaces safetycar trigger`

- [ ] 25. **MulticlassWarnings**

  **What to do**: Crear trigger `MulticlassWarningTrigger`. Cuando un coche de clase más rápida está < 2s detrás, avisar "Hypercar alcanzando". Cuando te acercas a clase más lenta < 1s, avisar "GT3 delante, prepárate para doblar". Integrar con spotter multiclase (Task 7).
  **Blocked By**: Task 7 (spotter multiclase), Task 17 (class filtering)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 24, 26, 27, 28)
  **TDD**: Tests verify multiclass proximity warnings
  **QA**: Hypercar 1.5s detrás de GT3 → "Hypercar alcanzando"
  **Commit**: `feat(events): add multiclass warnings`

- [ ] 26. **DriverSwaps — detección de cambios de piloto (endurance)**

  **What to do**: Detectar cuando el driver_name del player cambia (diferente piloto al volante). Disparar evento "Cambio de piloto detectado — Pilot X al volante". Resetear acumuladores de stint. Importante para 24h Le Mans.
  **Blocked By**: Task 12 (fuzzy matching para reconocer nombre)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 24, 25, 27, 28)
  **TDD**: Tests verify driver change detection
  **QA**: Simular cambio driver_name → evento + reset stint
  **Commit**: `feat(events): add driver swap detection for endurance`

- [ ] 27. **Penalties — monitor de penalizaciones**

  **What to do**: LMU expone datos de penalización. Monitorear `num_penalties` y `penalty_served`. Trigger cuando: nueva penalización asignada (drive-through, stop-and-go), penalización servida. Mensaje: "Penalización de drive-through asignada, entra en boxes para servirla".
  **Blocked By**: Nothing (datos vienen de shared-memory)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 24, 25, 26, 28)
  **TDD**: Tests verify penalty detection
  **QA**: Simular penalty count change → alerta
  **Commit**: `feat(events): add penalties monitor`

- [ ] 28. **PushNow + SessionEndMessages**

  **What to do**: `PushNow` — trigger que activa modo ataque cuando el piloto necesita presionar. Mensaje: "Modo ataque activado, dale todo". `SessionEndMessages` — trigger al final de sesión con resumen: posición final, mejores vueltas, estadísticas.
  **Blocked By**: Nothing
  **Agent**: `unspecified-low` | **Parallel**: YES (with 24, 25, 26, 27)
  **TDD**: Tests verify push now and session end triggers
  **QA**: Últimas 3 vueltas → mensaje fin de sesión
  **Commit**: `feat(events): add push now and session end messages`

#### Wave 9: Config + Debug (MAX PARALLEL)

- [ ] 29. **Sistema de perfiles de configuración**

  **What to do**: Añadir persistencia de perfiles completos (no solo config actual). Crear `backend/src/persistence/profile_store.py`: `save_profile(name, config)`, `load_profile(name)`, `list_profiles()`, `delete_profile(name)`. Frontend: selector de perfiles en ConfigTab. Perfiles incluyen: servidor, audio, spotter, triggers, MQTT, voz.
  **Blocked By**: Nothing
  **Agent**: `unspecified-high` | **Parallel**: YES (with 30, 31, 32)
  **TDD**: Tests verify profile save/load/delete/list
  **QA**: Crear perfil "endurance" → cargar → settings cambian. Eliminar → ya no listado
  **Commit**: `feat(config): add profile system`

- [ ] 30. **Auto-update system**

  **What to do**: Sistema de auto-actualización. Backend expone `GET /version`. Frontend comprueba versión contra GitHub releases. Si nueva: notificar al usuario con opción de descargar. Integrar con Tauri: abrir URL de release o descargar actualizador.
  **Blocked By**: Nothing
  **Agent**: `unspecified-high` | **Parallel**: YES (with 29, 31, 32)
  **TDD**: Tests verify version check logic
  **QA**: GET /version → versión actual. Simular nueva version → notificación
  **Commit**: `feat(config): add auto-update system`

- [ ] 31. **LMU REST API dummy server**

  **What to do**: Servidor HTTP de prueba que mockea la REST API de LMU (puerto 6397). Endpoints: `/rest/sessions/weather`, `/rest/strategy/usage`, `/rest/garage/UIScreen/RepairAndRefuel`. Devuelve datos realistas. Para desarrollo sin LMU corriendo. CC ya tiene uno similar.
  **Blocked By**: Nothing
  **Agent**: `unspecified-low` | **Parallel**: YES (with 29, 30, 32)
  **TDD**: Tests verify dummy endpoints respond correctly
  **QA**: `curl localhost:6397/rest/sessions/weather` → JSON realista
  **Commit**: `feat(debug): add LMU REST API dummy server`

- [ ] 32. **Trace recording + playback system**

  **What to do**: Grabar telemetría a disco (archivos .trace). Reproducir traces grabados para testear cambios sin LMU. Crear `backend/src/persistence/trace_store.py`: `start_recording()`, `stop_recording()`, `list_traces()`, `playback(trace_id, callback)`. Reproducción a velocidad real o 2x/5x.
  **Blocked By**: Task 28 (session end marca fin de trace)
  **Agent**: `unspecified-high` | **Parallel**: YES (with 29, 30, 31)
  **TDD**: Tests verify record → playback produces same data
  **QA**: Grabar 10 segundos de telemetría → playback reproduce exactos
  **Commit**: `feat(debug): add trace recording and playback system`


## Final Verification Wave (MANDATORY)

> 4 review agents run in PARALLEL for EACH release. ALL must APPROVE before next release starts.

### Release 1 — R1 Final Verification

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end for R1. For each "Must Have": verify implementation exists (read file, run test, execute scenario). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest backend/` + `bun test frontend/`. Review all changed files for: `as any`/`# type: ignore`, bare `except:`, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY R1 task. Test cross-task integration. Test edge cases: empty state, invalid input, rapid toggles. Save to `.omo/evidence/final-qa-r1/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each R1 task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

### Release 2 — R2 Final Verification

- [ ] F5. **Plan Compliance Audit (R2)** — `oracle`
  Same as F1 but for R2 scope.

- [ ] F6. **Code Quality Review (R2)** — `unspecified-high`
  Same as F2 but includes R1+R2 tests.

- [ ] F7. **Real Manual QA (R2)** — `unspecified-high`
  Same as F3 but for R2 scenarios + cross-R1 integration.

- [ ] F8. **Scope Fidelity Check (R2)** — `deep`
  Same as F4 but for R2 tasks.

### Release 3 — R3 Final Verification

- [ ] F9. **Plan Compliance Audit (R3)** — `oracle`
  Same as F1 but for R3 scope.

- [ ] F10. **Code Quality Review (Full)** — `unspecified-high`
  Full suite: `pytest` + `bun test`. Comprehensive code review.

- [ ] F11. **Complete QA — All Scenarios** — `unspecified-high`
  Execute ALL QA scenarios from ALL 3 releases. Focus on cross-release integration (e.g., FlagsMonitor + Spotter).

- [ ] F12. **Scope Fidelity Check (Final)** — `deep`
  Final scope check across all 3 releases.

---

## Commit Strategy

### Release 1
- **Task 1**: `perf(spotter): add latency benchmark for spotter evaluation`
- **Tasks 2-4**: `feat(spotter): add tyre dimensions, time formatter, swear toggle`
- **Tasks 5-9**: `feat(spotter): car-xyz, quali-off, multiclass, exclusion, dimensions`
- **Task 10**: `feat(spotter): add spot/dont-spot direct voice command`
- **Tasks 11-14**: `feat(audio): ducking, fuzzy names, pearls, swear toggle`

### Release 2
- **Tasks 15-18**: `feat(competitors): name queries, monitoring, multiclass, track-vs-class`
- **Tasks 19-21**: `feat(track): splines, attack/defense, corner names`
- **Task 22**: `feat(mqtt): telemetry publishing`
- **Task 23**: `feat(competitors): integrate queries in engine + websocket`

### Release 3
- **Task 24**: `feat(events): flags monitor (replaces safetycar trigger)`
- **Tasks 25-26**: `feat(events): multiclass warnings, driver swaps`
- **Task 27**: `feat(events): penalties monitor`
- **Task 28**: `feat(events): push now + session end`
- **Task 29**: `feat(config): profile system`
- **Task 30**: `feat(config): auto-update`
- **Task 31**: `feat(debug): lmu rest api dummy server`
- **Task 32**: `feat(debug): trace recording and playback`

---

## Success Criteria

### Verification Commands
```bash
# R1
pytest backend/src/intelligence/spotter.py -v  # Spotter tests pass
pytest backend/src/services/ -v                 # Audio/services tests pass
bun test frontend/                              # Frontend tests pass

# R2
pytest shared-strategy/tests/ -v                # Strategy tests pass
bun test frontend/                              # Frontend + MQTT

# R3
pytest backend/ -v                              # All backend tests
bun test frontend/                              # All frontend tests
python backend/qa_test_script.py                # Smoke test
```

### Final Checklist
- [ ] All "Must Have" for each release present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass (pytest + vitest)
- [ ] Agent QA evidence captured for every task
- [ ] All 3 releases verified
- [ ] User explicit approval obtained
