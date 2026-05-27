# Quality Analysis & Refactor Plan — 27 Mayo 2026

> Análisis exhaustivo de calidad de código para todo el proyecto Vantare Ingeniero IA.
> Cubre: Python (backend + shared + sidecar), TypeScript (frontend), Rust (Tauri).

---

## Resumen Ejecutivo

| Métrica | Valor | Δ vs baseline |
|---------|:-----:|:-------------:|
| Líneas totales | ~12,753 | — |
| Tests backend | 285 ✅ | +49 |
| Tests frontend | 55 ✅ | 0 |
| Cobertura backend | 69% | +4 pts |
| Cobertura frontend | — | — |
| Errores TypeScript | 0 | ✅ |
| Errores Ruff (src/) | 0 | ✅ |
| Errores Ruff (tests/) | 61 (F401) | ⚠️ |
| Complejidad C+ (Python) | 15 funciones | ⚠️ |
| Seguridad (S-class) | Solo tests | ✅ |
| Rust | 2 archivos, 149 líneas | ✅ |

---

## 1. Análisis Python — Backend (4,978 líneas)

### 1.1 Ruff — Linting

**src/ (producción): 0 errores.** ✅ Limpio.

**tests/ (61 errores):** Todos son `F401` (imports no usados). La mayoría en test_ws_integration.py. No bloquean, pero son ruido.

**F-strings sin placeholder (3):**
- `build_backend.py:140` — `print(f"Preparando para copiar...")` 
- `run_dev.py:41,46` — `print(f"  Vantare Ingeniero...")`

**Fix:** Quitar prefijo `f` → `print("texto")`

### 1.2 Radon — Complejidad Ciclomática

**15 funciones con grado C (11+) o superior:**

| Grado | Función | Archivo | Líneas |
|:-----:|---------|---------|:------:|
| **E (40)** | `StrategyService._process_cycle` | `strategy_service.py` | 164-247 |
| **D (30)** | `_build_ticker_data` | `context_builder.py` | 18-150 |
| **D (29)** | `IntelligenceEngine.evaluate_cycle` | `engine.py` | 118-220 |
| **D (27)** | `lifespan` | `main.py` | 57-150 |
| **D (26)** | `LiveContextManager.on_lap_completed` | `live_context.py` | 20-80 |
| **D (24)** | `VLLMClient.ask_streaming` | `llm_client.py` | 82-200 |
| **D (22)** | `websocket_endpoint` | `websocket.py` | 238-280 |
| **D (21)** | `poll_api` | `lmu_api.py` | 91-183 |
| **D (21)** | `StrategyService.get_race_summary` | `strategy_service.py` | 101-160 |
| **C (17)** | `SpotterService.evaluate` | `spotter.py` | 36-149 |
| **C (17)** | `strategy_sender_loop` | `websocket.py` | 121-185 |
| **C (14)** | `VLLMClient.ask_streaming_text` | `llm_client.py` | 206-287 |
| **C (11)** | `IntelligenceEngine._to_dict` | `engine.py` | 468-496 |
| **C (11)** | `_summarize_event` | `context_builder.py` | 289-335 |
| **C (11)** | `format_event_text` | `formatter.py` | 15-127 |

### 1.3 Análisis por Módulo

#### strategy_service.py (473 líneas) — PRIORIDAD 1
- `_process_cycle()`: **E (40)** — la función más compleja del proyecto
- Causa: 150+ líneas de lógica secuencial con 5+ bloques de validación, cálculo de fuel, tyres, brakes, hybrid, competitors, pit window, todo en una sola función
- Síntoma: mezcla de concerns (parseo de telemetría + lógica de estrategia + populado de modelos)
- **Refactor:** Extraer 5 sub-funciones: `_parse_session_info()`, `_parse_player_telemetry()`, `_parse_tyre_data()`, `_parse_competitors()`, `_compute_strategy()`

#### engine.py (496 líneas) — PRIORIDAD 2
- `evaluate_cycle()`: **D (29)** — segundo motor de lógica más complejo
- Causa: 100+ líneas con iteración de triggers, construcción de prompt, llamada LLM, manejo de ALERT_ONLY/DETERMINISTIC_ONLY/LLM_REQUIRED
- **Refactor:** Extraer `_process_llm_trigger()`, `_process_alert_trigger()`, `_process_deterministic_trigger()`

