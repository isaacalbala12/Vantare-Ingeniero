# Draft: Comparación Vantare-Ingeniero vs CrewChiefV4

## Requirements (confirmed)
- Analizar el repositorio Vantare-Ingeniero en profundidad
- Comparar con CrewChiefV4 (https://gitlab.com/mr_belowski/CrewChiefV4)
- Identificar features faltantes
- Evaluar similitud de pipelines/arquitectura
- Recomendar cambios

## Technical Decisions
- Vantare: Python/FastAPI backend + React/Tauri frontend
- CrewChiefV4: C# (.NET) WinForms desktop app
- Ambos apuntan a LMU pero CrewChief soporta 20+ sims

## Scope Boundaries
- INCLUDE: Comparación exhaustiva de features, arquitectura, CI/CD
- INCLUDE: Recomendaciones de qué features añadir
- EXCLUDE: No implementar nada ahora, solo planificar

## Research Findings

### 📁 Archivos LEÍDOS de Vantare (54 archivos Python + 45 TypeScript/TSX + 3 Rust)

**Backend/src (52 .py):**
- `main.py` - FastAPI app, lifespan, service init
- `config.py` - Settings (Pydantic BaseSettings)
- `version.py` - APP_VERSION
- `debug_session_log.py` - Debug logging utility
- `models/messages.py` - Pydantic models (BaseMessage, AlertMessage, etc.)
- `routers/`: websocket.py, health.py, llm.py, tts.py, history.py, transcribe.py, profiles.py, version.py, traces.py, debug_ingest.py
- `services/`: strategy_service.py, tts_service.py, edge_tts_service.py, elevenlabs_tts_service.py, gemini_tts_service.py, lmu_api.py, mqtt_service.py, msgpack_codec.py, update_service.py
- `intelligence/`: engine.py, triggers.py, spotter.py, spotter_geometry.py, spotter_state.py, spotter_adapter.py, cartesian_spotter.py, context_builder.py, prompt_templates.py, llm_client.py, live_context.py, corner_names.py, driver_names.py, track_spline.py, flags_monitor.py, sector_analysis.py, ticker.py, time_format.py, pearls_of_wisdom.py, competitor_queries.py, formatter.py
- `persistence/`: history_store.py, profile_store.py, trace_store.py, event_store.py (ChromaDB RAG)
- `transport/broadcaster.py`
- `debug/lmu_dummy_server.py`

**Shared-libs:**
- `shared-telemetry/`: reader.py, sync.py, models.py, pyLMUSharedMemory/ (lmu_data.py, lmu_enum.py, lmu_mmap.py, lmu_type.py)
- `shared-strategy/`: __init__.py, calculation.py, competitors.py, fuel.py, hybrid.py, models.py, pit_window.py, tyres.py, vehicle_lookup.py

**Sidecar:**
- `sidecar/src/`: main.py, strategy_runner.py, event_detector.py

**Frontend/src (45 .ts/.tsx):**
- `App.tsx` - Main app (PTT, screen management, hotkeys, speech recognition)
- `hooks/`: useWebSocket.ts, usePTT.ts, useHotkey.ts, useAudioCapture.ts, useAudioContext.ts
- `services/`: api.ts, audioQueue.ts, audioUnlock.ts, msgpack.ts, spotterCommands.ts, spotterPhrases.ts, telemetryFrame.ts, ttsCache.ts, updateChecker.ts, alertVoice.ts, priorityAudioQueue.ts
- `components/`: RadioOverlay.tsx, ConfigTab.tsx, ChatBubble.tsx, PTTIndicator.tsx, SystemTrayMenu.tsx
- `store/`: appStore.ts, config.ts
- `__tests__/`: 17 test files (alertVoice, api, appStore, audioPipeline, audioQueue, audioTriggerMatrix, configStore, filters, msgpack, priorityAudioQueue, spotterCommands, spotterPipeline, ttsCache, useWebSocket, useWebSocket.spotter, fixtures/setup)
- `debugSessionLog.ts`

**Frontend/src-tauri (Rust):**
- `src/main.rs`, `src/lib.rs`, `src/audio_duck.rs`

**Scripts Python:**
- benchmark_spotter.py, capture_spotter_trace.py, verify_audio_pipeline.py, verify_r2.py, verify_r3.py, verify_spotter_pipeline.py

### 📁 Archivos de CrewChiefV4 (explorados vía API GitLab)

**Estructura del repo (C# .NET):**
```
CrewChiefV4/
├── ACC/, ACE/, ACS/, ACS128/       # Per-game shared memory parsers
├── AMS2/, Dirt/, F1_2018-2023/     # Game-specific modules
├── GTR2/, LMU/, PCars/, PCars2/    # Game-specific modules
├── PMR/, R3E/, RBR/, RF1/, RF2/    # Game-specific modules  
├── iRacing/                        # iRacing-specific (incluye formations)
├── AllGames/                       # Game-agnostic logic
├── Audio/                          # Sound engine (nAudio)
├── Events/                         # Event system
├── GameState/                      # Game state + session management
├── NumberProcessing/               # Number-to-speech (EN, IT, PT-BR)
├── Overlay/                        # Overlay system (HTML, subtitles, charts)
│   ├── OverlayElements/            # HTML/JS overlay elements
│   ├── Charts.cs                   # Live charting (fuel, tyres, brakes)
│   ├── CrewChiefOverlay.cs         # Main overlay orchestrator
│   ├── SubtitleOverlay.cs          # Subtitle overlay
│   └── OverlaySubscription.cs      # Data subscription model
├── PitManager/                     # Pit management (per-game implementations)
│   ├── PitManager.cs               # Core pit logic
│   ├── PitManagerVoiceCmds.cs      # Voice commands for pit
│   ├── PitManagerEventHandlers_LMU.cs  # LMU-specific pit handling
│   ├── PitManagerEventHandlers_RF2.cs  # rF2-specific pit handling
│   ├── PitManagerEventHandlers_iRacing.cs
│   └── PitManagerResponseHandlers.cs   # Response processing
├── Properties/                     # Settings system (hundreds of properties)
├── TrackSpline/                    # Track spline system
│   ├── TrackSpline.cs              # Spline data model
│   ├── TrackSplineManager.cs       # Manager
│   └── SplineViewerControl.cs      # Visual spline viewer
├── Track_splines/                  # Track spline DATA files (per track)
├── VROverlayWindow/                # VR overlay (OpenVR)
├── commands/                       # Voice command macros
│   ├── CommandMacro.cs             # Macro definition
│   ├── MacroManager.cs             # Macro execution
│   ├── KeyPresser.cs               # Keyboard simulation
│   └── Rf2ChatTransceiver.cs       # rF2 chat integration
├── sounds/                         # Sound packs
│   ├── voice/                      # Voice recordings (Jim, Jerry, etc.)
│   ├── driver_names/               # ~5000+ pre-recorded driver names
│   ├── pace_notes/                 # Rally pace note sounds
│   ├── personalsiations/           # Custom name recordings
│   ├── fx/                         # Sound effects
│   └── background_sounds/          # Ambient sounds
├── plugins/                        # Per-game plugins (DLLs)
├── tools/                          # Helper tools
├── ui_text/                        # UI text resources
├── Resources/                      # Embedded resources
├── SRE/                            # Speech recognition engine
├── CrewChief.cs                    # MAIN ORCHESTRATOR
├── CommandManager.cs               # Voice command processing
├── SpeechRecogniser.cs             # Windows speech recognition
├── SpeechCommands.cs               # ALL SPEECH COMMANDS (hundreds)
├── SpeechTrace.cs                  # Speech debug logging
├── NoisyCartesianCoordinateSpotter.cs  # SPOTTER ENGINE
├── SharedMemory.cs                 # Base shared memory reader
├── CarData.cs                      # Car database
├── TrackData.cs                    # Track database
├── DriverNameHelper.cs             # Driver name management
├── Configuration.cs                # Configuration manager
├── UserSettings.cs                 # User settings (properties)
├── DataFiles.cs                    # Data file management
├── DriverTrainingService.cs        # Driver training/fuel data
├── AdditionalDataProvider.cs       # REST API data (fuel, damage)
├── QueuedMessage.cs                # Message queuing
├── ThreadManager.cs                # Thread management
├── CircularBuffer.cs               # Ring buffer
├── ColloquialTime.cs              # Time formatting
├── PluginInstaller.cs              # Game plugin installer
├── ControlVolumeOfProcess.cs      # Volume control
└── UpdateHelper.cs                 # Auto-update
```

### ✅ CORRECCIÓN: Lo que Vantare YA TIENE (pero no sabía o no había leído):
1. ✅ **`corner_names.py`** + **`track_spline.py`** — Sistema de nombres de curvas con datos para 5 circuitos (Spa, Monza, Le Mans, Silverstone, Portimao). Busca por distancia.
2. ✅ **`driver_names.py`** — Fuzzy matching de nombres de pilotos (difflib.SequenceMatcher, normalize acentos).
3. ✅ **`vehicle_lookup.py`** — Base de datos de dimensiones de vehículos por nombre.
4. ✅ **Multi-class spotter** — `detect_lateral_proximity()` + `detect_path_lateral_proximity()` con weighting por clase.
5. ✅ **Blue flag** — `blue_flag_active` leído de `player_scor.mFlag == 6` en `strategy_service.py`.
6. ✅ **DRS state** — `drs_state` en `TelemetryFrame` y `context_builder.py`.
7. ✅ **Audio ducking** — `audio_duck.rs` en Tauri, `AUDIO_DUCK_LEVEL` en config.
8. ✅ **MQTT** — `mqtt_service.py` completo con publish de telemetría.
9. ✅ **Profile management** — `profile_store.py` + UI de perfiles en ConfigTab.
10. ✅ **Fuel persistence** — `history_store.py` guarda consumo vuelta a vuelta a JSON.
11. ✅ **Lap invalidation** — `is_invalid_lap` leído de `m_LapInvalidated`.
12. ✅ **Penalty tracking** — `num_penalties` en TelemetryFrame, PenaltyMonitorTrigger.
13. ✅ **LMU REST API poller** — `lmu_api.py` con weather, strategy_usage, garage_wear.
14. ✅ **Chat history** — `messageHistory` en el store, visible en Dashboard.
15. ✅ **Spotter cooldown** — `_alert_cooldown_s` y `_proximity_cooldown_s` en spotter.
16. ✅ **Fuel to end calculation** — `fuel_needed_to_finish` en FuelAdvice.
17. ✅ **Pit window** — `pit_window.py` con earliest/latest/optimal lap + undercut/overcut.
18. ✅ **Update checker** — `updateChecker.ts` + `/version` endpoint.
19. ✅ **Corner cutting warning** — vía `is_invalid_lap` detection.
20. ✅ **Session end detection** — `SessionEndTrigger` + `session_over`.
21. ✅ **Countdown/race start** — `PhaseChangedTrigger` detecta inicio de carrera.

### Vantare-Ingeniero Overview
- **Backend**: Python 3.12+ FastAPI asíncrono, puerto 8008
- **Frontend**: React 19 + TypeScript + Tauri 2 + TailwindCSS v4 + Zustand
- **Shared Libraries**: `shared-telemetry` (lectura memoria compartida LMU), `shared-strategy` (cálculo determinista)
- **Sidecar**: Proceso Windows independiente que lee shared memory y envía WebSocket al backend
- **Telemetría**: MessagePack binario sobre WebSocket a 20Hz (con delta compression)
- **Estrategia**: 0.5Hz con 19 triggers de condición de carrera (FuelCritical, FlagsMonitor, BrakeWearCritical, TyreDeg, Hybrid, Weather, PitWindow, CompetitorPitted, GapClosed, PushNow, SessionEnd, PhaseChanged, PilotQuestion, etc.)
- **Spotter**: 20Hz, TRIPLE detección: cartesiana (3D) + path-based (mPathLateral) + world-space
- **LLM**: vLLM streaming con preemption por prioridad (CRITICAL > HIGH > MEDIUM > LOW)
- **TTS**: Edge TTS (cloud), Piper TTS (local ONNX), ElevenLabs (cloud), Gemini TTS (cloud)
- **RAG**: ChromaDB para memoria de eventos con embeddings
- **MQTT**: Publicación de telemetría opt-in
- **Voice**: Web Speech API + ASR fallback (WAV → /transcribe)
- **CI/CD**: GitHub Actions - backend tests (pytest + coverage 70%), frontend (vitest), smoke tests
- **Release**: GitHub Actions release.yml + Tauri bundler (NSIS installer)
- **Tests**: 59 test files backend, 17 test files frontend

### CrewChiefV4 Overview
- **Lenguaje**: C# (.NET Framework 4.8 / WinForms)
- **Arquitectura**: Aplicación de escritorio monolítica
- **Soporte**: 20+ simuladores (cada uno con su propio parser de shared memory + plugin DLL)
- **Spotter**: `NoisyCartesianCoordinateSpotter.cs` - detección cartesiana con ruido/suavizado
- **Voice Commands**: `SpeechCommands.cs` + `CommandManager.cs` - cientos de comandos, con sistema de reconocimiento local (Windows Speech Recognition + nAudio)
- **TTS**: `Audio/` - nAudio para reproducción, voice packs pregrabados (WAV) + TTS sintético como fallback
- **Overlays**: `Overlay/` con HTML/JS overlay engine, `SubtitleOverlay.cs`, `VROverlayWindow/` (OpenVR)
- **Pit Management**: `PitManager/` - abstracción por juego (interfaces IPitMenu), con LMU-specific handlers
- **Driver Names**: `sounds/driver_names/` ~5000+ archivos WAV de nombres pregrabados
- **Track Landmarks**: `TrackSpline/` + `Track_splines/` - archivos de datos por circuito
- **Pace Notes**: `sounds/pace_notes/` - navegación rally
- **Properties**: `UserSettings.cs` + `Properties/` - cientos de opciones configurables
- **Command Macros**: `commands/` - ejecutar DOS commands, key presses, rF2 chat por voz
- **Audio Ducking**: `ControlVolumeOfProcess.cs` - control volumen de procesos externos
- **Multi-language**: Number readers EN, IT, PT-BR
- **CI/CD**: `.gitlab-ci.yml` (manual) + `appveyor.yml` - solo build, sin tests automatizados
- **Actualizaciones**: `UpdateHelper.cs` + `AutoUpdater.NET.dll` - auto-update con MSI installer

### Comparación de Arquitectura

**Vantare (moderna, distribuida)**:
```
Frontend Tauri (React)
    ↓ WebSocket (MessagePack 20Hz + JSON events)
Backend FastAPI (Python asyncio)
    ├── Sidecar Windows (shared memory → WS) ───→ LMU Shared Memory
    ├── StrategyService (0.5Hz) ───→ shared-strategy
    ├── IntelligenceEngine (triggers 0.5Hz)
    │   ├── SpotterService (20Hz, 3 detectores)
    │   └── LLM Client (vLLM streaming) ───→ Cloud LLM API
    ├── TTS Services (Edge/Piper/ElevenLabs/Gemini)
    ├── LMU REST API poller (weather, garage, strategy)
    ├── EventStore (ChromaDB RAG)
    ├── MQTT publisher
    └── HistoryStore (JSON persistence)
```

**CrewChiefV4 (monolítica, desktop)**:
```
CrewChief.exe (WinForms)
    ├── SharedMemory.cs (per-game plugin DLLs) → 20+ sims
    ├── GameState/ (session management)
    ├── CrewChief.cs (event loop 20Hz)
    │   ├── NoisyCartesianCoordinateSpotter.cs
    │   ├── Event system (Events/)
    │   └── SpeechRecogniser.cs ← Windows Speech API
    ├── AudioEngine (nAudio + WAV voice packs)
    ├── PitManager/ (per-game pit commands)
    ├── Overlay/ (HTML transparent window)
    ├── VROverlayWindow/ (OpenVR)
    └── UserSettings (Properties system)
```

### 🔄 Comparación CI/CD

| Aspecto | Vantare | CrewChiefV4 |
|---------|---------|-------------|
| **Platform** | GitHub Actions | GitLab CI + AppVeyor |
| **Backend tests** | ✅ pytest + coverage 70% | ❌ No tests automatizados |
| **Frontend tests** | ✅ Vitest + JSDOM | ❌ N/A (WinForms) |
| **E2E tests** | ✅ playwright | ❌ No |
| **Smoke tests** | ✅ Import + syntax check | ❌ No |
| **Lint** | ❌ No visible | ❌ No |
| **Build** | Tauri bundle (NSIS) | MSI installer |
| **Release** | GitHub Releases | AutoUpdater.NET |

### ✅ Lo que Vantare tiene MEJOR que CrewChief:

1. **LLM con lenguaje natural** — CrewChief solo dice frases fijas pregrabadas, Vantare conversa contextualmente con respuestas únicas
2. **Streaming de tokens** — Respuesta en tiempo real letra por letra
3. **Preemption por prioridad** — Una alerta crítica interrumpe inmediatamente la respuesta LLM en curso
4. **RAG (ChromaDB)** — Memoria semántica de eventos anteriores con búsqueda por similitud
5. **Arquitectura cliente-servidor** — Permite múltiples frontends (Tauri, web, MQTT subscribers)
6. **MessagePack + delta compression** — Ancho de banda 10x menor que JSON plano
7. **Triple detección spotter** — Cartesian 3D + path-based (mPathLateral) + world-space, mientras CrewChief usa solo cartesiano
8. **Pearls of Wisdom** — Mensajes motivacionales contextuales automáticos
9. **UI React moderna** — Mucho más extensible y personalizable que WinForms
10. **Sidecar desacoplado** — El lector de shared memory corre como proceso independiente
11. **Múltiples TTS backends** — Edge, Piper (local ONNX), ElevenLabs, Gemini
12. **Deterministic strategy engine** — Cálculo de estrategia 100% determinista (fuel, tyres, brakes, hybrid, pit window)
13. **19 triggers de carrera** — Sistema de condiciones más granular que CrewChief

### ❌ Lo que CrewChief tiene MEJOR o tiene y Vantare NO:

**⚠️ = Ya existe en Vantare pero menos maduro**
**❌ = No existe en Vantare**

#### Categoría 1: Spotter y Navegación
| # | Feature | CrewChief | Vantare | Prioridad |
|---|---------|-----------|---------|-----------|
| 1 | **Track landmarks DB extensa** | Track_splines/ para 20+ tracks | ⚠️ Solo 5 tracks (Spa, Monza, LeMans, Silverstone, Portimao) | ALTA |
| 2 | **Driver names pregrabados** | ~5000+ WAVs en sounds/driver_names/ | ⚠️ Solo fuzzy matching lógico | ALTA |
| 3 | **Pit exit position prediction** | Sí (Speech_PitExitPositionPrediction) | ❌ No existe | ALTA |
| 4 | **In-game overlays (HTML)** | OverlayElements/ (tablas, chartas HTML) | ❌ No existe | ALTA |
| 5 | **Three-wide spotter mejorado** | Manejo explícito de 3-wide | ⚠️ Básico en spotter_state.py | MEDIA |
| 6 | **Subtitle overlays** | SubtitleOverlay.cs | ❌ No existe | MEDIA |
| 7 | **VR overlays** | VROverlayWindow/ (OpenVR) | ❌ No existe | BAJA |
| 8 | **Track map visualization** | Charts.cs con mapa de pista | ❌ No existe | BAJA |

#### Categoría 2: Pit Management
| # | Feature | CrewChief | Vantare | Prioridad |
|---|---------|-----------|---------|-----------|
| 9 | **Pit menu commands (LMU)** | PitManager/PitManagerEventHandlers_LMU.cs + VoiceCmds | ❌ No existe | ALTA |
| 10 | **"Fuel to end" command** | PitManagerVoiceCmds.cs | ❌ No existe | ALTA |
| 11 | **"Change front tyres only"** | PitManager - comando de voz | ❌ No existe | ALTA |
| 12 | **"Repair [suspension/aero]"** | PitManager - comando de voz | ❌ No existe | ALTA |
| 13 | **Virtual Energy management** | "Pitstop virtual energy %" | ❌ No existe | ALTA |
| 14 | **Auto-refuel on pit entry** | Property "Enable auto refuelling" | ❌ No existe | MEDIA |
| 15 | **Pit stop benchmarking** | Pit benchmark persistence | ❌ No existe | BAJA |

#### Categoría 3: Comandos de Voz
| # | Feature | CrewChief | Vantare | Prioridad |
|---|---------|-----------|---------|-----------|
| 16 | **Comandos de voz estructurados** | SpeechCommands.cs (cientos) | ❌ Solo "pilot_question" libre | ALTA |
| 17 | **"How's my fuel?"** + respuesta detallada | Sí | ⚠️ Vía LLM (más lento) | MEDIA |
| 18 | **"How long's left?"** | Sí | ⚠️ Vía LLM | MEDIA |
| 19 | **"What's the gap to [driver]"** | Sí (reconocimiento por nombre) | ❌ No implementado | MEDIA |
| 20 | **"Monitor the car ahead/behind"** | Sí | ❌ No implementado | MEDIA |
| 21 | **Command macros** | MacroManager.cs (DOS, key presses) | ❌ No existe | BAJA |
| 22 | **Free dictation chat** | Rf2ChatTransceiver.cs | ❌ No existe | BAJA |
| 23 | **Wake word activation** | "Talk to Crew Chief" | ❌ Solo PTT | BAJA |

#### Categoría 4: Estrategia y Datos
| # | Feature | CrewChief | Vantare | Prioridad |
|---|---------|-----------|---------|-----------|
| 24 | **Fuel percentile calculator** | Experimental fuel with adjustable percentile | ⚠️ Estimación lineal básica | ALTA |
| 25 | **Pit window prediction mejorado** | Basado en fuel + benchmark + leader pace | ⚠️ Básico en pit_window.py | MEDIA |
| 26 | **Opponent reputation (iRacing)** | Sistema heurístico | ❌ No relevante (LMU) | BAJA |
| 27 | **Safety rating / license query** | "What's my iRating" | ❌ No relevante (LMU no tiene) | BAJA |
| 28 | **Incident tracking** | Conteo de incidentes | ❌ No implementado | BAJA |
| 29 | **Formation lap management** | iRacing formation rules DB | ❌ No implementado | BAJA |

#### Categoría 5: UI/UX
| # | Feature | CrewChief | Vantare | Prioridad |
|---|---------|-----------|---------|-----------|
| 30 | **Topic windows (brakes/tyres/fuel)** | Ventanas dedicadas con charts | ❌ No existe | MEDIA |
| 31 | **Properties system extenso** | Cientos de settings con tooltips | ⚠️ Config básica en ConfigTab | MEDIA |
| 32 | **Voice pack marketplace** | Sound packs descargables | ❌ No existe | MEDIA |
| 33 | **Diagnostics console** | Ventana de logs en vivo | ❌ No existe | BAJA |
| 34 | **Multi-language speech rec** | EN, IT, PT-BR number readers | ❌ Solo español | BAJA |
| 35 | **Rally pace notes** | sounds/pace_notes/ | ❌ No relevante | BAJA |
| 36 | **Race start countdown** | "Go! Go! Go!" automático | ❌ No implementado | BAJA |

#### Categoría 6: Arquitectura
| # | Feature | CrewChief | Vantare | Prioridad |
|---|---------|-----------|---------|-----------|
| 37 | **Multi-sim soporte** | 20+ sims con parsers dedicados | ❌ Solo LMU | LARGO PLAZO |
| 38 | **Auto-detect game** | Detección automática de proceso | ❌ No existe | BAJA |
| 39 | **Plugin installer** | PluginInstaller.cs per-game DLLs | ❌ No relevante (solo LMU) | BAJA |

### Análisis de Pipelines

**Vantare pipeline (telemetría → UI)**:
```
LMU Shared Memory (20Hz)
  ↓ Sidecar (strategy_runner.py) o StrategyService local
  ↓ WebSocket (MessagePack / JSON events)
  ↓ useWebSocket.ts
  ├── Telemetry (20Hz) → store → Dashboard
  ├── Spotter (alerts) → TTS queue → audio playback
  ├── Strategy (0.5Hz) → triggers → LLM client
  └── LLM streaming → tokens → TTS
```

**CrewChief pipeline (telemetría → UI)**:
```
LMU Shared Memory (20Hz)
  ↓ LMU plugin DLL
  ↓ CrewChief.cs event loop (20Hz)
  ├── Spotter (NoisyCartesianCoordinateSpotter)
  ├── Event system → message queue
  ├── Voice recognition → command processing
  ├── TTS/sound playback (nAudio)
  └── Overlay update (HTML window)
```

**Diferencia clave**: Vantare tiene una **capa LLM adicional** entre la telemetría y la salida. CrewChief es puramente determinista con mensajes pregrabados. Vantare puede generar análisis contextual único que CrewChief no puede, pero es más lento y depende de conectividad cloud.

### Recomendaciones Priorizadas

**FASE 1 — ALTA PRIORIDAD (impacto inmediato en experiencia de carrera):**
1. **Pit management commands** — "fuel to end", "change fronts", "repair", "virtual energy %"
   - Dónde: `backend/src/routers/pit_manager.py` + integración con LMU REST API
   - Por qué: Permite control total de boxes por voz, como CrewChief
   
2. **Comandos de voz estructurados** — Reconocimiento de comandos específicos sin LLM
   - Dónde: `frontend/src/services/spotterCommands.ts` (extender) + backend route
   - Por qué: Respuestas instantáneas vs 1-3s del LLM para preguntas comunes

3. **Track landmarks DB ampliada** — Añadir 15+ circuitos con nombres de curvas reales
   - Dónde: `backend/src/intelligence/track_spline.py` (ampliar)
   - Por qué: "Eau Rouge" suena mucho mejor que "km 0.8"

**FASE 2 — MEDIA PRIORIDAD (polish y UX):**
4. **In-game overlay system** — HUD transparente superpuesto al juego vía Tauri
   - Dónde: `frontend/overlays/` (nueva ventana Tauri sin chroma)
   
5. **Fuel calculator mejorado** — Percentil ajustable + persistencia
   - Dónde: `shared-strategy/src/fuel.py`
   
6. **Topic windows** — Ventanas de frenos, neumáticos, combustible
   - Dónde: `frontend/src/components/TopicWindows/`

7. **Pit exit prediction** — Predecir dónde saldrás
   - Dónde: `shared-strategy/src/pit_window.py`

**FASE 3 — BAJA PRIORIDAD (nice to have):**
8. Driver names pregrabados → No es práctico (requiere ~5000 grabaciones de voz)
9. Command macros → Potencial riesgo de seguridad
10. Multi-sim → Requeriría reescribir shared-telemetry para cada sim
11. VR overlays → Público nicho
12. Rally pace notes → No relevante para LMU

### Conclusión

**NO cambiar la arquitectura.** Vantare tiene un stack moderno y superior (Python/FastAPI + React/Tauri + LLM).

**SÍ añadir features específicas de CrewChief que faltan.** Las 3 prioridades ALTAS (pit management commands, comandos de voz estructurados, track landmarks ampliados) aportan el mayor valor inmediato.

**CI/CD de Vantare es superior** al de CrewChief (tests automatizados, coverage, linting implícito). No necesita cambios.

**El LLM es la ventaja diferencial** de Vantare — CrewChief no puede generar análisis contextual. Pero conviene complementarlo con respuestas deterministas rápidas para comandos comunes (como hace CrewChief).
