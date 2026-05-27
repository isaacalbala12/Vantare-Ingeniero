# Fase 7: Sidecar Windows + Integración Tauri — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Empaquetar backend + sidecar como dos ejecutables independientes, gestionados por Tauri en Windows. El sidecar lee shared memory de LMU y envía datos al backend vía localhost WebSocket.

**Arquitectura:** Dos procesos separados, cada uno con su propio event loop asyncio. Comunicación vía WebSocket localhost (sub-ms latencia). Tauri spawna ambos al arrancar. PyInstaller `--onedir` para arranque instantáneo.

```
Tauri app
├── spawn → vantare-engine.exe (FastAPI + LLM + TTS + WS hub)
│              └── puerto :8008, REST + WebSocket
│              └── GET /health cada 5s desde Tauri
│
├── spawn → strategy-sidecar.exe (LMU shared memory reader)
│              └── WS → ws://127.0.0.1:8008/ws/sidecar
│              └── Envía strategy_frame cada 2s
│
└── Health: backend monitorea, Tauri monitorea backend
    └── Si sidecar se cae → backend detecta WS disconnect → espera reconexión
    └── Si backend se cae → Tauri detecta health check → reinicia
```

**Tech Stack:** Python 3.12+, FastAPI, PyInstaller 6+, Tauri 2 + Rust, websockets, shared-telemetry (C extensions)

---

### Task 1: build.py para backend (vantare-engine.exe)

**Files:**
- Modify: `backend/build.py`
- Add: `backend/.gitignore` entries

- [ ] **Step 1: Reescribir build.py con --onedir**

```python
"""
Build script para empaquetar backend FastAPI como vantare-engine.exe.
Uso: cd backend && pyinstaller build.py
"""
import sys
from pathlib import Path

import PyInstaller.__main__

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "src"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

args = [
    "--onedir",                          # Arranque instantáneo (no temp extract)
    "--noconsole",                       # Sin ventana de terminal
    "--name=vantare-engine",
    "--add-data", f"{SHARED_TELEMETRY}{Path.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{Path.pathsep}shared_strategy",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
    "--distpath=./dist",
    "--workpath=./build",
]

# Incluir .pyd de pyLMUSharedMemory si existen (Windows build)
PYLMU_DIR = SHARED_TELEMETRY / "shared_telemetry" / "pyLMUSharedMemory"
for pyd_file in PYLMU_DIR.glob("*.pyd"):
    args.extend(["--add-binary", f"{str(pyd_file)}{Path.pathsep}shared_telemetry/pyLMUSharedMemory"])

args.append("src/main.py")

PyInstaller.__main__.run(args)
```

- [ ] **Step 2: Actualizar backend/.gitignore**

```gitignore
# backend/.gitignore (añadir al existente)
dist/
build/
*.spec
```

- [ ] **Step 3: Verificar sintaxis**

```bash
cd backend && python -c "import ast; ast.parse(open('build.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/build.py backend/.gitignore
git commit -m "feat: backend PyInstaller build.py (--onedir)"
```

---

### Task 2: build.py para sidecar (strategy-sidecar.exe)

**Files:**
- Create: `sidecar/build.py`

- [ ] **Step 1: Crear build.py para el sidecar**

```python
"""
Build script para empaquetar el sidecar de estrategia como strategy-sidecar.exe.
Uso: cd sidecar && pyinstaller build.py
"""
from pathlib import Path

import PyInstaller.__main__

SIDECAR_SRC = Path(__file__).resolve().parent / "src"
REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "src"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

args = [
    "--onedir",
    "--noconsole",
    "--name=strategy-sidecar",
    "--add-data", f"{SHARED_TELEMETRY}{Path.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{Path.pathsep}shared_strategy",
    "--distpath=./dist",
    "--workpath=./build",
]

# Incluir .pyd de pyLMUSharedMemory
PYLMU_DIR = SHARED_TELEMETRY / "shared_telemetry" / "pyLMUSharedMemory"
for pyd_file in PYLMU_DIR.glob("*.pyd"):
    args.extend(["--add-binary", f"{str(pyd_file)}{Path.pathsep}shared_telemetry/pyLMUSharedMemory"])

args.append("src/sidecar/main.py")

PyInstaller.__main__.run(args)
```

