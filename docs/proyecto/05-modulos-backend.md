# 05 — Módulos backend

Raíz: `backend/src/`

---

## Punto de entrada

| Archivo | Rol |
|---------|-----|
| `main.py` | FastAPI app, lifespan, spawn `race_loop` + `voice_loop`, routers |
| `config.py` | Settings desde `.env` (Pydantic) |
| `version.py` | `APP_VERSION`, `GITHUB_REPO` |

---

## `intelligence/` — cerebro de carrera

| Módulo | Responsabilidad |
|--------|-----------------|
| `engine.py` | **IntelligenceEngine** — triggers @0.5Hz, streaming LLM, preemption, proactive cycle |
| `triggers.py` | 12+ condiciones (fuel, SC, tyres, hybrid, weather, pit window, …) |
| `spotter.py` | Orquestación spotter |
| `spotter_geometry.py` | Geometría cartesiana proximidad |
| `spotter_adapter.py` | Adaptador telemetría → spotter |
| `spotter_state.py` | Estado persistente spotter |
| `cartesian_spotter.py` | Lógica CC-style cartesiana |
| `personality_pack.py` | Perfiles tono/voz + runtime (sweary, proactivity, pearls) |
| `phrase_picker.py` | Selección variantes frases `\|` por perfil |
| `phrase_catalog.py` | Catálogo mergeado defaults + usuario (v0.4) |
| `pearls_of_wisdom.py` | Perlas proactivas con sampling por frecuencia |
| `pilot_ptt_agent.py` | Agente PTT piloto → LLM |
| `pilot_tool_executor.py` | Tools deterministas PTT (base v0.7) |
| `llm_client.py` | Cliente streaming httpx |
| `prompt_templates.py` | Plantillas system/user |
| `live_context.py` | Contexto sesión en vivo |
| `commentary_orchestrator.py` | LEGACY batch LLM (ruta B; gate proactivity) |
| `verbosity_controller.py` | Filtro verbosidad eventos |
| `event_registry.py` | Definiciones event_id → priority, verbosity_min |
| `flags_monitor.py`, `rain_monitor.py`, `fuel_safety.py`, … | Monitores proactivos wave1 |
| `proactive_monitors.py` | Ciclo monitores |
| `damage_report.py`, `penalty_tracker.py`, `pit_prediction.py` | Dominios específicos |

### `intelligence/crewchief_events/`

Port nativo CrewChief — **evaluación @20Hz en race loop global**.

```
crewchief_events/
├── game_state.py          # Estado sesión CC
├── lap_edge.py            # Detección vuelta completada
├── cutover_registry.py    # Eventos activos post-cutover
├── modules/
│   ├── fuel.py, flags.py, lap_times.py, pearls.py
│   ├── damage.py, pit_stops.py, tyre_monitor.py
│   ├── opponent_messages.py, session_end.py, …
│   └── ( ~25 módulos )
```

Cada módulo implementa `evaluate(ctx) -> list[CrewChiefMessage]`.

---

## `voice/` — reproducción audio

| Módulo | Rol |
|--------|-----|
| `service.py` | `voice_loop` — asyncio + pygame |
| `voice_queue.py` | Cola prioridad |
| `moderator.py` | Reglas interrupción / defer |
| `tts_manager.py` | Routing Edge/Gemini/Piper/ElevenLabs |
| `spotter_cache.py` | Precalentamiento WAV spotter |
| `play_command.py` | Comando play unificado |
| `tts_routing.py` | Routing por rol engineer/spotter |
| `player_pygame.py` | Backend audio |
| `ducking.py` | Ducking LMU (opcional) |

---

## `services/`

| Servicio | Rol |
|----------|-----|
| `lmu_api.py` | REST LMU :6397 (pit menu read; write v0.8) |
| `strategy_service.py` | Wrapper shared-strategy |
| `edge_tts_service.py` | Microsoft Edge TTS |
| `gemini_tts_service.py` | Google Gemini TTS |
| `asr_service.py` | Transcripción PTT (faster-whisper) |

---

## `routers/`

| Router | Endpoints |
|--------|-----------|
| `websocket.py` | `/ws` — telemetría, config, eventos |
| `health.py` | `/health` |
| `tts.py` | `/tts` — síntesis (legacy/auxiliar) |
| `phrases.py` | `/phrases` — CRUD frases usuario (v0.4) |
| `transcribe.py` | ASR upload |
| `llm.py` | Utilidades LLM |

---

## `persistence/`

| Módulo | Rol |
|--------|-----|
| `phrase_store.py` | Merge/save `user_phrases.json` AppData |
| `event_store.py` | Historial eventos |
| `history_store.py` | Consumo fuel por vuelta |

---

## `data/`

| Archivo | Contenido |
|---------|-----------|
| `spotter_phrases_es.json` | Frases spotter ES |
| `trigger_phrases_es.json` | Triggers P0 ES |

(v0.6 añadirá `*_en.json`)

---

## `models/messages.py`

Modelos Pydantic WebSocket: `AlertMessage`, `AdviceEndMessage`, `CommentaryEndMessage`, `CommentaryEndMessage`, eventos playback, etc.

---

## `race/`

| Módulo | Rol |
|--------|-----|
| `tick_loop.py` / telemetría hub | Loop carrera 20 Hz |
| Integración spotter + CC en un tick |

---

## Tests

`backend/tests/` — ~40+ archivos incluyendo:

- `test_spotter*.py`, `test_cartesian_spotter.py`
- `test_voice_loop.py`, `test_preemption.py`
- `test_phrase_store.py`, `test_phrases_router.py`
- `test_personality_pack.py`, `test_pearls_*.py`
- `test_config_sync_ws.py`
- `test_engine*.py`, `test_*_wave1.py`

Fixtures spotter: `tests/fixtures/spotter/`.

---

## Shared libraries (no UI)

### `shared-telemetry/`
- `TelemetryReader` — thread daemon mmap LMU
- Modelos Pydantic vehículo/sesión/vuelta

### `shared-strategy/`
- Cálculos fuel, tyres, brakes, hybrid, pit window, competitors

**Regla roadmap:** no editar `shared-telemetry/` hasta v1.1.
