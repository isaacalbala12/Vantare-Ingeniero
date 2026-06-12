# Vantare Ingeniero IA

Crew chief en español para **Le Mans Ultimate**: telemetría nativa Windows, spotter de baja latencia, ingeniero por voz (PTT + LLM) y overlay F1-style.

**Versión actual:** **0.5.1** — personalidades avanzadas + frases editables + fix auto-update.

**Distribución:** instalador Windows (Electron + backend empaquetado). Ver [Instalación desktop](docs/instalacion-desktop.md) y [Releases](https://github.com/isaacalbala12/Vantare-Ingeniero/releases).

## Novedades v0.5.x

- **Personalidades avanzadas** — proactividad (baja/normal/alta), frecuencia perlas 0–100%, preview tono
- **Frases personalizadas** (v0.4) en Hub → Audio: edita variantes spotter/triggers por perfil, export/import JSON
- **Auto-update** (v0.5.1) — funciona sin certificado de firma de código

## Novedades v0.4.0

- **Frases personalizadas** en Hub → Audio: edita variantes spotter/triggers por perfil, export/import JSON
- Overrides en `%APPDATA%/Vantare/phrases/user_phrases.json` con merge sobre el bundle
- Hot-reload de caché TTS spotter al guardar

## Novedades v0.3.0

- **Frases spotter/triggers** con variantes naturales (tono radio, perfiles standard/formal/aggressive)
- **Gemini TTS** opcional por rol en Hub → Audio → proveedor ingeniero/spotter (requiere `GEMINI_API_KEY` en backend; fallback Edge automático)
- **Voice Beta** sin cambios de arquitectura: audio sigue en backend (`voice_loop` + pygame)

## Quick start (desarrollo)

### Requisitos

- Windows 10/11 (telemetría nativa LMU)
- Python 3.12+
- Node.js 22+
- Rust (opcional, para `duck_lmu`)
- Le Mans Ultimate en ejecución para pruebas en pista

### Backend

```powershell
cd backend
pip install -e ../shared-telemetry -e ../shared-strategy -e ".[dev]"
copy .env.example .env
# Editar .env — LLM_API_KEY obligatorio para PTT/ingeniero
# GEMINI_API_KEY opcional — TTS Gemini (Hub → proveedor ingeniero/spotter)
python run_dev.py
```

Health: http://127.0.0.1:8008/health

### Frontend (Electron)

```powershell
cd frontend
npm ci
npm run dev:electron
```

Hub: http://127.0.0.1:1420 — en dev el backend **no** se auto-lanza; arranca el backend aparte.

### Build instalador local

```powershell
powershell -File scripts/build-desktop.ps1
```

Salida: `frontend/release/vantare-ingeniero-<version>-setup.exe`

## Comandos

| Comando | Dónde | Descripción |
|---------|--------|-------------|
| `python run_dev.py` | `backend/` | API + WS en `:8008` |
| `pytest tests/ -v` | `backend/` | Tests backend |
| `npm run dev:electron` | `frontend/` | Hub + overlay (dev) |
| `npm test` | `frontend/` | Vitest |
| `npm run build:desktop` | `frontend/` | Instalador NSIS |
| `powershell -File scripts/build-desktop.ps1` | raíz | Backend PyInstaller + desktop |

## Arquitectura (resumen)

```
LMU (shared memory + REST)
        │
        ▼
Backend FastAPI (:8008) — spotter 20Hz, ingeniero, TTS, perfiles
        │ WebSocket
        ▼
Electron — Hub (config) + Overlay (radio) + auto-update
```

Decisiones clave: [docs/decisions/](docs/decisions/README.md)

## Releases

| Canal | Cómo |
|-------|------|
| **Producción desktop** | Tag `v*.*.*` → workflow [Release Desktop](.github/workflows/release-desktop.yml) → [GitHub Releases](https://github.com/isaacalbala12/Vantare-Ingeniero/releases) |
| **CI** | Push/PR a `master` → [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| **Pre-release manual** | Actions → Pre-Release Gate → smoke local → tag |

Runbook: [docs/launch/first-deploy-runbook.md](docs/launch/first-deploy-runbook.md)

## Documentación

- **[Handbook del proyecto](docs/proyecto/README.md)** — visión, arquitectura, estado, roadmap, prompt orquestador
- [Instalación y actualizaciones](docs/instalacion-desktop.md)
- [Smoke checklist Electron](docs/qa/electron-smoke-checklist.md)
- [AGENTS.md](AGENTS.md) — guía rápida para agentes IA (ver handbook para estado actual)
- [Roadmap producto 0.3→1.1](docs/ROADMAP-1.0.md)
- [Roadmap beta / deuda alpha](docs/ROADMAP-beta.md)

## Licencia

MIT (ver repositorio).