- [ ] **Step 2: Añadir sidecar/.gitignore**

```gitignore
# sidecar/.gitignore
dist/
build/
*.spec
```

- [ ] **Step 3: Verificar sintaxis**

```bash
cd sidecar && python -c "import ast; ast.parse(open('build.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add sidecar/build.py sidecar/.gitignore
git commit -m "feat: sidecar PyInstaller build.py (--onedir)"
```

---

### Task 3: Configurar Tauri para dos sidecars

**Files:**
- Modify: `frontend/src-tauri/tauri.conf.json`
- Modify: `frontend/src-tauri/src/main.rs`
- Modify: `frontend/src-tauri/capabilities/default.json`

- [ ] **Step 1: Leer tauri.conf.json**

```bash
cat frontend/src-tauri/tauri.conf.json | grep -A 5 externalBin
```

- [ ] **Step 2: Añadir ambos ejecutables a externalBin**

```json
"externalBin": [
    "../backend/dist/vantare-engine",
    "../sidecar/dist/strategy-sidecar"
],
```

- [ ] **Step 3: Reescribir main.rs para spawn de ambos procesos**

```rust
// frontend/src-tauri/src/main.rs
// Cambios clave respecto al actual:

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_websocket::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                println!("[Rust] MODO DEBUG: Sidecars desactivados.");
                println!("[Rust] Ejecutar manualmente:");
                println!("  Backend:  python backend/run_dev.py");
                println!("  Sidecar:  python sidecar/src/sidecar/main.py");
                app.manage(BackendChild(Mutex::new(None)));
                app.manage(SidecarChild(Mutex::new(None)));
            } else {
                let shell = app.shell();
                
                // 1. Spawn backend
                println!("[Rust] Iniciando vantare-engine...");
                let backend_child = match shell.sidecar("vantare-engine") {
                    Ok(cmd) => cmd.env("PORT", "8008").spawn().ok(),
                    Err(e) => {
                        eprintln!("[Rust] Error resolving vantare-engine: {:?}", e);
                        None
                    }
                };
                
                if let Some((mut rx, child)) = backend_child {
                    app.manage(BackendChild(Mutex::new(Some(child))));
                    // Monitor STDOUT para confirmar arranque
                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = rx.recv().await {
                            if let tauri_plugin_shell::process::CommandEvent::Stdout(line) = event {
                                let s = String::from_utf8_lossy(&line);
                                if s.contains("Uvicorn running") {
                                    println!("[Rust] Backend LISTO en :8008");
                                    break;
                                }
                            }
                        }
                    });
                } else {
                    app.manage(BackendChild(Mutex::new(None)));
                }
                
                // 2. Spawn sidecar (solo si backend arrancó)
                println!("[Rust] Iniciando strategy-sidecar...");
                let sidecar_child = match shell.sidecar("strategy-sidecar") {
                    Ok(cmd) => cmd.spawn().ok(),
                    Err(e) => {
                        eprintln!("[Rust] Error resolving strategy-sidecar: {:?}", e);
                        None
                    }
                };
                
                if let Some((mut rx, child)) = sidecar_child {
                    app.manage(SidecarChild(Mutex::new(Some(child))));
                    tauri::async_runtime::spawn(async move {
                        while let Some(event) = rx.recv().await {
                            if let tauri_plugin_shell::process::CommandEvent::Stdout(line) = event {
                                let s = String::from_utf8_lossy(&line);
                                println!("[Sidecar STDOUT] {}", s.trim());
                            }
                        }
                    });
                } else {
                    app.manage(SidecarChild(Mutex::new(None)));
                }
                
                // 3. Health check del backend cada 5s
                let app_handle = app.handle().clone();
                tauri::async_runtime::spawn(async move {
                    let mut failures = 0;
                    loop {
                        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
                        let ok = std::net::TcpStream::connect_timeout(
                            &"127.0.0.1:8008".parse().unwrap(),
                            std::time::Duration::from_secs(2),
                        ).is_ok();
                        if ok {
                            failures = 0;
                        } else {
                            failures += 1;
                            eprintln!("[Rust] Health check falló ({}/3)", failures);
                            if failures >= 3 {
                                eprintln!("[Rust] Backend caído — solicitando reinicio...");
                                if let Some(window) = app_handle.get_webview_window("main") {
                                    let _ = window.emit("backend-crashed", ());
                                }
                                break;
                            }
                        }
                    }
                });
            }
            
            // Resto del código existente (tray menu, mic preheat, etc.)
            // ...
        })
        .on_window_event(|window, event| {
            // Matar ambos procesos al cerrar
            if let tauri::WindowEvent::CloseRequested { .. } = event {
                // Matar backend
                if let Some(child) = window.state::<BackendChild>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
                // Matar sidecar
                if let Some(child) = window.state::<SidecarChild>().0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

// Estructuras para almacenar los procesos hijos
struct BackendChild(Mutex<Option<CommandChild>>);
struct SidecarChild(Mutex<Option<CommandChild>>);
```

