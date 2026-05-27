# Fase 7: Sidecar Windows + Integración Tauri

**Fecha:** 27 mayo 2026
**Estado:** Aprobado
**Autor:** Brainstorming session

## Resumen

Unificar el sidecar de estrategia dentro del backend FastAPI y empaquetar todo como un único ejecutable (`vantare-engine.exe`) que Tauri gestiona como proceso hijo en Windows. El LLM sigue remoto vía Cloudflare tunnel.

## Arquitectura

```
Windows (todo local excepto LLM):

Tauri app
  └── spawn → vantare-engine.exe (PyInstaller --onefile --noconsole)
                ├── FastAPI (main.py)
                ├── backend/src/sidecar/        ← movido de sidecar/src/sidecar/
                │   ├── strategy_runner.py      (lee shared memory LMU)
                │   └── event_detector.py       (detecta cambios estado)
                ├── WebSocket hub (frontend)
                └── GET /health (para health check Tauri)
                     │
                     └── Cloudflare tunnel → LiteLLM → Hipfire (LLM remoto)
```

### Principios

- **Un solo ejecutable:** El sidecar NO es un proceso separado. Vive dentro de `vantare-engine.exe`.
- **Comunicación directa:** El sidecar module llama a `StrategyService` en memoria. Sin WebSocket interno.
- **Detección de LMU:** Variable de entorno `LMU_AVAILABLE=true/false`. Si true → shared memory real. Si false/ausente → simulado (modo dev actual).
- **Tauri gestiona un solo proceso:** health check vía `GET /health`, reinicio si no responde.

## Cambios Estructurales

### 1. Mover sidecar a backend/

```
ANTES:
sidecar/
├── src/sidecar/
│   ├── main.py
│   ├── strategy_runner.py
│   ├── event_detector.py
│   └── __init__.py
├── pyproject.toml
└── README.md

DESPUÉS:
backend/src/sidecar/            ← MOVER
├── strategy_runner.py          ← (sin main.py, se integra en backend)
├── event_detector.py
└── __init__.py
```

Eliminar carpeta `sidecar/` raíz.

### 2. Integración en backend/main.py

```python
# pseudocódigo
LMU_AVAILABLE = os.getenv("LMU_AVAILABLE", "false").lower() == "true"

if LMU_AVAILABLE:
    reader = TelemetryReader(offline=False, poll_rate=0.05)
    reader.start()
    strategy_runner = StrategyRunner(reader)
    event_detector = StateChangeDetector()
    app.state.sidecar_runner = strategy_runner
    app.state.sidecar_detector = event_detector
    # Arrancar loop interno cada 2s (sin WebSocket)
else:
    reader = TelemetryReader(offline=True)  # modo dev actual
```

### 3. Comunicación interna

El sidecar ya no envía WebSocket. En su lugar:

```python
# Cada 2s dentro del backend (asyncio loop)
runner.process_cycle()
if runner.latest_frame and runner.latest_advice:
    events = detector.detect(runner.latest_frame)
    # Llamada directa a StrategyService
    strategy_service.update(runner.latest_advice, runner.latest_frame, events)
    # RAG: store_events(events)
```

### 4. PyInstaller

- Archivo: `backend/build.py`
- Modo: `--onefile --noconsole`
- Output: `backend/dist/vantare-engine.exe`
- C extensions de `pyLMUSharedMemory` → incluir como `binaries` en el spec
- shared-strategy → incluir como `datas`

### 5. Tauri

**tauri.conf.json:**
- `"externalBin"`: renombrar `"backend"` → `"vantare-engine"`
- Ajustar ruta relativa

**main.rs:**
- Renombrar `shell.sidecar("backend")` → `shell.sidecar("vantare-engine")`
- El resto del patrón (spawn en release, skip en dev, kill al cerrar) se mantiene

**capabilities/default.json:**
- Añadir `"shell:allow-spawn"` si no existe

### 6. Health Check (simplificado)

Un solo proceso → un solo health check:

```
Tauri → GET http://127.0.0.1:8008/health cada 5s
  ├── Si 200 OK → todo bien
  └── Si timeout/error → reiniciar vantare-engine.exe (máx 3 intentos, backoff)
```

## Deuda Técnica Documentada

### REST API de LMU (brake wear, aero, suspension, weather)

El sidecar no incluye poller REST a `localhost:6397`. El brake wear se envía como 0.0. El motor de estrategia calcula sobre datos incompletos de frenos. Pendiente: mini poller HTTP en `strategy_runner.py` que consuma `/rest/garage/UIScreen/RepairAndRefuel` y `/rest/sessions/weather`.

### Modo "solo local"

Futuro modo donde la app funciona completamente sin conexión a internet: spotter + estrategia + TTS local sin LLM. Requiere separar la lógica de LLM para que sea opcional.

## Archivos Afectados

| Archivo | Cambio |
|---------|--------|
| `sidecar/src/sidecar/` → `backend/src/sidecar/` | Mover (3 archivos) |
| `sidecar/` (raíz) | Eliminar |
| `backend/src/main.py` | Añadir detección LMU_AVAILABLE + integración sidecar |
| `backend/build.py` | Nuevo — spec PyInstaller |
| `backend/pyproject.toml` | Añadir dependencias sidecar |
| `frontend/src-tauri/tauri.conf.json` | Renombrar externalBin |
| `frontend/src-tauri/src/main.rs` | Renombrar sidecar + health check |
| `frontend/src-tauri/capabilities/default.json` | Permisos shell |
| `backend/tests/` | Tests nuevos para integración sidecar |

## No Cambia

- LLM sigue remoto vía Cloudflare tunnel
- Frontend React/TypeScript no cambia
- Estrategia determinista (`shared-strategy`) no cambia
- Formato ticker, RAG, LiveContext no cambian
