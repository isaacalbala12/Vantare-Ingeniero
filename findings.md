# Quality Analysis — Hallazgos Completos

## Resumen

Realizada auditoría completa el 27-mayo-2026 mediante 6 subagentes paralelos cubriendo: seguridad (Python), complejidad, código muerto, cobertura backend, cobertura frontend y Rust.

---

## Seguridad (Python)

### CRITICAL: API Key en git
- **Archivo:** `backend/.env` trackeado en git
- **Evidencia:** `git ls-files backend/.env` → existe
- **Riesgo:** `LLM_API_KEY` expuesta en historial git (resuelto: `.env` fuera del repo)
- **Nota:** Rotar credenciales si el repo fue público en algún momento

### HIGH: CORS sobrepermisivo
- **Archivo:** `backend/src/main.py:260-271`
- **Evidencia:** `allow_methods=["*"]` + `allow_credentials=True`
- **Riesgo:** Conflicto CORS spec + cualquier origen con credenciales

### MEDIUM: 5 try-except-pass silenciosos
- `engine.py:130` - weather_data
- `engine.py:162` - priority lookup
- `engine.py:219` - description lookup
- `engine.py:429` - cancel cleanup
- `spotter.py:28` - evaluate_tick

### Resultados escaneo
- Bandit: 0 issues reales
- Frontend: 0 `dangerouslySetInnerHTML`, `eval()`, `innerHTML`

---

## Complejidad (Python)

### Funciones con CC ≥ C (11+)

| Función | Archivo | CC | Líneas | Prioridad |
|---------|---------|:--:|:------:|:---------:|
| `_process_cycle` | strategy_service.py:164 | 40 | 240 | 🔴 Refactor |
| `_build_ticker_data` | context_builder.py:18 | 30 | 76 | 🟠 Dividir |
| `evaluate_cycle` | engine.py:118 | 29 | 134 | 🟠 Dividir |
| `lifespan` | main.py:57 | 27 | 144 | 🟠 Simplificar |
| `on_lap_completed` | live_context.py:20 | 26 | 125 | 🟡 Extraer |
| `ask_streaming` | llm_client.py:82 | 24 | 97 | 🟡 Extraer |
| `websocket_endpoint` | websocket.py:238 | 22 | 69 | 🟡 Extraer |
| `poll_api` | lmu_api.py:91 | 21 | 65 | 🟡 Extraer |
| `get_race_summary` | strategy_service.py:101 | 21 | 41 | 🟡 Extraer |
| `strategy_sender_loop` | websocket.py:121 | 17 | 51 | 🟡 Extraer |
| `evaluate` | spotter.py:36 | 17 | 96 | 🟡 Extraer |

### Archivos > 300 líneas
- `engine.py` - 496 ⚠️ (modularizar triggers)
- `strategy_service.py` - 473 ⚠️
- `triggers.py` - 354
- `ticker.py` - 354
- `context_builder.py` - 337
- `websocket.py` - 330

---

## Código Muerto

### Vulture (≥80% confianza)
- 1 hallazgo: `RaceState` import en `strategy_service.py:7`

### Ruff F401 (17 imports sin uso)
- `engine.py:5` - `Dict`, `List`
- `formatter.py:12` - `Optional`
- `prompt_templates.py:14` - `Any`, `Dict`, `List`
- `ticker.py:10` - `Any`, `Optional`
- `triggers.py:4` - `Any`, `Dict`
- `main.py:3` - `uuid`
- `messages.py:2` - `Optional`
- `gemini_tts_service.py:6` - `SpeechConfig`, `PrebuiltVoiceConfig`
- `strategy_service.py:7` - `RaceState`
- `broadcaster.py:2` - `asyncio`

### Comentado
- 0 bloques de código comentados

---

## Cobertura Backend

### Total actual: ~13% (src/) | 39% (intelligence/) | 70% (tests seleccionados)

### Por módulo

| Módulo | Cobertura | Prioridad |
|--------|:---------:|:---------:|
| `ticker.py` | 98% | ✅ |
| `spotter.py` | 88% | ✅ |
| `triggers.py` | 88% | ✅ |
| `prompt_templates.py` | 79% | ✅ |
| `health.py` | 100% | ✅ |
| `history.py` | 100% | ✅ |
| `tts.py` | 98% | ✅ |
| `context_builder.py` | 47% | 🟡 |
| `lmu_api.py` | 40% | 🟡 |
| `engine.py` | 0% | 🔴 |
| `live_context.py` | 0% | 🔴 |
| `llm_client.py` | 0% | 🔴 |
| `strategy_service.py` | 0% | 🔴 |
| `websocket.py` | 0% | 🔴 |
| `msgpack_codec.py` | 0% | 🟡 |
| `edge_tts_service.py` | 0% | 🟡 |

### Tests existentes: 24 archivos

---

## Cobertura Frontend

### Tests actuales: 55 (4 archivos)
- `filters.test.ts` - 11 tests
- `audioQueue.test.ts` - 5 tests
- `configStore.test.ts` - 26 tests
- `msgpack.test.ts` - 13 tests

### Módulos sin test
| Archivo | Prioridad | Complejidad |
|---------|:---------:|:-----------:|
| `useWebSocket.ts` | 🔴 Alta | 460 líneas, lógica crítica |
| `appStore.ts` | 🔴 Alta | Estado global |
| `api.ts` | 🔴 Alta | Llamadas HTTP |
| `usePTT.ts` | 🟡 Media | Lógica PTT |
| `useAudioCapture.ts` | 🟡 Media | Captura audio |
| `RadioOverlay.tsx` | 🟡 Media | UI principal |
| `ConfigTab.tsx` | 🟢 Baja | Configuración |
| `ChatBubble.tsx` | 🟢 Baja | UI simple |

---

## Rust

### main.rs (220 líneas)
- 4 plugins Tauri: opener, shell, global-shortcut, websocket
- Sidecars: BackendChild + SidecarChild con Mutex<Option<CommandChild>>
- Health check TCP cada 5s al puerto 8008
- System tray con "Ocultar" y "Salir"
- Cleanup de sidecars en CloseRequested

### Unwraps encontrados (7 total)
| Línea | Código | Riesgo |
|:-----:|--------|:------:|
| 132 | `parse().unwrap()` | Bajo (IP hardcodeada) |
| 155 | `default_window_icon().unwrap()` | **CRÍTICO** |
| 161 | `lock().unwrap()` | Seguro (Mutex local) |
| 166 | `lock().unwrap()` | Seguro (Mutex local) |
| 202 | `lock().unwrap()` | Seguro (Mutex local) |
| 207 | `lock().unwrap()` | Seguro (Mutex local) |
| 216 | `expect("error while running tauri")` | Aceptable (entry point) |

### Seguridad
- `csp: null` → Sin protección XSS en WebView2
- `shell:allow-execute` → Permite ejecución arbitraria desde JS

### Compilación
- `cargo check` falla en Linux (normal, falta binary backend)
- Funciona correctamente en Windows con los sidecars compilados

---

## Deprecation Warnings (Python 3.14+)
- `lmu_data.py:412-464` - 4 estructuras LMU que requieren `_layout_ = 'ms'` en Python 3.19
- No urgente pero monitorear
