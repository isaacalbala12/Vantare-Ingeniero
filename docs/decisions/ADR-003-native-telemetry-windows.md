# ADR-003: Telemetría nativa Windows (sin sidecar)

## Status

Accepted

## Date

2026-06-07

## Context

El backend necesita telemetría LMU a ~20 Hz. La arquitectura alpha usaba un sidecar Windows que enviaba frames por WebSocket. Añadía un proceso extra, latencia y complejidad de empaquetado.

Task 49 completó lectura in-process vía `shared-telemetry` / `pyLMUSharedMemory`.

## Decision

- Lectura directa de shared memory en el proceso backend en Windows
- Flag `VANTARE_NATIVE_TELEMETRY=1` (default en app empaquetada)
- `src/app_runtime/` (antes `src/platform/`) para helpers OS — **no** nombrar paquetes `platform` (colisión PyInstaller con stdlib)

Sidecar queda desactivado por defecto (`SIDECAR_FALLBACK=false`).

## Alternatives Considered

### Mantener sidecar como path principal

- Rejected: dos procesos, más puntos de fallo en instalador

### WebSocket desde frontend a LMU

- Rejected: LMU expone memoria compartida nativa, no API en browser

## Consequences

- CI backend corre en `windows-2022` para tests de telemetría
- App empaquetada solo soporta Windows para telemetría nativa
- Renombrar `src/platform` fue necesario para PyInstaller (ver release v0.2.3)
