# Task Plan: Fase 2 — Sidecar StrategyService en Windows

## Goal
Mover el cálculo de estrategia a Windows (donde LMU shared memory entrega datos reales), eliminando dependencia de datos simulados en Linux. El sidecar produce `strategy_frame` cada 2s vía WebSocket al backend Linux.

## Current Phase
Phase 1 — Análisis completado. A la espera de aprobación para iniciar Phase 2.

## Phases

### Phase 1: Análisis de código existente ✅
- [x] Leer `StrategyService._process_cycle()` — 474 líneas, mapeo LMU shared memory → TelemetryFrame → compute_strategy → StrategyAdvice
- [x] Leer `shared-strategy/models.py` — TelemetryFrame (~70 campos), StrategyAdvice (fuel/tyres/brakes/hybrid/competitors/pit_window/track), StrategyState
- [x] Leer `websocket.py` strategy_sender_loop — consume `strategy_service.get_latest_advice()`, emite evento `strategy` cada 2s, evalúa intelligence engine triggers
- [x] Leer `main.py` lifespan — `StrategyService(reader)` con `TelemetryReader(offline=True)`, `app.state.latest_client_frame = None`
- [x] Identificar qué se reutiliza vs qué se duplica en el sidecar
- **Status:** complete

### Phase 2: Crear el proyecto sidecar
- [ ] **2.1** Crear `sidecar/pyproject.toml` con hatchling build, Python >=3.12
  - Dependencias: `shared-telemetry`, `shared-strategy`, `websockets>=12.0`, `pydantic>=2.6`, `httpx>=0.27`, `python-dotenv>=1.0`
  - [tool.hatch.build.targets.wheel] packages = ["src"]
- [ ] **2.2** Crear estructura `sidecar/src/sidecar/`:
  - `__init__.py`
  - `main.py` — entrypoint asyncio: lee `.env`, conecta WebSocket al backend, inicia StrategyRunner + StateChangeDetector, loop 2s
  - `strategy_runner.py` — réplica de `StrategyService._process_cycle()` (lines 164-473), sin dependencias del backend Linux
  - `event_detector.py` — StateChangeDetector (nuevo, no existe en código actual)
- [ ] **2.3** Crear `sidecar/.env.example`:
  ```
  BACKEND_WS_URL=ws://192.168.1.X:8008/ws
  ```
- [ ] **2.4** Crear `sidecar/README.md` con instrucciones de instalación y uso
- **Status:** pending

### Phase 3: StateChangeDetector (`event_detector.py`)
- [ ] **3.1** Clase `StateChangeDetector`: recibe `TelemetryFrame` actual, compara con anterior, emite eventos
  ```python
  class StateChangeDetector:
      def __init__(self):
          self._prev_frame: Optional[TelemetryFrame] = None
          self._prev_lap: int = 0
          self._lap_snapshots: list[dict] = []

      def detect(self, frame: TelemetryFrame) -> list[dict]:
          """Compara frame actual con anterior. Retorna lista de eventos detectados."""
  ```
- [ ] **3.2** 8 tipos de eventos:
  | Evento | Condición | Prioridad |
  |--------|-----------|-----------|
  | `position_change` | `lap_distance` implica cambio en orden relativo | baja |
  | `pit_entry` | `in_pits` pasó de False → True | alta |
  | `pit_exit` | `in_pits` pasó de True → False | alta |
  | `gap_change` | gap con rival inmediato > 0.5s | media |
  | `safety_car` | `safety_car_active` cambió | alta |
  | `lap_completed` | `lap_number` incrementó | media |
  | `weather_change` | (deferred — sidecar no tiene REST API weather) | baja |
  | `yellow_flag` | `yellow_flag_active` cambió | alta |
- [ ] **3.3** Snapshot por vuelta: al detectar `lap_completed`, guardar `{lap, fuel_used, avg_speed, tyre_wear[], brake_wear[], gaps[], timestamp}`
- **Status:** pending

### Phase 4: StrategyRunner en sidecar
- [ ] **4.1** Replicar helpers `safe_float()` y `safe_str()` en `strategy_runner.py`
- [ ] **4.2** Usar `TelemetrySync` de shared-telemetry para sincronizar índices scoring↔telemetry
- [ ] **4.3** `TelemetryReader(offline=False)` — shared memory real en Windows
- [ ] **4.4** Replicar lógica de `_process_cycle()` (lines 164-473) adaptada:
  - **NO** incluir `get_additional_data("brakes")` de `lmu_api.py` (ese módulo solo existe en backend Linux)
  - **NO** incluir modo offline/simulado (siempre `offline=False`)
  - brake_wear: usar `race_state.brakes.wear[]` directamente (ya está en shared-telemetry, no necesita REST API)
  - weather: omitido (el sidecar no tiene acceso a `/rest/sessions/weather`)
