# Análisis Integral y Plan de Remediación — Vantare Ingeniero

> **TL;DR**: El repositorio (29,641 líneas Python + 4,814 TS/TSX + 265 Rust) tiene ~20 problemas estructurales y de calidad identificados. Este documento documenta cada hallazgo con evidencia y provee un plan de remediación priorizado. Ejecución estimada: ~40 tareas en 6 waves paralelas.

---

## Contexto

### Resumen del Proyecto
Vantare Ingeniero IA es un asistente de estrategia de carrera en tiempo real para Le Mans Ultimate (LMU). Arquitectura: Backend FastAPI asíncrono (~30 módulos), Frontend Tauri/React/TypeScript (~20 módulos), Shared Libraries Python (telemetría y estrategia), Sidecar Windows.

### Metodología de Análisis
- Escaneo manual de estructura de directorios
- Revisión de imports y dependencias entre paquetes
- Verificación de `__init__.py` en todos los paquetes Python
- Análisis de duplicación de código y datos
- Revisión de configuración CI/CD y tooling

---

## Work Objectives

### Core Objective
Sanear la estructura del repositorio para garantizar mantenibilidad a largo plazo: eliminar duplicaciones, limpiar directorios stub, estandarizar tooling, unificar planificación, y mejorar CI/CD.

### Definition of Done
- [ ] 0 directorios stub vacíos sin propósito
- [ ] Todos los paquetes Python tienen `__init__.py`
- [ ] 1 sola store de frontend (no appStore.ts + config.ts)
- [ ] 1 sola cola de audio (no audioQueue.ts + priorityAudioQueue.ts)
- [ ] 1 sola ubicación de planificación (`.omo/plans/`)
- [ ] CI ejecuta tests del sidecar
- [ ] ESLint/Prettier configurado en frontend
- [ ] `agents.md` renombrado a `AGENTS.md`
- [ ] pnpm eliminado (solo npm)
- [ ] Root libre de scripts de prueba sueltos y artefactos

### Must Have
| ID | Requisito | Evidencia |
|----|-----------|-----------|
| MH-1 | Eliminar/completar directorios stub vacíos | 5 dirs: `auth/`, `config/`, `data/`, `middleware/`, `events/` — solo `__pycache__` |
| MH-2 | Añadir `__init__.py` a paquetes que faltan | 10 paquetes sin `__init__.py` |
| MH-3 | Unificar store frontend | `appStore.ts` y `config.ts` definen interfaces paralelas |
| MH-4 | Unificar audio queue frontend | `audioQueue.ts` y `priorityAudioQueue.ts` |
| MH-5 | Unificar planificación | `plans/`, `docs/plans/`, `.planning/`, `.omo/plans/` |
| MH-6 | Sidecar en CI | CI actual solo testea backend y frontend |
| MH-7 | Limpiar raíz del repositorio | 4 test scripts, archivos sueltos, submódulos |

### Must NOT Have (Guardrails)
- NO romper imports existentes (cambios graduales con backward compat)
- NO cambiar lógica de negocio — solo estructura/organización
- NO eliminar submódulos sin verificar dependencias externas
- NO modificar `Engine.evaluate_cycle()` — solo su constructor si es necesario
- NO introducir nuevas dependencias externas

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: YES (pytest backend, vitest frontend)
- **Automated tests**: Tests-after (no TDD para refactor estructural)
- **Framework**: pytest (backend) + vitest (frontend)

### QA Policy
Cada tarea incluye escenarios de verificación concretos. Evidencia en `.omo/evidence/`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Foundation — inmediato, paralelo máximo):
├── Task 1: __init__.py en todos los paquetes Python [quick]
├── Task 2: Renombrar agents.md → AGENTS.md [quick]
├── Task 3: Eliminar directorios stub vacíos [quick]
├── Task 4: Limpiar archivos test_* de raíz [quick]
├── Task 5: Unificar planificación en .omo/plans/ [quick]
├── Task 6: Migrar pnpm → npm (eliminar pnpm-lock.yaml) [quick]
├── Task 7: Configurar ESLint + Prettier en frontend [quick]
└── Task 8: Agregar ruff al backend [quick]

Wave 2 (Refactor estructural — alto impacto):
├── Task 9: Unificar store frontend [deep]
├── Task 10: Unificar audio queue frontend [deep]
├── Task 11: Consolidar StrategyService/StrategyRunner [unspecified-high]
├── Task 12: Refactor IntelligenceEngine constructor [deep]
└── Task 13: Añadir __init__.py con exports explícitos [quick]

Wave 3 (CI/CD — integración):
├── Task 14: Sidecar tests en CI.yml [quick]
├── Task 15: Lint steps en CI [quick]
├── Task 16: Configurar ruff en CI [quick]
├── Task 17: ESLint+Prettier check en CI [quick]
└── Task 18: Coverage thresholds por proyecto [quick]

Wave 4 (Código muerto y legacy):
├── Task 19: Eliminar GROQ_API_KEY legacy [quick]
├── Task 20: Limpiar build scripts redundantes [quick]
├── Task 21: Eliminar o migrar appStore.ts [unspecified-high]
├── Task 22: Eliminar o migrar audioQueue.ts [unspecified-high]
└── Task 23: Limpiar test_edge_tts_integration.py [quick]

Wave 5 (Calidad de código):
├── Task 24: Tipar any types en frontend [unspecified-high]
├── Task 25: Separar _process_cycle() en StrategyService [deep]
├── Task 26: Consolidar safe_float/safe_str/infnan_to_zero [quick]
├── Task 27: Eliminar dependencia circular broadcaster↔websocket [deep]
└── Task 28: Unificar patrones de broadcast [unspecified-high]

Wave FINAL (Verificación — 4 revisores paralelos):
├── Task F1: Plan Compliance Audit (oracle)
├── Task F2: Build + Lint + Tests ([unspecified-high])
├── Task F3: QA completo ([unspecified-high])
└── Task F4: Scope Fidelity Check ([deep])