#### llm_client.py (286 líneas) — PRIORIDAD 3
- `ask_streaming()`: **D (24)** — lógica de streaming + tool_calls + errores
- `ask_streaming_text()`: **C (14)** — SSE parsing duplicado
- **Problema:** Dos implementaciones de streaming (OpenAI SDK + httpx directo) con lógica SSE similar
- **Refactor:** Extraer `_parse_sse_tokens()` como función compartida

#### context_builder.py (337 líneas) — PRIORIDAD 3
- `_build_ticker_data()`: **D (30)** — normaliza 4 fuentes de datos distintas
- 80% de cobertura (35 líneas sin cubrir)
- Líneas sin cubrir: 65-67 (fallback), 85-91 (modo legacy), 188-215 (condiciones de borde), 233, 253, 301, 319, 335
- **Refactor:** Separar normalización de cada fuente en funciones dedicadas

#### lmu_api.py (183 líneas) — PRIORIDAD 4
- `poll_api()`: **D (21)** — polling loop con 3 endpoints
- **Problema:** Cobertura 40%. Caches globales con `global` statement (línea 156)
- **Refactor:** Usar clase `CacheManager` en vez de módulo con vars globales. Tests directos de lógica de cache ya creados (24 tests).

#### live_context.py (229 líneas) — PRIORIDAD 4
- `on_lap_completed()`: **D (26)** — actualiza 6+ buffers diferentes
- **Refactor:** Extraer actualización de cada buffer en método aparte

#### spotter.py (176 líneas) — PRIORIDAD 4
- `evaluate()`: **C (17)** — 8 condiciones en cascada
- **Problema:** 88% cobertura. Líneas 23-29 sin cubrir (fallback de extracción de dict)
- **Refactor:** Cada condición podría ser un método independiente (patrón monitor, como CrewChief)

---

## 2. Análisis Python — Shared Libraries (3,597 líneas)

### 2.1 shared-telemetry (1,090 líneas)
- `reader.py` (566 líneas): Módulo más grande, posible candidato a split
- `lmu_data.py` (502 líneas): Structs C conctypes, no refactorizable
- `lmu_enum.py` (292 líneas): Enums de LMU
- **Sin tests** — solo scripts de prueba ad-hoc

### 2.2 shared-strategy (717 líneas)
- `models.py` (233 líneas): Modelos Pydantic
- `calculation.py` (174 líneas): Lógica de cálculo
- `tyres.py` (194 líneas): Cálculo de neumáticos
- `fuel.py` (143 líneas): Cálculo de combustible
- 3 tests existentes (test_strategy.py, test_calculation.py)
- **Cobertura desconocida** — no hay pytest-cov configurado para shared

### 2.3 sidecar (519 líneas)
- `strategy_runner.py` (256 líneas): Duplica lógica de `StrategyService._process_cycle()` del backend
- `main.py` (138 líneas): Loop principal limpio
- `event_detector.py` (125 líneas): Detección de eventos
- **Sin tests**

---

## 3. Análisis TypeScript — Frontend (3,510 líneas)

### 3.1 Compilación
- ✅ `tsc --noEmit`: 0 errores
- ✅ 55 tests Vitest pasando

### 3.2 Estructura

| Directorio | Archivos | Líneas | Propósito |
|-----------|:--------:|:------:|-----------|
| `src/hooks/` | 5 | 1,109 | Custom hooks (WebSocket, PTT, audio) |
| `src/components/` | 5 | 772 | UI components |
| `src/store/` | 2 | 360 | Zustand stores |
| `src/services/` | 3 | 219 | API, audioQueue, msgpack |
| `src/__tests__/` | 5 | 564 | Tests |

### 3.3 Observaciones

**useWebSocket.ts (459 líneas):** 
- Hook más grande del frontend. Maneja: conexión, msgpack, delta encoding, TTS queue, alertas, advice streaming.
- Posible split en: `useWebSocketConnection`, `useWebSocketTelemetry`, `useWebSocketTTS`

**App.tsx (475 líneas):**
- Segundo archivo más grande. Maneja: PTT, speech recognition, layout.
- Posible extracción de lógica PTT a hook `useSpeechRecognition`

**Sin errores de linter/type-check.** La base TypeScript es sólida.

---

## 4. Análisis Rust — Tauri (149 líneas)

### 4.1 Código

