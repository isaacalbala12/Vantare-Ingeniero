# Progress Log — Fase 2: Sidecar StrategyService en Windows

## Session 2026-05-26 (21:50–)

### 21:55 — Análisis completado
- Leído `StrategyService._process_cycle()` (474 líneas): mapeo LMU shared memory → TelemetryFrame → compute_strategy → StrategyAdvice
- Leído `shared-strategy/models.py`: TelemetryFrame (~70 campos), StrategyAdvice, StrategyState, CompetitorTelemetry
- Leído `websocket.py` strategy_sender_loop (lines 105-156): consume strategy_service.get_latest_advice()
- Leído `main.py` lifespan: TelemetryReader(offline=True), app.state.latest_client_frame = None
- Plan reescrito con detalle de implementación (clases, métodos, snippets)

### Próximo paso
- Presentar plan a usuario para aprobación
- Phase 2: Crear `sidecar/` con pyproject.toml, estructura src/sidecar/, main.py, strategy_runner.py, event_detector.py
