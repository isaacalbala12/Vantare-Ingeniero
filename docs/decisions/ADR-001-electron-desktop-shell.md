# ADR-001: Electron como shell desktop de producción

## Status

Accepted

## Date

2026-06-08

## Context

Vantare necesita en Windows:

- Hub de configuración (1920×1080)
- Overlay always-on-top transparente sobre el sim
- Atajos globales PTT
- Backend Python empaquetado en el mismo instalador
- Auto-update sin abrir navegador

El repo incluía Tauri 2 (`frontend/src-tauri`) y un sidecar backend. Tauri funcionaba pero el overlay, tray, gamepad y empaquetado del backend PyInstaller convergieron más rápido en Electron.

## Decision

Usar **Electron 34 + electron-builder (NSIS)** como único canal desktop de producción.

- Main/preload en `frontend/electron/`
- Renderer: Vite multi-entry (`index.html` hub, `overlay.html`)
- Backend en `extraResources` → `resources/backend/`
- `duck_lmu.exe` en `extraResources` para ducking de audio del juego

Tauri permanece en el repo como legacy; no se publica en Releases.

## Alternatives Considered

### Tauri 2 (mantener)

- Pros: binario más pequeño, Rust nativo
- Contras: sidecar naming, overlay + tray + updater menos maduro en nuestro fork
- Rejected para v1 desktop: coste de parity > beneficio inmediato

### Qt / PySide (estilo TinyPedal)

- Pros: probado en ecosistema LMU Python
- Contras: UI menos flexible para overlay F1 + pipeline LLM/voz
- Rejected: ver `docs/arquitectura-shell-desktop.md`

## Consequences

- Build release solo en `windows-2022` (NSIS + PyInstaller + Rust duck)
- Vite debe usar `base: './'` para `file://` en producción
- Rutas renderer vía `app.getAppPath()/dist/` (`frontend/electron/paths.ts`)
- Documentación y CI orientados a `npm run build:desktop`