Waves: 5 impl + 1 final = 6 waves total
Max Concurrent: 8 (Wave 1)
Critical Path: Wave 1 → Wave 2 → Wave 3 → Wave FINAL
```

---

## TODOs

- [ ] 1. Añadir `__init__.py` a todos los paquetes Python que faltan

  **What to do**:
  - Crear `__init__.py` vacío (o con docstring y `__all__`) en:
    - `backend/src/models/`
    - `backend/src/routers/`
    - `backend/src/services/`
    - `backend/src/transport/`
  - Verificar que `backend/src/intelligence/` ya tiene `__init__.py`
  - Verificar que `backend/src/persistence/` ya tiene `__init__.py`
  - Verificar que `backend/src/debug/` ya tiene `__init__.py`
  - NO tocar paquetes vacíos (se eliminan en Task 3)

  **Must NOT do**:
  - No cambiar imports en archivos existentes
  - No alterar lógica de negocio

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Tarea repetitiva, completamente mecánica
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1 (con Tasks 2, 3, 4, 5, 6, 7, 8)

  **Acceptance Criteria**:
  - `backend/src/models/__init__.py` existe
  - `backend/src/routers/__init__.py` existe
  - `backend/src/services/__init__.py` existe
  - `backend/src/transport/__init__.py` existe

  **QA Scenarios**:
  ```
  Scenario: Verificar que __init__.py files existen
    Tool: Bash
    Preconditions: Ninguna
    Steps:
      1. Test-Path "backend/src/models/__init__.py" → True
      2. Test-Path "backend/src/routers/__init__.py" → True
      3. Test-Path "backend/src/services/__init__.py" → True
      4. Test-Path "backend/src/transport/__init__.py" → True
    Expected Result: Todos los archivos existen
    Evidence: .omo/evidence/task-1-init-files-exist.txt

  Scenario: Backend imports no se rompen
    Tool: Bash
    Preconditions: Ninguna
    Steps:
      1. cd backend && python -c "from src.main import app; print('OK')"
    Expected Result: Import exitoso
    Evidence: .omo/evidence/task-1-import-check.txt
  ```

  **Commit**: YES (grupo con 2, 3)
  - Message: `chore(package): add missing __init__.py to all python packages`

- [ ] 2. Renombrar `agents.md` → `AGENTS.md`

  **What to do**:
  - Mover `agents.md` a `AGENTS.md` (git mv)
  - Verificar que ningún archivo referencia `agents.md` en minúsculas
  - Actualizar si hay referencias

  **Must NOT do**:
  - No cambiar el contenido del archivo

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Renombre simple de archivo
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - `AGENTS.md` existe
  - `agents.md` no existe

  **QA Scenarios**:
  ```
  Scenario: Archivo renombrado correctamente
    Tool: Bash
    Steps:
      1. Test-Path "AGENTS.md" → True
      2. -not (Test-Path "agents.md") → True
    Expected Result: AGENTS.md existe, agents.md no
    Evidence: .omo/evidence/task-2-rename-ok.txt
  ```

  **Commit**: YES (grupo con 1, 3)
  - Message: `chore(package): add missing __init__.py, remove stub dirs, rename agents.md`

- [ ] 3. Eliminar directorios stub vacíos (sin código fuente)

  **What to do**:
  - Eliminar (git rm -rf) directorios que solo contienen `__pycache__/`:
    - `backend/src/auth/`
    - `backend/src/config/`
    - `backend/src/data/`
    - `backend/src/middleware/`
    - `backend/src/intelligence/events/`
    - `backend/src/services/tts_models/`
  - Verificar que no hay imports desde estos directorios
  - Si algún archivo importa desde estos paths, mover el código antes de eliminar

  **Must NOT do**:
  - No eliminar si algún archivo `.py` real depende de la ruta

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Eliminación mecánica de directorios
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - Los 6 directorios no existen (o no tienen archivos .py)

  **QA Scenarios**:
  ```
  Scenario: Verificar directorios eliminados
    Tool: Bash
    Steps:
      1. Test-Path "backend/src/auth" → False (o dir vacío sin .py)
      2. Test-Path "backend/src/config" → False
      3. Test-Path "backend/src/data" → False
      4. Test-Path "backend/src/middleware" → False
      5. Test-Path "backend/src/intelligence/events" → False
      6. Test-Path "backend/src/services/tts_models" → False (sin archivos .py)
    Expected Result: Todos los directorios stub eliminados
    Evidence: .omo/evidence/task-3-stubs-removed.txt
  ```

  **Commit**: YES (grupo con 1, 2)
  - Message: `chore(package): add missing __init__.py, remove stub dirs, rename agents.md`

- [ ] 4. Limpiar scripts de prueba y archivos sueltos de la raíz del repositorio

  **What to do**:
  - Mover a `scripts/legacy/` o eliminar:
    - `test_qwen_tts.py`
    - `test_qwen2.py`
    - `test_voxtral_gguf.py`
    - `test_voxtral.py`
    - `tmp_delete_llm_service.py`
  - Mover `debug-69c028.log` a `logs/` o eliminar
  - Mover `progress.md`, `task_plan.md` a `.omo/plans/` o archivar
  - Verificar `backend/_test_edge_tts_integration.py` — mover a `backend/tests/`

  **Must NOT do**:
  - No eliminar archivos que son referenciados desde CI o scripts
  - No eliminar `backend/qa_test_script.py` (referenciado en AGENTS.md)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Tarea mecánica de organización
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - Raíz sin test scripts sueltos
  - `scripts/legacy/` contiene los scripts movidos

  **QA Scenarios**:
  ```
  Scenario: Root limpio de test scripts
    Tool: Bash
    Steps:
      1. Get-ChildItem "test_*.py" en raíz → 0
      2. Get-ChildItem "tmp_*.py" en raíz → 0
    Expected Result: No hay scripts de prueba sueltos en raíz
    Evidence: .omo/evidence/task-4-root-clean.txt
  ```

  **Commit**: YES (grupo con 5)
  - Message: `chore(cleanup): remove root test scripts, unify plan dirs`

- [ ] 5. Unificar directorios de planificación en `.omo/plans/`

  **What to do**:
  - Mover contenido de `plans/` a `.omo/plans/` (si no está ya duplicado)
  - Mover contenido de `docs/plans/` a `.omo/plans/`
  - Mover contenido de `.planning/` a `.omo/plans/` (cada fase como subdirectorio o archivo separado)
  - Crear symlink/redirect o eliminar los directorios originales
  - Verificar `.planning/.active_plan` y migrar su referencia

  **Must NOT do**:
  - No eliminar información — solo consolidar
  - No mover archivos de planificación que sean referenciados por herramientas activas

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Consolidación mecánica de archivos
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - Todo el contenido de planificación reside bajo `.omo/plans/`
  - `plans/`, `docs/plans/` eliminados o vacíos

  **QA Scenarios**:
  ```
  Scenario: Unificación de planificación verificada
    Tool: Bash
    Preconditions: Ninguna
    Steps:
      1. Test-Path ".omo/plans/" → True
      2. Get-ChildItem ".omo/plans/*.md" -Recurse | Measure-Object | Select-Object Count > 0
      3. -not (Test-Path "plans/") → True (o dir vacío)
    Expected Result: Planes centralizados en .omo/plans/
    Evidence: .omo/evidence/task-5-plans-unified.txt
  ```

  **Commit**: YES (grupo con 4)
  - Message: `chore(cleanup): remove root test scripts, unify plan dirs`

- [ ] 6. Estandarizar en npm — eliminar `pnpm-lock.yaml` y config

  **What to do**:
  - Verificar que `frontend/package-lock.json` está actualizado
  - Eliminar `frontend/pnpm-lock.yaml`
  - Eliminar `frontend/pnpm-workspace.yaml` si existe
  - Verificar que `npm install` funciona correctamente

  **Must NOT do**:
  - No cambiar `package.json` scripts ni dependencias

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Eliminación simple de archivos redundantes
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - `pnpm-lock.yaml` eliminado
  - `pnpm-workspace.yaml` eliminado
  - `npm ci` funciona en frontend/

  **QA Scenarios**:
  ```
  Scenario: pnpm files eliminados
    Tool: Bash
    Steps:
      1. -not (Test-Path "frontend/pnpm-lock.yaml") → True
      2. -not (Test-Path "frontend/pnpm-workspace.yaml") → True

  Scenario: npm install funciona
    Tool: Bash
    Preconditions: package-lock.json existe y es válido
    Steps:
      1. cd frontend && npm ci --no-audit --no-fund 2>&1
    Expected Result: npm install exitoso
    Evidence: .omo/evidence/task-6-npm-works.txt
  ```

  **Commit**: YES
  - Message: `chore(frontend): standardize on npm, remove pnpm artifacts`

- [ ] 7. Configurar ESLint + Prettier en frontend

  **What to do**:
  - Crear `frontend/.eslintrc.cjs` con configuración para TypeScript + React
  - Crear `frontend/.prettierrc` con reglas básicas
  - Añadir scripts en `frontend/package.json`:
    - `"lint": "eslint src/"`
    - `"lint:fix": "eslint src/ --fix"`
    - `"format": "prettier --write src/"`
  - Correr lint inicial y corrige errores auto-fixables

  **Must NOT do**:
  - No cambiar reglas que requieran refactors mayores (usar `warn` no `error`)
  - No añadir plugins que requieran instalación extra no incluida

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuración de tooling estándar
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - `.eslintrc.cjs` existe con configuración válida
  - `.prettierrc` existe
  - `npm run lint` se ejecuta sin errores (puede tener warnings)

  **QA Scenarios**:
  ```
  Scenario: ESLint configurado y ejecutable
    Tool: Bash
    Steps:
      1. cd frontend && npm run lint 2>&1
    Expected Result: Lint se ejecuta (puede reportar warnings)
    Evidence: .omo/evidence/task-7-eslint-works.txt

  Scenario: Prettier configurado
    Tool: Bash
    Steps:
      1. Test-Path "frontend/.prettierrc" → True
    Expected Result: Prettier config file existe
    Evidence: .omo/evidence/task-7-prettier-config.txt
  ```

  **Commit**: YES (grupo con 8)
  - Message: `chore(tooling): add ESLint+Prettier config`

- [ ] 8. Configurar ruff para backend Python

  **What to do**:
  - Crear `backend/pyproject.toml` section `[tool.ruff]` si no existe
  - Configurar reglas básicas: `E`, `F`, `I` (imports), `N` (naming)
  - Añadir `[tool.ruff.lint]` con `select = ["E", "F", "I", "N"]`
  - Ignorar `__pycache__`, `build/`, `dist/`
  - Crear `backend/.ruff.toml` como alternativa si pyproject.toml está muy lleno
  - Ejecutar `ruff check backend/src/` y reportar hallazgos

  **Must NOT do**:
  - No activar reglas muy estrictas (p.ej. `D` docstrings) que generen cientos de errores
  - No modificar código automáticamente sin revisión

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Configuración de linter estándar
  - **Skills**: None needed

  **Parallelization**: YES | Wave 1

  **Acceptance Criteria**:
  - Ruff configurado en `backend/pyproject.toml` o `backend/.ruff.toml`
  - `ruff check backend/src/` se ejecuta sin crash

  **QA Scenarios**:
  ```
  Scenario: Ruff configurado correctamente
    Tool: Bash
    Steps:
      1. cd backend && ruff check src/ 2>&1
    Expected Result: Ruff ejecuta análisis (puede reportar issues)
    Evidence: .omo/evidence/task-8-ruff-works.txt
  ```

  **Commit**: YES (grupo con 7)
  - Message: `chore(tooling): add ESLint+Prettier+ruff config`

- [ ] 9. Unificar store de frontend — eliminar `appStore.ts` y consolidar tipos

  **What to do**:
  - Analizar `frontend/src/store/appStore.ts` para identificar tipos definidos allí:
    - `RadioMode` (también en `config.ts`)
    - `ConnectionStatus` (único en appStore)
    - `TelemetryData` (vs `TelemetryState` en config.ts)
    - `RadioMessage` (vs `MessageRecord` en config.ts)
    - `AppConfig` (vs `AppConfig` en config.ts — diferentes!)
    - `SpotterAlert` (único en appStore)
  - Consolidar todos los tipos en `frontend/src/store/config.ts`
  - Migrar `SpotterAlert` y `ConnectionStatus` al nuevo store
  - Verificar qué componentes importan de `appStore.ts` y actualizar imports
  - Eliminar `appStore.ts`

  **Must NOT do**:
  - Romper imports de `appStore.ts` antes de migrar todos los consumidores
  - Perder tipos definidos solo en appStore pero no en config.ts

  **Parallelization**: NO (depende de análisis de imports)
  - **Blocks**: Task 22 (eliminar appStore.ts definitivamente)
  - **Blocked By**: None (Wave 1 complete)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Requiere análisis de todos los imports y migración cuidadosa
  - **Skills**:
    - `code-review-expert`: Para identificar todos los consumidores de appStore.ts

  **Acceptance Criteria**:
  - `config.ts` contiene todos los tipos que antes estaban en `appStore.ts`
  - `appStore.ts` eliminado
  - Todos los imports actualizados

  **QA Scenarios**:
  ```
  Scenario: appStore.ts eliminado y compilación exitosa
    Tool: Bash
    Preconditions: Migración completada
    Steps:
      1. -not (Test-Path "frontend/src/store/appStore.ts") → True
      2. cd frontend && npx tsc --noEmit 2>&1
    Expected Result: Compilación TypeScript exitosa sin errores
    Evidence: .omo/evidence/task-9-store-migration.txt

  Scenario: Tipos consolidados existen en config.ts
    Tool: Bash
    Steps:
      1. Select-String "SpotterAlert" "frontend/src/store/config.ts" → match found
      2. Select-String "ConnectionStatus" "frontend/src/store/config.ts" → match found
    Expected Result: Todos los tipos migrados
    Evidence: .omo/evidence/task-9-types-consolidated.txt
  ```

  **Commit**: YES
  - Message: `refactor(frontend): unify store — remove appStore.ts, consolidate types`

- [ ] 10. Unificar colas de audio — eliminar `audioQueue.ts`

  **What to do**:
  - Analizar diferencias entre `frontend/src/services/audioQueue.ts` y `priorityAudioQueue.ts`
  - Si `priorityAudioQueue.ts` es un superconjunto con prioridades:
    - Migrar cualquier interfaz/función que solo exista en `audioQueue.ts`
    - Actualizar imports en `App.tsx` y otros consumidores
    - Eliminar `audioQueue.ts`
  - Si tienen APIs incompatibles: mantener ambas pero renombrar claramente, añadir deprecation notice

  **Must NOT do**:
  - Perder funcionalidad de `audioQueue.ts` que no exista en `priorityAudioQueue.ts` (p.ej. `setOnPlaybackChange`, `registerAudioUnlock`)

  **Parallelization**: NO (depende de análisis)
  - **Blocks**: Task 21 (eliminar código legacy)
  - **Blocked By**: None

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Comparación de APIs y migración de funcionalidad
  - **Skills**:
    - `vercel-react-best-practices`: Para estructura de servicios frontend

  **Acceptance Criteria**:
  - `priorityAudioQueue.ts` contiene toda la funcionalidad de `audioQueue.ts`
  - `audioQueue.ts` eliminado
  - Compilación TypeScript exitosa

  **QA Scenarios**:
  ```
  Scenario: audioQueue.ts eliminado, compilación exitosa
    Tool: Bash
    Steps:
      1. -not (Test-Path "frontend/src/services/audioQueue.ts") → True
      2. cd frontend && npx tsc --noEmit 2>&1
    Expected Result: Compilación exitosa
    Evidence: .omo/evidence/task-10-queue-migration.txt

  Scenario: Test suite pasa
    Tool: Bash
    Steps:
      1. cd frontend && npm test 2>&1
    Expected Result: Todos los tests de audio/colas pasan
    Evidence: .omo/evidence/task-10-tests-pass.txt
  ```

  **Commit**: YES
  - Message: `refactor(frontend): unify audio queue — remove audioQueue.ts`

- [ ] 11. Consolidar lógica de estrategia: StrategyService vs StrategyRunner

  **What to do**:
  - Comparar `backend/src/services/strategy_service.py` (StrategyService) con `sidecar/src/sidecar/strategy_runner.py` (StrategyRunner)
  - Identificar lógica duplicada (telemetry→frame mapping, fuel simulation, competitor tracking)
  - Extraer lógica común a `shared-strategy/src/shared_strategy/` como `service_helpers.py` o similar
  - Refactorizar ambos servicios para usar la lógica compartida
  - NO eliminar los servicios individuales — son wrappers de framework (FastAPI vs standalone)

  **Must NOT do**:
  - No cambiar la API pública de StrategyService ni StrategyRunner
  - No introducir dependencias de framework en shared-strategy

  **Parallelization**: NO (depende de análisis de duplicación)
  - **Blocks**: None
  - **Blocked By**: Wave 1 complete

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**:
    - `code-review-expert`: Para identificar duplicación exacta

  **Acceptance Criteria**:
  - Lógica duplicada extraída a shared-strategy
  - Ambos servicios refactorizados usan la lógica compartida
  - Tests existentes siguen pasando

  **QA Scenarios**:
  ```
  Scenario: Ambos servicios funcionan después del refactor
    Tool: Bash
    Steps:
      1. cd backend && python -c "from src.services.strategy_service import StrategyService; print('OK')"
      2. cd sidecar && python -c "from sidecar.strategy_runner import StrategyRunner; print('OK')"
    Expected Result: Ambos imports exitosos
    Evidence: .omo/evidence/task-11-strategy-imports.txt

  Scenario: Tests de estrategia pasan
    Tool: Bash
    Steps:
      1. cd shared-strategy && pytest tests/ -v 2>&1
    Expected Result: Tests de shared-strategy pasan
    Evidence: .omo/evidence/task-11-strategy-tests.txt
  ```

  **Commit**: YES
  - Message: `refactor(backend): consolidate shared strategy logic between StrategyService and StrategyRunner`

- [ ] 12. Refactorizar constructor de IntelligenceEngine

  **What to do**:
  - Extraer las 6 resoluciones lazy del constructor (`__init__` líneas 44-96) a métodos separados
  - Crear `_resolve_live_context()`, `_resolve_context_builder()`, `_resolve_prompt_templates()`, `_resolve_llm_client()`, `_resolve_broadcaster()`, `_resolve_lmu_api()`
  - Simplificar `__init__` a solo asignación directa de parámetros + llamadas a métodos resolve
  - Reducir de 11 parámetros a parámetros esenciales (los que realmente se inyectan desde tests)

  **Must NOT do**:
  - No cambiar la lógica de `evaluate_cycle()` ni `_run_llm_stream()`
  - No cambiar la firma pública de métodos existentes

  **Parallelization**: NO (depende de entender el constructor)
  - **Blocks**: None
  - **Blocked By**: Wave 1 complete

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Refactor cuidadoso de constructor core con side effects
  - **Skills**:
    - `receiving-code-review`: Para verificar corrección

  **Acceptance Criteria**:
  - Constructor de IntelligenceEngine simplificado (≤6 params directos)
  - Tests de engine.py existentes siguen pasando
  - Ninguna resolución lazy se ejecuta en `__init__` si no es necesaria

  **QA Scenarios**:
  ```
  Scenario: IntelligenceEngine importa correctamente
    Tool: Bash
    Steps:
      1. cd backend && python -c "from src.intelligence.engine import IntelligenceEngine; print('OK')"
    Expected Result: Import exitoso

  Scenario: Tests de engine pasan
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_engine.py -v 2>&1
    Expected Result: Tests de engine pasan
    Evidence: .omo/evidence/task-12-engine-tests.txt
  ```

  **Commit**: YES
  - Message: `refactor(engine): simplify IntelligenceEngine constructor with lazy resolve methods`

- [ ] 13. Añadir `__init__.py` con exports explícitos a paquetes core

  **What to do**:
  - Para los paquetes que tienen `__init__.py` pero sin exports explícitos, añadir `__all__`:
    - `backend/src/intelligence/__init__.py`
    - `backend/src/persistence/__init__.py`
    - `backend/src/debug/__init__.py`
  - Para los nuevos `__init__.py` creados en Task 1, añadir docstring y `__all__` con los símbolos principales
  - NO mover código — solo declarar exports

  **Must NOT do**:
  - No refactorizar imports inline que ya existen

  **Parallelization**: YES | Wave 2 (con Tasks 9, 10 si fueran paralelizables)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - Cada `__init__.py` tiene `__all__` con exports explícitos
  - Backend importa correctamente

  **QA Scenarios**:
  ```
  Scenario: Backend importa con exports explícitos
    Tool: Bash
    Steps:
      1. cd backend && python -c "from src.main import app; print('OK')"
    Expected Result: Import exitoso
    Evidence: .omo/evidence/task-13-explicit-exports.txt
  ```

  **Commit**: YES
  - Message: `chore(package): add explicit exports in __init__.py files`

- [ ] 14. Agregar tests del sidecar al CI

  **What to do**:
  - En `.github/workflows/ci.yml`, añadir job `test-sidecar`:
    ```yaml
    test-sidecar:
      name: Sidecar Unit Tests
      runs-on: windows-2022
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v6
          with:
            python-version: '3.12'
        - run: pip install -e ./shared-telemetry -e ./shared-strategy -e ./sidecar[dev]
        - run: cd sidecar && python -m pytest tests/ -v
    ```
  - Añadir `[project.optional-dependencies] dev = ["pytest"]` al `sidecar/pyproject.toml` si no existe

  **Must NOT do**:
  - No modificar jobs existentes de backend/frontend

  **Parallelization**: YES | Wave 3 (con Tasks 15, 16)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - CI tiene job `test-sidecar`
  - Sidecar tests se ejecutan en CI

  **QA Scenarios**:
  ```
  Scenario: Sidecar tests ejecutables localmente
    Tool: Bash
    Steps:
      1. cd sidecar && python -m pytest tests/ -v 2>&1
    Expected Result: Tests se ejecutan (pueden fallar si falta LMU)
    Evidence: .omo/evidence/task-14-sidecar-tests-local.txt
  ```

  **Commit**: YES (grupo con 15, 16)
  - Message: `ci: add sidecar tests, lint steps, coverage thresholds`

- [ ] 15. Añadir lint steps al CI

  **What to do**:
  - En `.github/workflows/ci.yml`:
    - Añadir step de ruff check al job `test-backend`
    - Añadir step de ESLint al job `test-frontend`
    - Añadir step de compileall al job `smoke-backend` (ya existe)
  - Ruff: `ruff check src/` en backend directory
  - ESLint: `npm run lint` en frontend directory

  **Must NOT do**:
  - No hacer que el lint falle el CI si hay warnings (solo errores)

  **Parallelization**: YES | Wave 3

  **Acceptance Criteria**:
  - CI ejecuta ruff en backend
  - CI ejecuta ESLint en frontend

  **QA Scenarios**:
  ```
  Scenario: CI workflow syntax check
    Tool: Bash
    Steps:
      1. python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"
    Expected Result: YAML es válido
    Evidence: .omo/evidence/task-15-ci-yaml-valid.txt
  ```

  **Commit**: YES (grupo con 14, 16)
  - Message: `ci: add sidecar tests, lint steps, coverage thresholds`

- [ ] 16. Configurar coverage thresholds por proyecto

  **What to do**:
  - En `backend/pyproject.toml`, añadir `[tool.coverage.report] fail_under = 70`
  - Verificar que `--cov-fail-under=70` en CI.yml es consistente
  - Para sidecar, si no tiene coverage config, añadirlo

  **Must NOT do**:
  - No cambiar thresholds existentes sin justificación

  **Parallelization**: YES | Wave 3

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - Coverage config existe en pyproject.toml
  - CI usa la misma configuración

  **Commit**: YES (grupo con 14, 15)

- [ ] 17. Eliminar configuración legacy de Groq API

  **What to do**:
  - En `backend/src/config.py`:
    - Eliminar campos `CROFAI_API_KEY` y `CROFAI_BASE_URL` (marcados DEPRECATED)
    - Eliminar campos `GROQ_API_KEY` y `GROQ_MODEL` (legacy)
  - Buscar referencias a estos campos en el código:
    - `src/routers/llm.py` — verificar endpoint /ask
    - Cualquier otro archivo que use `settings.GROQ_*` o `settings.CROFAI_*`
  - Actualizar imports según corresponda

  **Must NOT do**:
  - No eliminar `settings.LLM_API_KEY`, `settings.LLM_BASE_URL`, `settings.LLM_MODEL` (activos)
  - No romper el endpoint /ask si aún usa Groq

  **Parallelization**: YES | Wave 4 (con Tasks 18, 19, 23)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `settings.CROFAI_API_KEY` ya no existe
  - `settings.CROFAI_BASE_URL` ya no existe
  - Backend importa y funciona

  **QA Scenarios**:
  ```
  Scenario: Config legacy eliminada
    Tool: Bash
    Steps:
      1. Select-String "CROFAI" "backend/src/config.py" → -1 (no match)
      2. Select-String "GROQ_API_KEY" "backend/src/config.py" → -1 (no match si no se usa)
    Expected Result: No hay referencias a config legacy
    Evidence: .omo/evidence/task-17-legacy-config.txt
  ```

  **Commit**: YES (grupo con 18, 19, 23)
  - Message: `chore: remove deprecated Groq/CrofAI legacy config`

- [ ] 18. Limpiar build scripts redundantes

  **What to do**:
  - Analizar scripts de build en backend/:
    - `backend/build.py`
    - `backend/build_backend.py`
    - `backend/launch_tauri.py`
    - `backend/run_dev.py`
    - `backend/run_dev.bat`
  - Identificar cuál es el activo vs legacy
  - Eliminar o renombrar scripts duplicados
  - Documentar en `backend/README.md` qué script usar

  **Must NOT do**:
  - No eliminar scripts que son referenciados desde CI o documentación

  **Parallelization**: YES | Wave 4

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - 1 build script principal por proyecto
  - Scripts legacy movidos a `scripts/legacy/`

  **Commit**: YES (grupo con 17, 19, 23)
  - Message: `chore: clean up redundant build scripts`

- [ ] 19. Eliminar `backend/_test_edge_tts_integration.py` o mover a tests/

  **What to do**:
  - Si el archivo es un test real, moverlo a `backend/tests/`
  - Si es un script de prueba ad-hoc, moverlo a `scripts/legacy/`
  - Verificar que no es referenciado desde ningún otro lugar

  **Parallelization**: YES | Wave 4

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `_test_edge_tts_integration.py` ya no está en `backend/`

  **Commit**: YES (grupo con 17, 18, 23)

- [ ] 20. Analizar y consolidar `spotter_adapter.py` vs lógica en `spotter.py`

  **What to do**:
  - Analizar `backend/src/intelligence/spotter_adapter.py` y su relación con `spotter.py`
  - `spotter_adapter.py` exporta `frame_to_spotter_tick()` y `resolve_spotter_input()`
  - `spotter.py` importa ambos — verificar si son wrappers innecesarios
  - Si `spotter_adapter.py` es una capa de traducción pura, mantener pero documentar
  - Si hay duplicación, consolidar

  **Must NOT do**:
  - No cambiar la lógica de detección de proximidad

  **Parallelization**: YES | Wave 4

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**:
    - `code-review-expert`: Para análisis de duplicación

  **Acceptance Criteria**:
  - Duplicación identificada y consolidada (o documentada como intencional)
  - Tests de spotter pasan

  **Commit**: YES (grupo con 21)
  - Message: `refactor(spotter): consolidate spotter_adapter into spotter service`

- [ ] 21. Migrar todos los consumidores de `appStore.ts` a `config.ts` y eliminar

  **What to do**:
  - Buscar todos los imports de `./store/appStore` o `appStore` en frontend
  - Actualizar imports a `./store/config` o `config`
  - Verificar que la API es compatible (nombres de funciones, parámetros)
  - Eliminar `frontend/src/store/appStore.ts`

  **Must NOT do**:
  - No dejar imports rotos

  **Parallelization**: NO (depende de Task 9)
  - **Blocks**: None
  - **Blocked By**: Task 9

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `appStore.ts` eliminado
  - `npx tsc --noEmit` exitoso
  - `npm test` exitoso

  **QA Scenarios**:
  ```
  Scenario: appStore.ts eliminado y build exitoso
    Tool: Bash
    Steps:
      1. -not (Test-Path "frontend/src/store/appStore.ts") → True
      2. cd frontend && npx tsc --noEmit 2>&1
    Expected Result: Build exitoso
    Evidence: .omo/evidence/task-21-appstore-removed.txt

  Scenario: Tests pasan
    Tool: Bash
    Steps:
      1. cd frontend && npm test 2>&1
    Expected Result: Tests pasan
    Evidence: .omo/evidence/task-21-tests-pass.txt
  ```

  **Commit**: YES (grupo con 22)
  - Message: `refactor(frontend): finalize store and audio queue consolidation`

- [ ] 22. Migrar todos los consumidores de `audioQueue.ts` a `priorityAudioQueue.ts` y eliminar

  **What to do**:
  - Buscar todos los imports de `./services/audioQueue` en frontend
  - Actualizar imports a `./services/priorityAudioQueue`
  - Verificar que la API es compatible (exporta `audioQueue`, `setOnPlaybackChange`, etc.)
  - Si `priorityAudioQueue` no exporta algo que `audioQueue` sí, añadirlo como wrapper
  - Eliminar `frontend/src/services/audioQueue.ts`

  **Must NOT do**:
  - No perder funcionalidad (p.ej. `registerAudioUnlock`)

  **Parallelization**: NO (depende de Task 10)
  - **Blocks**: None
  - **Blocked By**: Task 10

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `audioQueue.ts` eliminado
  - `npx tsc --noEmit` exitoso
  - `npm test` exitoso

  **Commit**: YES (grupo con 21)
  - Message: `refactor(frontend): finalize store and audio queue consolidation`

- [ ] 23. Limpiar archivos de build/artefactos de Tauri y Python

  **What to do**:
  - Mover `backend/backend.log` a `logs/` o añadir a `.gitignore` si no está
  - Mover/eliminar `frontend/test_gemini.wav` (archivo de prueba)
  - Mover/eliminar `frontend/tauri_dev_log.txt`
  - Eliminar directorios `build/`, `dist/` si no son necesarios en el repo
  - Verificar `.gitignore` para cubrir todos estos patrones

  **Must NOT do**:
  - No eliminar `backend/dist/` si es necesario para CI

  **Parallelization**: YES | Wave 4

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - Archivos temporales/buil eliminados del repo
  - `.gitignore` actualizado

  **Commit**: YES (grupo con 17, 18, 19)
  - Message: `chore: clean up build artifacts and temp files`

- [ ] 24. Tipar usos de `any` en frontend

  **What to do**:
  - En `frontend/src/App.tsx`:
    - `recognitionRef = useRef<any>(null)` → tipar como `useRef<SpeechRecognition | null>(null)`
    - `(window as any).SpeechRecognition` → definir interfaz `WindowWithSpeech`
    - `(window as any).__TAURI_INTERNALS__` → interfaz para Tauri
    - `e: any` en event handlers → tipar correctamente
  - En otros archivos del frontend, buscar y tipar `any`
  - No cubrir casos extremos — solo los usos principales

  **Must NOT do**:
  - No introducir tipos complejos que requieran librerías externas

  **Parallelization**: YES | Wave 5 (con Tasks 25, 26, 27, 28)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**:
    - `vercel-react-best-practices`: Para patrones de tipos en React

  **Acceptance Criteria**:
  - 0 usos de `any` en nuevo código
  - `npx tsc --noEmit` exitoso

  **QA Scenarios**:
  ```
  Scenario: No quedan any types en archivos modificados
    Tool: Bash
    Steps:
      1. Select-String "as any" "frontend/src/App.tsx" → count = 0 (o reducción significativa)
    Expected Result: any types reducidos/eliminados
    Evidence: .omo/evidence/task-24-any-types.txt

  Scenario: Build TypeScript exitoso
    Tool: Bash
    Steps:
      1. cd frontend && npx tsc --noEmit 2>&1
    Expected Result: Build exitoso
    Evidence: .omo/evidence/task-24-tsc-pass.txt
  ```

  **Commit**: YES (grupo con 25, 26)
  - Message: `refactor(frontend): type any usages in App.tsx and services`

- [ ] 25. Separar `_process_cycle()` en StrategyService — extraer métodos

  **What to do**:
  - `backend/src/services/strategy_service.py` — `_process_cycle()` tiene ~370 líneas
  - Extraer bloques lógicos a métodos:
    - `_resolve_session_data()` — líneas 189-196 (tipo de sesión)
    - `_extract_online_telemetry()` — líneas 223-292 (lectura shared memory)
    - `_simulate_offline_telemetry()` — líneas 294-316
    - `_compute_lap_accumulators()` — líneas 319-335
    - `_map_tyre_wear()` — líneas 338-360
    - `_map_brake_wear()` — líneas 363-392
    - `_sync_competitors()` — líneas 395-468
    - `_assemble_telemetry_frame()` — líneas 471-535
  - `_process_cycle()` debe llamar a estos métodos secuencialmente

  **Must NOT do**:
  - No cambiar la lógica interna de los bloques extraídos
  - No cambiar la API pública

  **Parallelization**: YES | Wave 5

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `_process_cycle()` < 50 líneas (solo llamadas a métodos)
  - Tests existentes pasan

  **QA Scenarios**:
  ```
  Scenario: StrategyService importa y funciona
    Tool: Bash
    Steps:
      1. cd backend && python -c "from src.services.strategy_service import StrategyService; print('OK')"
    Expected Result: Import exitoso

  Scenario: Tests de estrategia pasan
    Tool: Bash
    Steps:
      1. cd backend && python -m pytest tests/test_strategy_service.py -v 2>&1
    Expected Result: Tests pasan
    Evidence: .omo/evidence/task-25-strategy-tests.txt
  ```

  **Commit**: YES (grupo con 24, 26)
  - Message: `refactor(strategy): split _process_cycle into focused methods`

- [ ] 26. Consolidar funciones de utilidad `safe_float`/`safe_str`/`infnan_to_zero`/`bytes_to_str`

  **What to do**:
  - `shared-telemetry/shared_telemetry/reader.py` define `infnan_to_zero()` y `bytes_to_str()`
  - `backend/src/services/strategy_service.py` define `safe_float()` y `safe_str()` (misma lógica)
  - Extraer a `shared-strategy/src/shared_strategy/utils.py` o `shared-telemetry/shared_telemetry/utils.py`
  - O mejor: crear `backend/src/utils.py` con funciones compartidas y re-export
  - Actualizar imports en strategy_service.py para usar la función compartida

  **Must NOT do**:
  - No crear dependencias circulares entre shared libs

  **Parallelization**: YES | Wave 5

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `safe_float`/`infnan_to_zero` unificados en un solo lugar
  - `safe_str`/`bytes_to_str` unificados en un solo lugar
  - Todos los que usaban las versiones duplicadas ahora usan la compartida

  **QA Scenarios**:
  ```
  Scenario: Funciones unificadas, imports limpios
    Tool: Bash
    Steps:
      1. cd backend && python -c "from src.utils import safe_float; print(safe_float(3.14))"
    Expected Result: 3.14
    Evidence: .omo/evidence/task-26-utils-consolidated.txt
  ```

  **Commit**: YES (grupo con 24, 25)
  - Message: `refactor: consolidate safe_float/safe_str/bytes_to_str into shared utils`

- [ ] 27. Eliminar dependencia circular broadcaster ↔ websocket

  **What to do**:
  - Actualmente: `src/transport/broadcaster.py` importa `from src.routers.websocket import broadcast_sync`
  - Esto crea dependencia: `transport → routers`
  - Opción A: Mover `broadcast_sync()` a `transport/broadcaster.py` y que `websocket.py` lo importe desde allí
  - Opción B: Hacer que `broadcaster.py` acepte el callback en lugar de importar directamente
  - Opción C: Tener un módulo `transport/__init__.py` que centralice

  **Must NOT do**:
  - No romper los callers de `broadcast_sync()` ni `send()`

  **Parallelization**: YES | Wave 5

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `broadcaster.py` no importa de `routers/`
  - Backend importa correctamente

  **QA Scenarios**:
  ```
  Scenario: Sin imports circulares
    Tool: Bash
    Steps:
      1. cd backend && python -c "
