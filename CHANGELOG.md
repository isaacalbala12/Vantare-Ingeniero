# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [0.5.1] - 2026-06-11 — Auto-update sin firma de código

### Fixed

- **Auto-update** — desactiva verificación Authenticode en instaladores sin certificado (`verifyUpdateCodeSignature=false`); corrige error *"not signed by the application owner"* al actualizar desde v0.2.x

## [0.5.0] - 2026-06-11 — Personalidades avanzadas

Configuración avanzada de personalidad del ingeniero: control de proactividad (filtro por prioridad), frecuencia de perlas de sabiduría (0-100%), y tono coloquial opcional.

### Added

- **`PersonalityRuntime`** — sweary, proactivity, pearl_frequency en PersonalityPack con apply_runtime()
- **Config WS** — `proactivityLevel`, `pearlFrequency` en config_update / config_ack (invariante I1)
- **Hub → Voz → Ingeniero** — selector de proactividad (Baja/Normal/Alta) y slider de frecuencia de perlas (0-100%)
- **Preview de tono** — muestra el tono activo + indicación de lenguaje coloquial si sweary activo
- **CC Pearls module** — respeta `pearl_frequency` en todos los tipos (overtake, comeback, fast_lap, standard)
- Tests: personality v2, pearls frequency (100 rolls deterministas), CC pearls frequency, comentary orchestrator proactivity gate, config WS v2 fields, frontend personalityConfig

### Changed

- `pearls_of_wisdom.py`: `__import__("random")` → `import random` estándar
- `engine.py`: sweary sync a personality en init y lifespan
- Voice contract I1–I5 no afectados (sin cambios en voice pipeline)

## [0.4.0] - 2026-06-07 — Frases editables

Permite editar, exportar e importar frases spotter/triggers con overrides en AppData y hot-reload de la caché TTS spotter.

### Added

- **`PhraseStore`** — merge defaults empaquetados + `user_phrases.json` en `%APPDATA%/Vantare/phrases/`
- **REST `/phrases`** — GET merged/defaults, PUT/import/export, POST/DELETE reset
- **Hub → Audio → Frases personalizadas** — editor por clave/perfil, variantes una por línea, export/import JSON
- **`SpotterPhraseCache.invalidate_all()`** — re-warm async tras guardar frases
- Tests: `test_phrase_store`, `test_phrases_router`, `phraseEditor.test.ts`

### Changed

- `PhrasePicker.load_defaults()` usa catálogo mergeado (defaults + usuario)
- `default_spotter_phrases()` lee frases del picker mergeado, no solo del bundle
- `PUT /phrases` fusiona overrides por defecto; `?replace=true` para reemplazo total
- Import JSON fusiona por defecto; confirmación en Hub para import/reset

### Fixed

- JSON corrupto en AppData expuesto vía `GET /phrases/meta` y aviso en Hub
- Guardado vacío elimina fichero usuario (no deja `{}` huérfano)
- `reload_picker()` síncrono antes del re-warm async de caché spotter
- Caché spotter deriva frases laterales (`still_there_*`, `hold_line_*`) del picker
- Validación de prefijos robóticos solo al inicio de frase; `.format()` tolera plantillas mal formadas
- Tests de picker aislados con `load_bundle_defaults()`

## [0.3.0] - 2026-06-11 — Frases humanas + Gemini TTS

Release con copy de radio más natural y **Gemini TTS** como proveedor selectable por rol (ingeniero/spotter), manteniendo Edge como fallback.

### Added

- **`phrase_picker`** — variantes con `|` en JSON spotter/triggers; perfiles standard/formal/aggressive
- **`trigger_phrases_es.json`** — catálogo P0 (fuel, FCY, lluvia, frenos, neumáticos, ventana pits)
- **`TtsRouting`** + selectores Hub `ttsProviderEngineer` / `ttsProviderSpotter` (schema config v5)
- **Gemini TTS** en `TTSManager` con fallback Edge; voz por rol (engineer/spotter)
- Tests: `test_phrase_picker`, `test_trigger_phrases_wired`, `test_tts_manager_gemini`, `test_engine_trigger_phrases`, `test_crewchief_phrase_picker`

### Changed

- Spotter usa `PhrasePicker` para frases con variantes humanas
- Módulos Crew Chief (fuel tiers 2–3, tyre/brake wear, pits, flags FCY) priorizan frases del picker
- `IntelligenceEngine` emite alertas con `phrase_key` en triggers DETERMINISTIC/LLM
- Caché spotter: variante estable al warm con voz spotter; bypass cuando spotter usa Gemini

### Fixed

- `runtime_config_snapshot` devuelve strings de provider TTS correctamente
- Gemini spotter ya no reproduce WAV precalentados en Edge cuando el provider es Gemini
- Frases picker cableadas al path de voz real (CC + engine), no solo unit tests
- Rising-edge en triggers lluvia/neumáticos para evitar spam de alertas
- FCY humano solo en activación FCY; Safety Car y pits cerrados conservan copy específico
- Fuel tier 1 (&lt;1 vuelta) mantiene template crítico dedicado

## [0.2.14] - 2026-06-11 — Voice Beta (stable)

Release estable de la **re-arquitectura de voz**: validada en pista (LMU) y promovida desde pre-release el 2026-06-11. Audio reproducido en el backend (pygame), telemetría y race loop in-process, contrato de voz documentado y gates de calidad.

### Added

- **Pipeline de voz in-process** (`voice_loop`, cola con prioridad, moderador, caché TTS, pygame)
- **Race loop nativo** sin sidecar WS separado; telemetría LMU vía memoria compartida
- **Contrato de voz** normativo (`docs/voice-contract.md`) + matriz de tests frontend/backend
- **Spotter cartesiano** y frases ES; integración spotter → cola de voz
- **Monitores proactivos** (combustible, lluvia, FCY, daños, penalizaciones, pits)
- **Overlay sincronizado con backend playback** vía eventos WS `voice_playback_start` / `voice_playback_end`
- **Scripts de release/QA:** `verify_beta_gate.ps1`, `verify_bundle_startup.ps1`, `verify_voice_contract.py`, `verify-release.ps1`, `doctor.ps1`
- **Planes y ADRs** de la re-arquitectura voice beta (Hitos 1–8)

### Changed

- **`voiceBackendPlayback=true` por defecto** — el frontend ya no reproduce TTS; solo orquesta UI/overlay
- Hub y overlay Electron actualizados (`ttsPipeline`, `ttsPlaybackGate`, `backendVoiceOverlay`)
- Bundle PyInstaller ampliado (pygame/SDL, faster-whisper, voice modules)
- Versión unificada backend/frontend en `0.2.14`

### Fixed

- Crash al arrancar bundle (`UnboundLocalError: broadcast_sync` en `main.py`)
- Overlay de radio invisible cuando el audio salía del backend
- Gates de commentary batch y coherencia runtime/config sync

### Known limitations

- `duck_lmu.exe` opcional no incluido en el instalador (ducking LMU manual)
- Requiere clave LLM configurada en `.env` del backend empaquetado
- Windows x64 + Le Mans Ultimate

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
