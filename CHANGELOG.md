# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [0.2.3] - 2026-06-09

### Added

- Instalador Windows NSIS (`vantare-ingeniero-*-setup.exe`) con Electron Hub + overlay + backend PyInstaller
- Auto-update in-app (`electron-updater`) en Hub → Avanzado → Actualizaciones
- Workflow CI `release-desktop.yml` en tag `v*`
- Telemetría nativa Windows (sin sidecar) vía `shared-telemetry`

### Fixed

- Backend empaquetado: colisión `src/platform` vs stdlib `platform` (PyInstaller)
- Hub negro en primera instalación: rutas `dist/` y `base: './'` en Vite
- Errores TypeScript que bloqueaban el build de release

### Changed

- Shell desktop principal: **Electron** (Tauri legacy en repo)
- Instalador NSIS backend-only (`installer/windows.nsi`) deprecado

## [0.2.1-alpha] - anterior

- Wave 9: perfiles, banner de update vía `/version/check`, sidecar legacy
