# Arquitectura del shell desktop — Vantare Ingeniero IA

> **Fecha:** 2026-06-07  
> **Estado:** Tauri 2 (actual) · Electron evaluado como alternativa  
> **Alcance:** Patrones del mercado sim-racing, stack actual, análisis Tauri vs Electron, plan de migración

---

## TL;DR

- El **frontend ya es React**; Rust/Tauri es solo el **shell nativo** (~220 líneas útiles).
- El patrón de mercado para apps “web + Python backend” es **Electron** (redwave-overlays, LMU Telemetry Lab).
- El patrón LMU “puro Python” es **PySide/Qt** (TinyPedal) — no recomendado para Vantare por la capa LLM/voz.
- **Migración a Electron:** viable en ~1–2 semanas; el 95% del código no cambia.
- **Audio ducking** requiere puente nativo en cualquier shell (hoy: Rust WASAPI).

---

## 1. Patrón común del mercado

```
Sim (LMU / iRacing / rF2)
  └─ shared memory / SDK / REST :6397
       └─ proceso lector (Python, Rust, C++)
            └─ UI overlay (Qt / C++ / Electron / Tauri)
```

**Requisito universal:** juego en **borderless** o **windowed** (fullscreen exclusivo oculta overlays).

### Referencias analizadas

| Proyecto | UI | Telemetría | Overlay | Empaquetado |
|----------|-----|------------|---------|-------------|
| [TinyPedal](https://github.com/TinyPedal/TinyPedal) | Python + PySide2/Qt | `pyLMUSharedMemory` | Ventanas Qt transparentes, tray | py2exe |
| [iFL03](https://github.com/SemSodermans31/iFL03) | C++ Direct2D + CEF (solo settings) | iRacing SDK | Overlays nativos C++ | VS + Inno Setup |
| [redwave-overlays](https://github.com/onesch/redwave-overlays) | Electron + React | Python FastAPI + pyirsdk | `BrowserWindow` transparente | electron-builder |
| [lmu-pitwall](https://github.com/Swizzjack/lmu-pitwall) | React embebido | Rust + REST :6397 | Segundo monitor (no overlay in-game) | Single exe |
| [LMU-Telemetry-Lab](https://github.com/rabbit20031225/LMU-Telemetry-Lab) | Electron + React + FastAPI | LMU files + live | Desktop modular | Installer |
| **CrewChiefV4** | C# (.NET) | Adapters por sim | Ingeniero de voz (no overlay HUD) | Installer + updater |

### Tres familias arquitectónicas

| Familia | Ejemplo | Ventaja | Coste |
|---------|---------|---------|-------|
| **A — Qt monolito** | TinyPedal | Simple, probado LMU, un proceso | UI menos flexible |
| **B — C++ nativo** | iFL03 | Máximo rendimiento | Muy caro de mantener |
| **C — Web shell + backend** | redwave, **Vantare** | React + LLM/TTS separados | Shell frágil (Tauri/Electron) |

Vantare encaja en **familia C** porque no es solo HUD: incluye LLM, TTS, spotter, triggers y backend FastAPI.

---

## 2. Stack actual de Vantare

### Target dev/prod (Task 49 — native telemetry, sin sidecar)

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND — Tauri 2 + React 19 + Vite + Zustand   │
│  PTT, Speech Recognition, TTS queue, WebSocket    │
└──────────────────────┬──────────────────────────────┘
                       │ ws://127.0.0.1:8008/ws
┌──────────────────────▼──────────────────────────────┐
│  BACKEND — FastAPI (Python)                         │
│  TelemetryReader @ 20 Hz (shared memory in-process) │
│  StrategyService.snapshot_frame → spotter + CC      │
│  IntelligenceEngine, TTS, LLM                       │
└──────────────────────▲──────────────────────────────┘
                       │ LMU_Data (shared memory)
                 Le Mans Ultimate
```

**Dev (2 procesos):** `scripts/dev.ps1` o backend + `npm run tauri dev`.  
**Release:** Tauri spawnea solo `backend.exe` con `VANTARE_NATIVE_TELEMETRY=1`.

### Legacy (pre-Task 49 — sidecar, **removed 2026-06-08**)

El sidecar strategy (`/ws/sidecar`, `strategy-sidecar.exe`) fue eliminado en Task 49-S9. El diagrama histórico ya no aplica; ver commit/plan `2026-06-08-task49-sidecar-removal-completion.md`.

### Qué hace Rust/Tauri (superficie pequeña)

| Capacidad | Implementación | Archivos |
|-----------|----------------|----------|
| Ventana overlay | `tauri.conf.json` | transparent, alwaysOnTop, frameless |
| System tray | `main.rs` | hide / quit |
| PTT global | `plugin-global-shortcut` | `useHotkey.ts` |
| Spawn backend (release) | `main.rs` | `backend.exe` + `VANTARE_NATIVE_TELEMETRY=1` |
| Audio ducking WASAPI | `audio_duck.rs` | `invoke("duck_lmu")` → `audioQueue.ts` |
| Abrir URLs | `plugin-opener` | `updateChecker.ts` |

**Archivos React con dependencia Tauri:** 6 (`App.tsx`, `useHotkey.ts`, `audioQueue.ts`, `updateChecker.ts`, `SystemTrayMenu.tsx`).

### Modo desarrollo vs release

| Modo | Backend | App |
|------|---------|-----|
| **Debug (dev)** | Manual: `.\scripts\dev.ps1` | `npm run tauri dev` |
| **Release** | Tauri spawna `backend.exe` | Instalador |

---

## 3. Problemas conocidos (Tauri / WebView2)

| Síntoma | Causa probable | Mitigación aplicada |
|---------|----------------|---------------------|
| App “no responde” al arrancar | `getUserMedia()` / `global-shortcut` / imports Tauri síncronos bloquean WebView2 | Sin prewarm de mic; shortcuts @ +4s; health @ +2s; imports Tauri lazy |
| Crash `0xcfffffff` | WebView2 / cierre anómalo | Probar `npm run tauri build` (release); fallback browser `:1420` |
| Pit limiter spam | Spotter @ 20Hz sin debounce | Edge detection + grace 1.5s en `spotter.py` |
| `mSpeedLimiterActive` false en boxes | LMU marca `in_pits` antes del limiter | Leer también `mSpeedLimiter` |

### Workaround inmediato si Tauri sigue colgando

1. Arrancar backend + sidecar (terminales 1–3).
2. `cd frontend && npm run dev` (solo Vite, sin Tauri).
3. Abrir `http://localhost:1420` en Chrome/Edge.
4. Probar telemetría, spotter, perfiles; PTT con teclado local (ventana enfocada).

Útil para QA de lógica sin depender de WebView2.

---

## 4. Análisis: migración Tauri → Electron

### Por qué considerarlo

- Mismo patrón que **redwave-overlays** (Electron + Python FastAPI).
- Crashes en dev apuntan a **WebView2**, no a React.
- Superficie Tauri pequeña → migración acotada.
- Dev más simple: sin compilación Rust en cada arranque.

### Mapeo feature a feature

| Feature | Tauri (actual) | Electron |
|---------|----------------|----------|
| Overlay window | `tauri.conf.json` | `BrowserWindow` (`transparent`, `alwaysOnTop`, `frame: false`) |
| System tray | `TrayIconBuilder` | `Tray` + `Menu` |
| PTT global | `plugin-global-shortcut` | `globalShortcut` en main process |
| Spawn procesos | `shell.command().spawn()` | `child_process.spawn()` |
| IPC duck | `invoke("duck_lmu")` | `ipcMain` + `contextBridge` |
| Abrir URL | `plugin-opener` | `shell.openExternal` |
| Packaging | `tauri build` + resources | `electron-builder` + `extraResources` |

### Audio ducking (único punto no trivial)

Hoy: Rust WASAPI en `audio_duck.rs`.

Opciones en Electron:

| Opción | Descripción |
|--------|-------------|
| **A** | Extender sidecar Python con `pycaw` |
| **B** | Paquete npm (`loudness`, etc.) en main process |
| **C** | Mini `duck_lmu.exe` (extraer lógica Rust actual) |
| **D** | Omitir temporalmente en POC |

**Recomendación:** C (corto plazo) o A (sin binarios extra).

### Qué NO cambia en migración

- React 19, Vite, Tailwind, Zustand, Vitest
- `useWebSocket`, hooks PTT, cola TTS
- Backend FastAPI, sidecar, `shared-telemetry`, `shared-strategy`
- Protocolo WebSocket, endpoints REST

### Comparativa

| Criterio | Tauri | Electron |
|----------|-------|----------|
| Estabilidad Windows | WebView2 variable | Chromium embebido, más estable |
| Tamaño instalador | ~50–80 MB + Python | ~150–200 MB + Python |
| Toolchain dev | Rust + Node | Solo Node |
| Tiempo 1er arranque dev | 1–2 min (compile Rust) | ~10 s |
| RAM idle | ~80–120 MB | ~150–250 MB |
| Patrón mercado sim web | Minoritario | redwave, irdashies, LMU Telemetry Lab |

### Plan de migración por fases

#### Fase 0 — POC (2–3 días)
- [ ] `electron/main.js` + `BrowserWindow` overlay
- [ ] Cargar `http://localhost:1420` en dev
- [ ] Tray básico + quit
- [ ] Validar estabilidad sobre LMU

#### Fase 1 — Paridad funcional (3–4 días)
- [ ] `globalShortcut` PTT
- [ ] `platform.ts` adapter (Tauri / Electron / Web)
- [ ] Spawn backend + sidecar en release
- [ ] Puente audio ducking

#### Fase 2 — Packaging (2–3 días)
- [ ] `electron-builder` + NSIS/Inno
- [ ] `extraResources`: backend.exe, strategy-sidecar.exe
- [ ] Iconos, auto-update opcional

#### Fase 3 — Limpieza (1 día)
- [ ] Eliminar `src-tauri/`
- [ ] Quitar `@tauri-apps/*`
- [ ] Actualizar scripts y AGENTS.md

**Estimación total:** 8–12 días desarrollador.

### Decisión recomendada

1. **Ahora:** seguir con Tauri + fixes de estabilidad.
2. **Paralelo:** branch `electron-poc` (Fase 0).
3. **Decidir** tras POC estable sobre LMU.
4. **No big-bang:** mantener Tauri hasta paridad Electron en release.

---

## 5. Comandos — stack de desarrollo

### Arranque manual (Windows, modo debug)

```powershell
# Terminal 1 — Backend
cd backend
python run_dev.py

# Terminal 2 — LMU dummy REST (opcional si no usas REST real)
.\scripts\run-lmu-dummy.ps1

# Terminal 3 — Sidecar (requiere LMU abierto)
cd sidecar\src
python -m sidecar.main

# Terminal 4 — App Tauri
cd frontend
npm run tauri dev
```

### Alternativa browser (sin Tauri)

```powershell
# Terminales 1–3 igual; luego:
cd frontend
npm run dev
# Abrir http://localhost:1420
```

En browser: PTT global y ducking no funcionan; útil para probar UI/WS.

### Smoke checks

```powershell
# Health
Invoke-RestMethod http://127.0.0.1:8008/health

# Verificación R3 automatizada
python scripts/verify_r3.py

# WebSocket telemetry
cd backend
python qa_test_script.py
```

### Requisitos LMU

- Juego en **borderless** o **windowed**
- **Enable Plugins** ON (Settings → Gameplay)
- Windows: API LMU built-in sin plugin extra
- rF2: plugin TheIronWolf en `Bin64\Plugins`

---

## 6. Verificación QA (referencia)

| Evidencia | Ubicación |
|-----------|-----------|
| R3 automated (F9–F12) | `.omo/evidence/final-qa-r3/wave10-r3-verification.md` |
| Script reproducible | `scripts/verify_r3.py` |
| Tests backend | `412 passed` (jun 2026) |
| Tests frontend | `92 passed` vitest |

### Checklist manual en pista

- [ ] Telemetría en vivo (vel, vuelta, pos, fuel)
- [ ] Indicadores BACKEND / LMU / LLM en verde
- [ ] Sidecar conectado (`health.sidecar.connected` tras strategy frames)
- [ ] Spotter (proximidad, banderas)
- [ ] PTT → LLM → TTS
- [ ] Perfiles (Config → guardar/cargar)
- [ ] Pit limiter: una sola alerta al entrar mal, no spam

---

## 7. Documentos relacionados

| Documento | Tema |
|-----------|------|
| `agents.md` | Overview arquitectura y comandos |
| `docs/crewchief-comparison.md` | Comparativa funcional CrewChief |
| `docs/ai/technical-debt-rust-migration.md` | Por qué NO migrar backend/sidecar a Rust |
| `sidecar/README.md` | Sidecar strategy + reconexión WS |
| `.omo/evidence/final-qa-r3/` | Verificación release R3 |

---

## Changelog

| Fecha | Cambio |
|-------|--------|
| 2026-06-07 | Documento inicial: patrones mercado, stack actual, análisis Electron, plan migración, comandos dev |
| 2026-06-07 | Mitigaciones WebView2: mic lazy, shortcuts diferidos, ConfigTab sin getUserMedia al montar |