- [ ] **4.5** Clase `StrategyRunner`:
  ```python
  class StrategyRunner:
      def __init__(self, reader: TelemetryReader):
          self.reader = reader
          self.sync = TelemetrySync()
          self.state = StrategyState()
          self.track = TrackConfig(track_length=7004.0)
          self.latest_advice: Optional[StrategyAdvice] = None
          self.latest_frame: Optional[TelemetryFrame] = None
          # Acumuladores de vuelta (igual que StrategyService)

      def process_cycle(self) -> None:
          """Igual que _process_cycle(), sin dependencias del backend."""
  ```
- [ ] **4.6** `main.py` loop: cada 2s → `runner.process_cycle()` → `detector.detect(runner.latest_frame)` → `ws.send_json(strategy_frame)`
  ```python
  async def main():
      reader = TelemetryReader(offline=False, poll_rate=0.05)  # 20Hz interno
      reader.start()
      runner = StrategyRunner(reader)
      detector = StateChangeDetector()

      async with websockets.connect(ws_url) as ws:
          while True:
              await asyncio.sleep(2.0)
              runner.process_cycle()
              events = detector.detect(runner.latest_frame)
              await ws.send(json.dumps({
                  "event": "strategy_frame",
                  "data": {
                      "advice": runner.latest_advice.model_dump(mode="json"),
                      "frame": runner.latest_frame.model_dump(mode="json"),
                      "events": events
                  }
              }))
  ```
- **Status:** pending

### Phase 5: Handler `strategy_frame` en backend Linux
- [ ] **5.1** En `websocket.py` `websocket_endpoint()`, añadir handler:
  ```python
  elif event == "strategy_frame":
      frame_data = msg.get("data", {})
      if frame_data:
          app_state.latest_strategy_frame = frame_data
  ```
- [ ] **5.2** Modificar `strategy_sender_loop()`:
  - Intentar `app_state.latest_strategy_frame` primero
  - Si no existe (sidecar no conectado), fallback a `strategy_service.get_latest_advice()`
  - Loggear warning "Usando StrategyService offline (sidecar no detectado)"
- [ ] **5.3** En `main.py` lifespan:
  - Mantener `StrategyService(reader)` como fallback
  - Añadir `app.state.latest_strategy_frame = None`
  - Loggear: "Esperando strategy_frame del sidecar Windows. Usando StrategyService offline mientras tanto."
- **Status:** pending

### Phase 6: Verificación
- [ ] **6.1** Sidecar Python compila sin errores (`python -c "from sidecar.main import main"`)
- [ ] **6.2** Backend Python compila sin errores tras cambios (`python -c "from src.main import app"`)
- [ ] **6.3** `pytest backend/tests/` pasa (0 fallos)
- [ ] **6.4** Prueba manual de integración:
  - Iniciar backend Linux
  - En Windows: instalar sidecar, configurar `.env` con IP del backend, ejecutar
  - Verificar que backend recibe `strategy_frame` (log o health endpoint)
  - Verificar que frontend recibe `strategy` via WebSocket
- **Status:** pending

## Key Decisions
| Decisión | Rationale |
|----------|-----------|
| Sidecar como proyecto Python independiente | PyInstaller lo empaqueta como .exe en Fase 7 |
| Reutilizar `shared-strategy` y `shared-telemetry` | Cero duplicación de lógica de cálculo |
| Brake wear desde `shared-telemetry.brakes` no REST API | Elimina dependencia de `lmu_api.py` en sidecar |
| Weather omitido en sidecar | Sidecar no tiene acceso a `/rest/sessions/weather` de LMU |
| WebSocket JSON (no MessagePack) | MessagePack en Fase 5 |
| Backend mantiene StrategyService offline | Desarrollo/testing en Linux sin sidecar |
| `strategy_frame` incluye advice + frame + events | Mínimo overhead, datos completos para backend |

## Dependencies
- **Requiere Fase 1 completada**: ✅ (ya hecha)
- **Independiente de Fase 0**: el sidecar no depende de la telemetría WebSocket frontend→backend
- **Habilita Fase 3 (RAG)**: snapshots por vuelta del StateChangeDetector alimentan ChromaDB
- **Habilita Fase 7 (Tauri)**: sidecar se empaqueta con PyInstaller como .exe

## Notes
- El sidecar **NO** incluye `lmu_api.py` (REST API poller exclusivo del backend Linux)
- `StateChangeDetector` es completamente nuevo
- `strategy_sender_loop` se modificará para consumir del sidecar en vez de producirlo localmente
- Las 3 shared libs (shared-telemetry, shared-strategy) se instalan en modo editable: `pip install -e ../shared-telemetry -e ../shared-strategy`
