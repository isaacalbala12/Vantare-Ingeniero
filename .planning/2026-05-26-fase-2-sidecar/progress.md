# Progress Log — Fase 2: Sidecar StrategyService en Windows

## Session 2026-05-26 (21:50–)

### 21:55 — Análisis completado
- Leído `StrategyService._process_cycle()` (474 líneas): mapeo LMU shared memory → TelemetryFrame → compute_strategy → StrategyAdvice
- Leído `shared-strategy/models.py`: TelemetryFrame (~70 campos), StrategyAdvice, StrategyState, CompetitorTelemetry
- Leído `websocket.py` strategy_sender_loop (lines 105-156): consume strategy_service.get_latest_advice()
- Leído `main.py` lifespan: TelemetryReader(offline=True), app.state.latest_client_frame = None
- Plan reescrito con detalle de implementación (clases, métodos, snippets)

### 21:58 — Estructura sidecar creada
- `sidecar/pyproject.toml` — hatchling, Python >=3.12, deps: pydantic, dotenv, httpx, websockets
- `sidecar/.env.example` — BACKEND_WS_URL
- `sidecar/README.md` — docs de instalación y uso
- `sidecar/src/sidecar/__init__.py`
- `sidecar/src/sidecar/main.py` — entrypoint: WS connect, loop 2s, graceful shutdown, exponential backoff reconexión

### 22:12 — Subagentes despachados en paralelo
- **Subagente 1 (c48c36a9)**: Sidecar — strategy_runner.py (257 líneas), event_detector.py (126 líneas)
- **Subagente 2 (54719246)**: Backend — /ws/sidecar endpoint + strategy_sender_loop modificado + main.py

### 22:17 — Bugs corregidos en sidecar
- CompetitorTelemetry: field names incorrectos → corregidos con nombres reales del modelo
- lap_time_best/lap_time_previous: race_state.lap_times (inexistente) → player.best_laptime/player.last_laptime
- position_xyz: acceso .x .y .z → [0] [1] [2] (Tuple, no named tuple)
- telemInfo vs telemetryData: corregido a telemInfo

### 22:18 — Verificación
- Sidecar: py_compile OK (strategy_runner.py, event_detector.py, main.py)
- Backend: import OK (2 rutas: /ws y /ws/sidecar)
- pytest: 100 passed, 13 warnings (preexistentes de ctypes)
- Backend committed y listo para producción

### Estado final Fase 2
✅ Phase 1: Análisis
✅ Phase 2: Proyecto sidecar/
✅ Phase 3: StateChangeDetector (8 eventos)
✅ Phase 4: StrategyRunner (257 líneas)
✅ Phase 5: Backend handler (/ws/sidecar + fallback)
✅ Phase 6: Verificación (100 tests OK)
