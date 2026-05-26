# Findings & Decisions — Fase 2: Sidecar StrategyService

## Requirements
- Mover el cálculo de estrategia a Windows (shared memory real)
- Eliminar la dependencia de datos simulados en Linux
- Generar eventos y snapshots por vuelta para futuro RAG (Fase 3)
- Comunicación vía WebSocket JSON con el backend Linux

## Research Findings

### Componentes actuales reutilizables

**shared-telemetry/ (Windows, ya existe)**
- `TelemetryReader(offline=False)` — lee shared memory real de LMU
- `RaceState`, `SessionData`, `VehicleData` — modelos Pydantic
- `TelemetrySync` — sincroniza índices scoring↔telemetry
- Ya funciona en Windows (es donde corre LMU)

**shared-strategy/ (cross-platform, ya existe)**
- `compute_strategy(frame, state, track) → (advice, new_state)` — cálculo determinista
- `TelemetryFrame`, `StrategyAdvice`, `StrategyState` — modelos
- `fuel.py`, `tyres.py`, `brakes.py`, `hybrid.py`, `pit_window.py`, `competitors.py`
- Sin dependencias del backend Linux

**Backend: StrategyService (`backend/src/services/strategy_service.py`)**
- 474 líneas de lógica de mapeo de telemetría → TelemetryFrame
- `_process_cycle()`: leer shared memory → mapear campos → `compute_strategy()` → guardar advice
- Depende de `lmu_api.py` para brake wear (REST API de LMU)
- Creado en `main.py` lifespan con `StrategyService(reader)`

**Backend: strategy_sender_loop (`backend/src/routers/websocket.py`)**
- Líneas 105-156: envía `strategy` event cada 2s si hay cambios
- Llama a `strategy_service.get_latest_advice()` y evalúa triggers
- Actualmente envía el advice serializado como JSON

### Qué cambia con el sidecar

**ANTES (Fase 0-1):**
```
Windows → WebSocket telemetry 20Hz → Linux
Linux: TelemetryReader(offline=True) → StrategyService → get_latest_advice()
```

**DESPUÉS (Fase 2):**
```
Windows: TelemetryReader(offline=False) → StrategyRunner → WS strategy_frame 0.5Hz → Linux
Linux: ya no calcula estrategia, recibe del sidecar
```

### Estructura del sidecar
```
sidecar/
├── pyproject.toml
├── .env.example
├── src/
│   └── sidecar/
│       ├── __init__.py
│       ├── main.py              # Entrypoint asyncio + WS cliente
│       ├── strategy_runner.py   # Réplica de StrategyService._process_cycle()
│       └── event_detector.py    # StateChangeDetector (nuevo)
```

### Mensaje strategy_frame (WebSocket)
```json
{
  "event": "strategy_frame",
  "data": {
    "advice": { ... StrategyAdvice },
    "frame": { ... TelemetryFrame },
    "events": [ ... eventos detectados ],
    "snapshot": { ... snapshot por vuelta }
  }
}
```

### StateChangeDetector — eventos a detectar
| Evento | Condición | Frecuencia |
|--------|-----------|------------|
| position_change | player.place cambió | ~raro |
| pit_entry | player.in_pits pasó a True | ~1-3 por carrera |
| pit_exit | player.in_pits pasó a False | ~1-3 por carrera |
| gap_change | gap con rival cambió > 0.5s | ~frecuente |
| safety_car | safety_car_active cambió | ~raro |
| lap_completed | current_lap cambió | cada vuelta |
| weather_change | rain_chance o temp cambió | ~por sesión |
| yellow_flag | yellow_flag_active cambió | ~ocasional |

### Cambios en backend Linux
1. `websocket.py`: handler `strategy_frame` almacena en `app.state.latest_strategy_frame`
2. `strategy_sender_loop`: usar `latest_strategy_frame` en vez de `strategy_service.get_latest_advice()`
3. `main.py`: mantener `StrategyService(reader)` como fallback offline, loggear warning

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| Sidecar como proyecto Python separado | PyInstaller lo empaqueta como .exe en Fase 7 |
| Misma dependencia de shared-strategy | Cero duplicación de lógica de cálculo |
| StrategyRunner sin dependencias del backend | Sin lmu_api.py, sin REST poller |
| WebSocket JSON inicial | MessagePack en Fase 5 |
| Backend mantiene StrategyService offline | Desarrollo en Linux sin necesidad de sidecar |
| StateChangeDetector separado de StrategyRunner | Responsabilidad única — detector de eventos vs cálculo |
