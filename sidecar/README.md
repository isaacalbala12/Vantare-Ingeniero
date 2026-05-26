# Vantare Ingeniero IA — Sidecar

Sidecar StrategyService para Windows. Corre junto a Le Mans Ultimate, lee la shared memory real y envía resultados de estrategia al backend Linux vía WebSocket.

## Instalación

```bash
cd sidecar
pip install -e ../shared-telemetry -e ../shared-strategy -e .
cp .env.example .env
# Editar .env con la IP del backend Linux
```

## Ejecución

```bash
python -m sidecar.main
```

## Arquitectura

```text
LMU Shared Memory → TelemetryReader(20Hz) → StrategyRunner(2s)
                                           → StateChangeDetector(20Hz)
                                           → WebSocket → Linux Backend
```

## Dependencias

- `shared-telemetry` — lector de shared memory de LMU
- `shared-strategy` — motor determinista de estrategia