import sys
sys.setrecursionlimit(100)
from src.transport.broadcaster import send
from src.routers.websocket import broadcast_sync
print('No circular dependency detected')
"
    Expected Result: Ambos imports exitosos
    Evidence: .omo/evidence/task-27-no-circular.txt
  ```

  **Commit**: YES
  - Message: `refactor(transport): eliminate circular dependency broadcaster ← websocket`

- [ ] 28. Unificar patrón de broadcast (broadcaster.py vs broadcast_sync inline)

  **What to do**:
  - Actualmente hay dos formas de broadcast:
    1. `from src.transport.broadcaster import send` — en llm_client.py, engine.py
    2. `from src.routers.websocket import broadcast_sync` — en main.py, engine.py
    3. `from src.transport.broadcaster import send` que a su vez llama a `broadcast_sync`
  - Estandarizar: TODO el broadcast debe pasar por `transport/broadcaster.py`
  - `broadcaster.py` debe ser el único punto de entrada para enviar mensajes al frontend
  - Actualizar imports en llm_client.py, engine.py, main.py

  **Must NOT do**:
  - No cambiar la lógica de broadcast existente

  **Parallelization**: YES | Wave 5

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: None needed

  **Acceptance Criteria**:
  - `broadcaster.send()` es la única función de broadcast
  - No hay imports directos de `broadcast_sync` desde módulos que no sean `broadcaster.py`

  **QA Scenarios**:
  ```
  Scenario: Import único de broadcast
    Tool: Bash
    Steps:
      1. grep -r "broadcast_sync" backend/src/ --include="*.py" | grep -v "broadcaster.py" | grep -v "websocket.py"
    Expected Result: Solo broadcaster.py y websocket.py referencian broadcast_sync
    Evidence: .omo/evidence/task-28-broadcast-unified.txt
  ```

  **Commit**: YES
  - Message: `refactor(transport): unify broadcast through broadcaster.py singleton`

---

## Final Verification Wave

- [ ] F1. **Plan Compliance Audit** — `oracle`

  Leer el plan completo. Por cada "Must Have" verificar que la implementación existe. Por cada "Must NOT Have" buscar patrones prohibidos. Verificar evidencia en `.omo/evidence/`.

  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Build + Lint + Tests** — `unspecified-high`

  Backend: `cd backend && python -m pytest tests/ -v --cov=src/ --cov-report=term`
  Frontend: `cd frontend && npm test && npx tsc --noEmit`
  Lint: ruff check backend/src/ (si configurado), ESLint frontend/src/ (si configurado)

  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | VERDICT`