```rust
// main.rs — 143 líneas ✅ Limpio
// lib.rs — 6 líneas (placeholder)
```

### 4.2 Rust Skills Assessment

| Categoría | Regla | Estado | Notas |
|-----------|-------|:------:|-------|
| **Ownership & Borrowing** | `own-borrow-over-clone` | ✅ | No hay `.clone()` innecesario |
| | `own-copy-small` | ✅ | Tipos pequeños correctos |
| | `own-lifetime-elision` | ✅ | Elisión de lifetimes correcta |
| **Error Handling** | `err-result-over-panic` | ⚠️ | 3 `.unwrap()` en líneas 93, 98, 134 |
| | `err-expect-bugs-only` | ⚠️ | `unwrap()` en `lock()` → podría ser `expect("lock poisoned")` |
| **Memory Optimization** | `mem-with-capacity` | ✅ | No aplica (no hay colecciones grandes) |
| **API Design** | `api-must-use` | ⚠️ | `Result` de `child.kill()` se ignora con `let _ =` |
| **Async/Await** | `async-tokio-runtime` | ✅ | Uso correcto de `tauri::async_runtime::spawn` |
| **Performance** | `perf-iter-over-index` | ✅ | No aplica |
| **Project Structure** | `proj-lib-main-split` | ⚠️ | `main.rs` tiene toda la lógica, `lib.rs` es placeholder vacío |
| | `proj-mod-by-feature` | ⚠️ | Podría extraer `sidecar_manager.rs`, `tray_menu.rs`, `window_setup.rs` |
| **Clippy & Linting** | `lint-deny-correctness` | ❌ | No hay `#![deny(clippy::correctness)]` |
| | `lint-rustfmt-check` | ❌ | No verificado |

### 4.3 Hallazgos Específicos

**1. Unwraps sin contexto (3 ocurrencias):**
```rust
// Línea 93 (tray icon)
.icon(app.default_window_icon().unwrap().clone())  // Si no hay icono, panic

// Línea 98 (lock)
app.state::<BackendChild>().0.lock().unwrap().take()  // Si lock poisoned, panic

// Línea 134 (lock)
state.0.lock().unwrap().take()  // Mismo patrón
```

**Fix:** `expect("reason")` o manejar con `if let Ok(...)`.

**2. lib.rs placeholder:**
```rust
pub fn run_placeholder() {
    println!("Vantare Ingeniero IA - Rust Lib initialized.");
}
```
Nunca se llama. Se puede eliminar.

**3. Sidecar management duplicado:**
La lógica de matar el sidecar aparece en 2 lugares:
- `on_menu_event("quit")` (línea 97-101)
- `on_window_event(CloseRequested)` (línea 133-137)

**Fix:** Extraer a función `fn kill_sidecar(app: &tauri::AppHandle)` en lib.rs.

**4. `cfg!(debug_assertions)` vs `#[cfg(debug_assertions)]`:**
La línea 27 usa `cfg!(...)` (macro runtime), que funciona pero es menos idiomático que `#[cfg(...)]` (atributo compile-time). En este caso es correcto porque está dentro de una función, no separando funciones completas.

---

## 5. Plan de Refactor Priorizado

### Fase R1: Seguridad y Robustez (CRÍTICO)

| # | Archivo | Cambio | Esfuerzo |
|:-:|---------|--------|:--------:|
| R1.1 | `main.rs:93` | `unwrap()` → `expect("app icon missing")` | 5min |
| R1.2 | `main.rs:98,134` | `unwrap()` → `if let Ok(guard)` con log | 10min |
| R1.3 | `main.rs` | Extraer `kill_sidecar()` a lib.rs | 15min |
| R1.4 | `strategy_service.py` | Refactor `_process_cycle` (E/40 → 5 funciones A) | 2h |

### Fase R2: Complejidad (ALTA)

| # | Archivo | Cambio | Esfuerzo |
|:-:|---------|--------|:--------:|
| R2.1 | `engine.py` | Extraer `_process_*_trigger()` de `evaluate_cycle()` | 1h |
| R2.2 | `context_builder.py` | Extraer normalizadores de `_build_ticker_data()` | 1h |
| R2.3 | `live_context.py` | Extraer métodos de buffer de `on_lap_completed()` | 30min |
| R2.4 | `spotter.py` | Extraer condiciones a métodos (patrón monitor) | 30min |
| R2.5 | `llm_client.py` | Extraer `_parse_sse_tokens()` de ambos streams | 30min |
| R2.6 | `lmu_api.py` | Refactor `poll_api` con `CacheManager` class | 1h |

