# ADR-002: GitHub Releases + electron-updater

## Status

Accepted

## Date

2026-06-08

## Context

Usuarios finales en Windows necesitan:

1. Descargar un instalador único (app + backend)
2. Recibir updates sin buscar manualmente en GitHub
3. Mantener lockstep shell + backend (misma versión)

Existía banner en Hub vía backend `/version/check` (solo enlace externo).

## Decision

- **Hosting:** GitHub Releases en `isaacalbala12/Vantare-Ingeniero`
- **Artefactos:** `vantare-ingeniero-${version}-setup.exe` + `latest.yml`
- **Cliente:** `electron-updater` con `publish.provider: github` en `electron-builder.yml`
- **UI:** Hub → Avanzado → panel Actualizaciones (check / download / restart)
- **CI:** push tag `v*.*.*` dispara `.github/workflows/release-desktop.yml`
- **Versión única:** `frontend/package.json`, `backend/src/version.py`, tag git alineados

Banner `/version/check` se omite cuando existe bridge desktop updater.

## Alternatives Considered

### Solo enlace a Releases (status quo alpha)

- Rejected: fricción alta, usuarios no actualizan

### Squirrel.Windows / custom updater

- Rejected: electron-updater integrado con electron-builder

### Actualizar backend y shell por separado

- Rejected: riesgo de mismatch API/WS; un NSIS empaqueta ambos

## Consequences

- Tags `v*` son el contrato de release; no reutilizar tag sin `--force` consciente
- SmartScreen puede advertir hasta code signing (P2)
- Dev mode (`npm run dev:electron`) no usa updater — documentado en `docs/instalacion-desktop.md`
