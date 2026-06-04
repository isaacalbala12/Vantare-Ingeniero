# Draft: Pipeline Review

## Requirements (confirmed)
- Sustituir tests actuales por tests E2E que detectan fallos reales en workflow
- 4 workflows críticos: CrewChief events, Spotter, Strategy sidecar, Config persistencia
- Nivel "real" = componentes reales + red real (nivel 2) + asserts de comportamiento (nivel 3)
- Fase 0: arreglar 22 tests pre-existentes rotos
- Fase final: Playwright E2E + stack dev manual
- LLM NO funciona (servidor en reparación) — avisar upfront, excluir PTT workflow

## Technical Decisions
- Playwright instalado globalmente (1.60.0) pero NO en frontend/node_modules → instalar
- Tests E2E backend: usar FastAPI TestClient + real WebSocket (httpx-ws)
- NO usar unittest.mock para componentes internos (CrewChiefRuntime, AudioPlayer, FrameCache)
- SÍ mockear dependencias externas imposibles: LMU game, GPU, micrófono
- Audio: verificar WAV file generado, no bytes
- Spotter: inyectar TelemetryFrame realista (state real, no dict vacío)
- Strategy: inyectar TelemetryFrame con datos suficientes (fuel, tyres, position)

## Research Findings
- `backend/src/intelligence/spotter.py:36-176` — 5+ condiciones: pit_limiter, gap_ahead/behind
- `backend/src/intelligence/event_engine.py:24` — `__init__(self, ap=None)` (mismatch con tests que pasan audio_player)
- `backend/src/services/frame_cache.py` — dedup por elapsed_time, spotter frame con frame_id
- `backend/src/services/event_bridge.py` — convierte QueuedMessage → CrewChiefAlertMessage
- Frontend: 7 test files existentes (api, appStore, audioQueue, configStore, filters, msgpack, useWebSocket)
- No E2E test del pipeline completo

## Open Questions
- None (user answered all)

## Scope Boundaries
### INCLUDE
- Phase 0: 5 fixes de API drift
- Phase 1: 4 workflow E2E tests backend
- Phase 2: WS multi-client integration
- Phase 3: Playwright setup + 4 E2E tests frontend
- Phase 4: Stack dev manual smoke
- Final Wave F1-F4

### EXCLUDE
- PTT/LLM workflow (LLM server down)
- Code quality / refactoring (separate phase)
- Performance / load testing
- Production deployment
- PyInstaller builds
- LLM benchmark tests
- Documentation

## Key Risk
- 22 tests pre-existentes pueden tener bugs de API más profundos que los 5 identificados
- Audio: si no hay dispositivo de audio en Windows, tests pueden fallar
- Playwright: necesita browsers (~200MB download)
- Sidecar: Windows-only, no testeable en dev (LMU no corre en test env)