- [ ] F3. **QA Completo** — `unspecified-high`

  Desde estado limpio, ejecutar cada escenario QA de cada tarea. Verificar integración cross-task. Guardar evidencia en `.omo/evidence/final-qa/`.

  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`

  Para cada tarea: leer "What to do", leer diff real (git log/diff). Verificar 1:1 — todo lo especificado fue construido, nada extra fue añadido. Verificar "Must NOT do" compliance.

  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

| Tareas | Mensaje | Alcance |
|--------|---------|---------|
| 1-3 | `chore(package): add missing __init__.py, remove stub dirs, rename agents.md` | backend/ |
| 4-5 | `chore(cleanup): remove root test scripts, unify plan dirs` | root, .planning/ → .omo/ |
| 6 | `chore(frontend): standardize on npm, remove pnpm-lock.yaml` | frontend/ |
| 7-8 | `chore(tooling): add ESLint+Prettier+ruff config` | frontend/, backend/ |
| 9 | `refactor(frontend): unify store — remove appStore.ts, consolidate types` | frontend/src/store/ |
| 10 | `refactor(frontend): unify audio queue — remove audioQueue.ts` | frontend/src/services/ |
| 11 | `refactor(backend): consolidate strategy services` | backend/, sidecar/ |
| 12 | `refactor(engine): simplify IntelligenceEngine constructor` | backend/src/intelligence/ |
| 14-18 | `ci: add sidecar tests, lint, coverage config` | .github/ |
| 19-23 | `chore: remove legacy code and dead files` | backend/, root |
| 24-28 | `refactor: improve code quality — types, circular deps, duplication` | backend/ |
| F1-F4 | `chore: final verification batch` | - |

---

## Success Criteria

### Verification Commands
```bash
# Backend tests
cd backend && python -m pytest tests/ -v --cov=src/ --cov-report=term

# Frontend tests
cd frontend && npm test && npx tsc --noEmit

# Lint backend
ruff check backend/src/

# Lint frontend
npx eslint frontend/src/

# Sidecar tests
cd sidecar && python -m pytest tests/ -v
```

### Final Checklist
- [ ] MH-1: 0 directorios stub vacíos
- [ ] MH-2: Todos los paquetes Python tienen `__init__.py`
- [ ] MH-3: 1 store de frontend (solo `config.ts`)
- [ ] MH-4: 1 cola de audio (solo `priorityAudioQueue.ts`)
- [ ] MH-5: 1 ubicación de planificación (`.omo/plans/`)
- [ ] MH-6: CI ejecuta sidecar tests
- [ ] MH-7: Root limpio
- [ ] `agents.md` → `AGENTS.md`
- [ ] ESLint+Prettier configurado
- [ ] ruff configurado
- [ ] Cobertura ≥70% backend
- [ ] 0 dependencias circulares
- [ ] 0 `any` types en frontend (nuevo código)