- [ ] **Step 4: Añadir SidecarChild al menú "Salir" del tray**

En el manejador del menú tray, añadir matado del sidecar además del backend:

```rust
"quit" => {
    // Matar backend
    let backend = app.state::<BackendChild>();
    if let Some(child) = backend.0.lock().unwrap().take() {
        let _ = child.kill();
    }
    // Matar sidecar
    let sidecar = app.state::<SidecarChild>();
    if let Some(child) = sidecar.0.lock().unwrap().take() {
        let _ = child.kill();
    }
    app.exit(0);
}
```

- [ ] **Step 5: Verificar permisos en capabilities/default.json**

Asegurar que `shell:allow-spawn` y `shell:allow-execute` están presentes:

```json
{
    "identifier": "default",
    "windows": ["main"],
    "permissions": [
        "core:default",
        "opener:default",
        "shell:default",
        "shell:allow-spawn",
        "shell:allow-execute",
        "global-shortcut:default",
        "websocket:default"
    ]
}
```

- [ ] **Step 6: Verificar compilación Rust**

```bash
cd frontend/src-tauri && cargo check 2>&1 | head -30
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src-tauri/tauri.conf.json frontend/src-tauri/src/main.rs frontend/src-tauri/capabilities/default.json
git commit -m "feat: Tauri spawns vantare-engine + strategy-sidecar with health check"
```

---

### Task 4: Añadir endpoint /ws/sidecar en backend (si no existe)

**Files:**
- Modify: `backend/src/routers/websocket.py`

- [ ] **Step 1: Verificar si /ws/sidecar ya existe**

```bash
grep -n "sidecar" backend/src/routers/websocket.py
```

- [ ] **Step 2: Si no existe, añadir handler**

El backend debe aceptar conexiones del sidecar en `/ws/sidecar`. El sidecar envía:
```json
{
    "event": "strategy_frame",
    "data": {
        "advice": {...},
        "frame": {...},
        "events": [...]
    }
}
```

El handler debe:
1. Aceptar la conexión WebSocket
2. Almacenar `latest_strategy_frame` en `app.state`
3. `strategy_sender_loop` usa `latest_strategy_frame` primero, fallback a `StrategyService`

```python
# En websocket.py, dentro del router
@router.websocket("/ws/sidecar")
async def sidecar_websocket(websocket: WebSocket):
    await websocket.accept()
    app.state.sidecar_connected = True
    try:
        while True:
            data = await websocket.receive_json()
            if data.get("event") == "strategy_frame":
                app.state.latest_strategy_frame = data.get("data")
    except WebSocketDisconnect:
        app.state.sidecar_connected = False
        app.state.latest_strategy_frame = None
```