### Fase R3: Cobertura de Tests (MEDIA)

| # | Archivo | Cambio | Esfuerzo |
|:-:|---------|--------|:--------:|
| R3.1 | `strategy_service.py` | Crear `test_strategy_service.py` | 2h |
| R3.2 | `sidecar/` | Tests para strategy_runner y event_detector | 1h |
| R3.3 | `spotter.py` | Tests para líneas 23-29 (fallback dict) | 15min |

### Fase R4: Limpieza (BAJA)

| # | Archivo | Cambio | Esfuerzo |
|:-:|---------|--------|:--------:|
| R4.1 | `build_backend.py`, `run_dev.py` | 3 f-strings sin placeholder | 5min |
| R4.2 | `test_ws_integration.py` | Eliminar imports no usados | 5min |
| R4.3 | `lib.rs` | Eliminar placeholder | 2min |
| R4.4 | `sidecar/README.md` | Actualizar con estado real | 10min |
| R4.5 | `.chroma_db/` | Añadir a `.gitignore` | 2min |

---

## 6. Dependencias entre Refactors

```
R1 (Seguridad)
├── R1.1-R1.3 (Rust) — independiente
└── R1.4 (strategy_service) — requiere tests primero → R3.1

R2 (Complejidad)
├── R2.1 (engine) — requiere tests existentes ✅
├── R2.2 (context_builder) — requiere tests existentes ✅
├── R2.3 (live_context) — requiere tests existentes ✅
├── R2.4 (spotter) — requiere tests existentes ✅
├── R2.5 (llm_client) — requiere tests existentes ✅
└── R2.6 (lmu_api) — requiere tests creados ✅

R3 (Tests)
├── R3.1 (strategy_service) — prerrequisito de R1.4
├── R3.2 (sidecar) — independiente
└── R3.3 (spotter) — independiente

R4 (Limpieza) — todos independientes
```

---

## 7. Estado Actual por Lenguaje

```
Python (12,094 líneas) ─────────────────────────────────────
  ✅ 285 tests backend
  ✅ 0 errores ruff en producción
  ⚠️ 61 errores ruff en tests (F401)
  ⚠️ 15 funciones con complejidad C+
  ⚠️ Cobertura 69% (objetivo: 80%)
  ❌ strategy_service.py (cobertura 49%)
  ❌ shared-telemetry sin tests
  ❌ shared-strategy con 3 tests mínimos
  ❌ sidecar sin tests

TypeScript (3,510 líneas) ──────────────────────────────────
  ✅ tsc --noEmit: 0 errores
  ✅ 55 tests Vitest
  ✅ Sin problemas de linting
  ⚠️ useWebSocket.ts (459 líneas) → candidato a split
  ⚠️ App.tsx (475 líneas) → candidato a split

Rust (149 líneas) ──────────────────────────────────────────
  ✅ Código funcional y correcto
  ⚠️ 3 unwrap() sin contexto
  ⚠️ lib.rs placeholder
  ⚠️ Lógica de sidecar duplicada
  ❌ Sin clippy configurado
  ❌ Sin rustfmt verificado
```

---

## 8. Recomendaciones

### Inmediato (< 1h)
1. Eliminar 3 `unwrap()` en Rust (R1.1, R1.2)
2. Eliminar lib.rs placeholder (R4.3)
3. Fix 3 f-strings (R4.1)
4. Añadir `.chroma_db/` a `.gitignore` (R4.5)

### Hoy (< 4h)
5. Extraer `kill_sidecar()` a función compartida (R1.3)
6. Refactor `_process_cycle()` en strategy_service (R1.4) — requiere tests
7. Tests para strategy_service (R3.1)

### Esta semana (< 8h)
8. Refactor de complejidad media (R2.1-R2.6)
9. Tests para sidecar (R3.2)
10. Configurar clippy + rustfmt en CI
11. Migrar lmu_api.py a clase CacheManager (R2.6)

### Post-MVP
12. Refactor useWebSocket.ts y App.tsx (split en hooks)
13. Tests para shared-telemetry
14. Tests completos para shared-strategy
