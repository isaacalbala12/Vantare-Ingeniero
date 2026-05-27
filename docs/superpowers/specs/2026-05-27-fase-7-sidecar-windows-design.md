# Fase 7: Sidecar Windows + Integración Tauri

**Fecha:** 27 mayo 2026
**Estado:** Aprobado (v2 — corregida)
**Autor:** Brainstorming session

## Resumen

Empaquetar backend + sidecar como dos ejecutables independientes. Tauri spawna ambos en Windows. El sidecar lee shared memory de LMU y envía datos al backend vía WebSocket localhost. El LLM sigue remoto vía Cloudflare tunnel.

## Arquitectura

```
Windows (todo local excepto LLM):

Tauri app
├── spawn → vantare-engine.exe (FastAPI + LLM + TTS + WS hub)
│              PyInstaller --onedir
│              Puerto :8008
│              GET /health cada 5s desde Tauri
│
├── spawn → strategy-sidecar.exe (LMU shared memory reader)
│              PyInstaller --onedir
│              WS → ws://127.0.0.1:8008/ws/sidecar
│              Envía strategy_frame cada 2s
│
└── Gestión de procesos:
    ├── Tauri monitorea backend vía health check TCP :8008
    ├── Backend detecta caída del sidecar vía WS disconnect
    ├── Auto-reinicio: backend (hasta 3 intentos Tauri)
    └── Cleanup: matar ambos procesos al cerrar Tauri
         │
         └── Cloudflare tunnel → LiteLLM → Hipfire (LLM remoto)
```

### Principios

- **Dos procesos independientes:** Cada uno con su propio event loop asyncio. Sin bloqueo mutuo.
- **Comunicación vía localhost WebSocket:** Sub-ms latencia, sin riesgo de bloqueo del event loop.
- **Aislamiento de fallos:** Si el sidecar crashea (C extension bug), el backend sigue vivo y viceversa.
- **PyInstaller --onedir:** Arranque instantáneo, sin extracción a temp directory.
- **LMU_AVAILABLE env var:** Si true → shared memory real (Windows). Si false/ausente → simulado (Linux dev).

## Por qué dos procesos (no fusionados)

Decisión revisada versus el diseño v1. Razones:

1. **process_cycle() es síncrono.** Dentro de una tarea asyncio compartida con WebSocket/LLM, bloquearía el event loop ~20-50ms cada 2s.
2. **Tauri soporta múltiples sidecars nativamente.** No hay complejidad extra.
3. **Aislamiento de fallos.** Bug en C extensions de shared memory no tumba el backend.
4. **Startup independiente.** El backend arranca en segundos; el sidecar espera a que LMU esté disponible.
5. **Debugging.** Cada proceso se puede correr standalone.

## Comunicación

```
strategy-sidecar.exe                    vantare-engine.exe
       │                                      │
       │  WS connect ws://127.0.0.1:8008/ws/sidecar
       │─────────────────────────────────────→│
       │                                      │
       │  WS send (cada 2s):                  │
       │  {                                    │
       │    "event": "strategy_frame",         │
       │    "data": {                          │
       │      "advice": {...},                 │
       │      "frame": {...},                  │
       │      "events": [...]                  │
       │    }                                  │
       │  }                                    │
       │─────────────────────────────────────→│
       │                                      │
       │  Si WS disconnect → esperar 2s       │
       │  y reconectar (backoff exponencial)   │
       │                                      │
       │  Si reconexión exitosa → reanudar     │
```

## Empaquetado

### backend/build.py → vantare-engine.exe
- `--onedir --noconsole --name=vantare-engine`
- Incluye: src/, shared-telemetry, shared-strategy, C extensions .pyd
- Salida: `backend/dist/vantare-engine/`

### sidecar/build.py → strategy-sidecar.exe
- `--onedir --noconsole --name=strategy-sidecar`
- Incluye: src/sidecar/, shared-telemetry, shared-strategy, C extensions .pyd
- Salida: `sidecar/dist/strategy-sidecar/`

## Tauri

**tauri.conf.json:**
```json
"externalBin": [
    "../backend/dist/vantare-engine",
    "../sidecar/dist/strategy-sidecar"
]
```

**main.rs:**
- Spawn secuencial: backend primero, sidecar después
- Health check vía `TcpStream::connect_timeout("127.0.0.1:8008", 2s)` cada 5s
- Matar ambos procesos en CloseRequested y menú "Salir"
- En debug mode: skip spawn, instrucciones para ejecución manual

## Health Check

```
Tauri → TCP :8008 cada 5s
  ├── Conecta → failures=0
  └── 3 fallos seguidos → emitir evento "backend-crashed"
       └── (futuro: reinicio automático)
```

## Archivos

| Archivo | Rol |
|---------|-----|
| `backend/build.py` | Build script para vantare-engine.exe |
| `backend/src/main.py` | FastAPI entrypoint (sin cambios estructurales) |
| `backend/src/routers/websocket.py` | Handler /ws/sidecar (nuevo o existente) |
| `sidecar/build.py` | Build script para strategy-sidecar.exe |
| `sidecar/src/sidecar/main.py` | Sidecar entrypoint (sin cambios, ya funciona) |
| `sidecar/src/sidecar/strategy_runner.py` | Lector shared memory + estrategia (sin cambios) |
| `sidecar/src/sidecar/event_detector.py` | Detector de eventos (sin cambios) |
| `frontend/src-tauri/tauri.conf.json` | externalBin con dos entries |
| `frontend/src-tauri/src/main.rs` | Spawn dual + health check |
| `frontend/src-tauri/capabilities/default.json` | Permisos shell |

## Deuda Técnica

- **REST API de LMU (brake wear):** El sidecar no incluye poller REST a `localhost:6397`. Brake wear se reporta como 0.0. Pendiente para cuando se pueda probar contra datos reales.
- **Modo "solo local":** Futuro modo donde spotter + estrategia + TTS funcionan sin LLM. Requiere hacer opcional la conexión al LLM remoto.
- **Auto-reinicio del backend:** Tauri detecta caída pero no reinicia automáticamente (post-MVP).