- [ ] **Step 3: Commit**

```bash
git add backend/src/routers/websocket.py
git commit -m "feat: add /ws/sidecar endpoint for strategy-sidecar communication"
```

---

### Task 5: Tests de integración

**Files:**
- Create: `backend/tests/test_sidecar_integration.py`
- Create: `sidecar/tests/test_strategy_runner.py` (existente o nuevo)

- [ ] **Step 1: Test de health endpoint con estado del sidecar**

```python
"""Tests de integración del sidecar en el backend."""
import pytest
from starlette.testclient import TestClient


class TestSidecarHealth:
    """El health endpoint debe reportar estado del sidecar."""

    def test_health_contains_sidecar_status(self, app):
        """GET /health debe incluir campo sidecar."""
        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "sidecar" in data
            assert "connected" in data["sidecar"]
            assert "lmu_available" in data["sidecar"]


class TestSidecarWebSocket:
    """Endpoint /ws/sidecar debe aceptar conexiones y strategy_frames."""

    @pytest.mark.asyncio
    async def test_sidecar_ws_connect(self, app):
        """Sidecar debe poder conectarse a /ws/sidecar."""
        from fastapi.testclient import TestClient as ASGIClient
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                # Enviar strategy_frame
                ws.send_json({
                    "event": "strategy_frame",
                    "data": {
                        "advice": {"fuel_advice": "OK"},
                        "frame": {"lap_number": 1},
                        "events": []
                    }
                })
                # Verificar que se almacenó
                assert app.state.latest_strategy_frame is not None
                assert app.state.sidecar_connected is True

    @pytest.mark.asyncio
    async def test_sidecar_ws_disconnect_clears_state(self, app):
        """Al desconectarse, debe limpiar latest_strategy_frame."""
        from fastapi.testclient import TestClient as ASGIClient
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                ws.send_json({"event": "strategy_frame", "data": {}})
            # Después del context manager, la conexión se cerró
            assert app.state.sidecar_connected is False
            assert app.state.latest_strategy_frame is None
```

- [ ] **Step 2: Ejecutar tests**

```bash
cd backend && python -m pytest tests/test_sidecar_integration.py -v
```

Expected:
```
test_health_contains_sidecar_status PASSED
test_sidecar_ws_connect PASSED
test_sidecar_ws_disconnect_clears_state PASSED
```

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_sidecar_integration.py
git commit -m "test: sidecar WebSocket integration tests"
```

---

### Task 6: Actualizar orchestrator.md

**Files:**
- Modify: `docs/ai/orchestrator.md`

- [ ] **Step 1: Marcar Fase 7 como completada**

En el roadmap, cambiar Fase 7 a ✅ COMPLETADA con fecha. Añadir resumen de la arquitectura final.

- [ ] **Step 2: Commit**

```bash
git add docs/ai/orchestrator.md
git commit -m "docs: mark Fase 7 complete in orchestrator.md"
```

---

## Resumen de Archivos (versión corregida)

| Archivo | Acción |
|---------|--------|
| `backend/build.py` | Modificado (--onedir) |
| `backend/.gitignore` | Modificado (dist/build/*.spec) |
| `sidecar/build.py` | Creado (--onedir) |
| `sidecar/.gitignore` | Creado |
| `frontend/src-tauri/tauri.conf.json` | Modificado (dos externalBin) |
| `frontend/src-tauri/src/main.rs` | Modificado (spawn dual + health check) |
| `frontend/src-tauri/capabilities/default.json` | Modificado (permisos shell) |
| `backend/src/routers/websocket.py` | Modificado (/ws/sidecar handler) |
| `backend/tests/test_sidecar_integration.py` | Creado |
| `docs/ai/orchestrator.md` | Modificado |

**NO se mueve sidecar/ a backend/.** Cada proceso mantiene su propio directorio y entrypoint.
