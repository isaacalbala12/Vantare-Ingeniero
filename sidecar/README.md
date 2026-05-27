# Vantare Ingeniero IA — Strategy Sidecar

Sidecar de estrategia para Windows. Lee shared memory de Le Mans Ultimate, calcula estrategia determinista y envía datos al backend vía WebSocket localhost.

## Arquitectura

```
LMU Shared Memory (20Hz)
  │
  ├→ StrategyRunner.process_cycle() cada 2s
  │    ├→ TelemetryFrame → compute_strategy() → StrategyAdvice
  │    ├→ Fuel, Tyres, Brakes, Hybrid, PitWindow
  │    └→ brake_wear = 0.0 (deuda técnica: REST API no implementada)
  │
  ├→ StateChangeDetector.detect()
  │    ├→ posición, pits, gap, safety car, clima, vuelta
  │    └→ eventos + snapshots por vuelta
  │
  └→ WebSocket → ws://127.0.0.1:8008/ws/sidecar (cada 2s)
       └→ {event: "strategy_frame", data: {advice, frame, events}}
```

## Ejecución

### Desarrollo (directo)
```bash
cd sidecar
pip install -e ../shared-telemetry -e ../shared-strategy -e .
cd src && python -m sidecar.main
```

### Producción (PyInstaller)
```bash
cd sidecar
pip install pyinstaller
pyinstaller build.py
# → dist/strategy-sidecar/strategy-sidecar.exe
```

### Tauri (bundle)
En release mode, Tauri spawna `strategy-sidecar.exe` automáticamente al arrancar la app.

## Dependencias

- `shared-telemetry` — lector de shared memory de LMU (incluye C extensions)
- `shared-strategy` — motor determinista de estrategia
- `websockets` — cliente WebSocket asíncrono
- `python-dotenv` — configuración vía .env

## Reconexión

El sidecar implementa backoff exponencial (1s → 30s, máx 10 intentos) si el backend no responde. Al reconectar, reanuda el envío de strategy_frames automáticamente.
