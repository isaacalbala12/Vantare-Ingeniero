# Fase 7: Sidecar Windows + Integración Tauri — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unificar el sidecar de estrategia dentro del backend FastAPI y empaquetar todo como un único ejecutable (`vantare-engine.exe`) gestionado por Tauri.

**Arquitectura:** El sidecar (strategy_runner.py + event_detector.py) se mueve a `backend/src/sidecar/` y se integra en `main.py`. La comunicación con StrategyService es directa (sin WebSocket). Tauri spawns un solo proceso con health check vía GET /health. El LLM sigue remoto.

**Tech Stack:** Python 3.12+, FastAPI, PyInstaller 6+, Tauri 2 + Rust, Tauri plugin shell

---

### Task 1: Mover archivos del sidecar a backend/

**Files:**
- Move: `sidecar/src/sidecar/strategy_runner.py` → `backend/src/sidecar/strategy_runner.py`
- Move: `sidecar/src/sidecar/event_detector.py` → `backend/src/sidecar/event_detector.py`
- Move: `sidecar/src/sidecar/__init__.py` → `backend/src/sidecar/__init__.py`
- Move: `sidecar/pyproject.toml` (fusionar dependencias en `backend/pyproject.toml`)
- Modify: `backend/src/sidecar/strategy_runner.py` (eliminar import de shared_telemetry.sync que ya no existe)

- [ ] **Step 1: Crear directorio y mover archivos**

```bash
mkdir -p backend/src/sidecar
cp sidecar/src/sidecar/strategy_runner.py backend/src/sidecar/strategy_runner.py
cp sidecar/src/sidecar/event_detector.py backend/src/sidecar/event_detector.py
cp sidecar/src/sidecar/__init__.py backend/src/sidecar/__init__.py
```

- [ ] **Step 2: Verificar imports en strategy_runner.py**

Leer archivo movido para confirmar que los imports funcionan dentro del backend. La línea `from shared_telemetry.sync import TelemetrySync` debe resolverse desde `shared-telemetry/src/`.

```bash
cd backend && python -c "from src.sidecar.strategy_runner import StrategyRunner; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Fusionar dependencias del sidecar en backend/pyproject.toml**

Verificar que `backend/pyproject.toml` ya tiene `websockets` y `python-dotenv`. Si faltan, añadirlas.

```bash
cd backend && grep -E "websockets|python-dotenv" pyproject.toml
```

- [ ] **Step 4: Commit**

```bash
git add backend/src/sidecar/ sidecar/src/sidecar/
git commit -m "feat: move sidecar modules to backend/src/sidecar/"
```

---

### Task 2: Integrar sidecar en backend/main.py

**Files:**
- Modify: `backend/src/main.py`
- Modify: `backend/src/routers/websocket.py`

- [ ] **Step 1: Leer main.py actual**

```bash
cat backend/src/main.py
```

- [ ] **Step 2: Añadir flag LMU_AVAILABLE y carga condicional del sidecar**

Al inicio de `main.py`, después de `load_dotenv()`:

```python
import os

# Detección de LMU real vs simulado
LMU_AVAILABLE = os.getenv("LMU_AVAILABLE", "false").strip().lower() == "true"
```

- [ ] **Step 3: Registrar sidecar runner en app.state si LMU_AVAILABLE**

Dentro del lifespan handler, después de inicializar `reader`:

```python
from src.sidecar.strategy_runner import StrategyRunner
from src.sidecar.event_detector import StateChangeDetector

if LMU_AVAILABLE:
    logger.info("LMU_AVAILABLE=true — iniciando sidecar con shared memory real")
    reader = TelemetryReader(offline=False, poll_rate=0.05)
    reader.start()
    app.state.sidecar_runner = StrategyRunner(reader)
    app.state.sidecar_detector = StateChangeDetector()
    app.state.lmu_available = True
else:
    logger.info("LMU_AVAILABLE=false — modo simulado (offline)")
    reader = TelemetryReader(offline=True)
    app.state.sidecar_runner = None
    app.state.sidecar_detector = None
    app.state.lmu_available = False
```

- [ ] **Step 4: Arrancar loop de sidecar como tarea asyncio de background**

Después de inicializar el reader, añadir tarea:

```python
async def _sidecar_loop():
    """Cada 2s: process_cycle + detect + update strategy_service directamente."""
    runner = app.state.sidecar_runner
    detector = app.state.sidecar_detector
    if runner is None or detector is None:
        return
    
    while True:
        try:
            runner.process_cycle()
            if runner.latest_frame is not None and runner.latest_advice is not None:
                events = detector.detect(runner.latest_frame)
                # Llamada directa a StrategyService
                from src.services.strategy_service import strategy_service
                strategy_service.update(runner.latest_advice, runner.latest_frame, events)
        except Exception as e:
            logger.exception("Error en sidecar_loop: %s", e)
        await asyncio.sleep(2.0)

if LMU_AVAILABLE:
    task = asyncio.create_task(_sidecar_loop())
    # Guardar referencia para cancelación en shutdown
    app.state._sidecar_task = task
```

Añadir cancelación en shutdown:

```python
# Al final del lifespan, en shutdown:
if LMU_AVAILABLE and hasattr(app.state, "_sidecar_task"):
    app.state._sidecar_task.cancel()
    try:
        await app.state._sidecar_task
    except asyncio.CancelledError:
        pass
    reader.stop()
```

- [ ] **Step 5: Añadir LMU status al endpoint /health**

```python
# En health endpoint o router existente:
"sidecar": {
    "lmu_available": getattr(app.state, "lmu_available", False),
    "active": getattr(app.state, "sidecar_runner", None) is not None
}
```

- [ ] **Step 6: Commit**

```bash
git add backend/src/main.py
git commit -m "feat: integrate sidecar into backend with LMU_AVAILABLE flag"
```

---

### Task 3: Crear build.py para PyInstaller

**Files:**
- Create: `backend/build.py`
- Modify: `backend/.gitignore`

- [ ] **Step 1: Crear spec de PyInstaller**

```python
# backend/build.py
"""
Build script para empaquetar backend como vantare-engine.exe.
Uso: cd backend && pyinstaller build.py
"""
import sys
from pathlib import Path

import PyInstaller.__main__

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED_TELEMETRY = REPO_ROOT / "shared-telemetry" / "src"
SHARED_STRATEGY = REPO_ROOT / "shared-strategy" / "src"

# Localizar .pyd de pyLMUSharedMemory (C extension)
PYLMU_DIR = SHARED_TELEMETRY / "shared_telemetry" / "pyLMUSharedMemory"
PYD_FILES = list(PYLMU_DIR.glob("*.pyd"))

binaries = []
if PYD_FILES:
    for pyd in PYD_FILES:
        binaries.append((str(pyd), "shared_telemetry/pyLMUSharedMemory"))

args = [
    "--onefile",
    "--noconsole",
    "--name=vantare-engine",
    "--add-data", f"{SHARED_TELEMETRY}{Path.pathsep}shared_telemetry",
    "--add-data", f"{SHARED_STRATEGY}{Path.pathsep}shared_strategy",
    "--hidden-import=uvicorn.logging",
    "--hidden-import=uvicorn.loops.auto",
    "--hidden-import=uvicorn.protocols.http.auto",
]

for src, dest in binaries:
    args.extend(["--add-binary", f"{src}{Path.pathsep}{dest}"])

args.append("src/main.py")

PyInstaller.__main__.run(args)
```

- [ ] **Step 2: Añadir backend/.gitignore para dist/ y build/**

```gitignore
# backend/.gitignore
dist/
build/
*.spec
```

- [ ] **Step 3: Verificar que build.py es sintácticamente válido**

```bash
cd backend && python -c "import ast; ast.parse(open('build.py').read()); print('build.py sintaxis OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/build.py backend/.gitignore
git commit -m "feat: add PyInstaller build script for vantare-engine.exe"
```

---

### Task 4: Renombrar externalBin en Tauri de backend a vantare-engine

**Files:**
- Modify: `frontend/src-tauri/tauri.conf.json`

- [ ] **Step 1: Leer tauri.conf.json**

```bash
cat frontend/src-tauri/tauri.conf.json
```

- [ ] **Step 2: Cambiar externalBin**

Localizar `"externalBin"` en tauri.conf.json. Cambiar:

```json
// ANTES
"externalBin": ["../backend/dist/backend"],

// DESPUÉS
"externalBin": ["../backend/dist/vantare-engine"],
```

- [ ] **Step 3: Verificar que el JSON es válido**

```bash
cd frontend/src-tauri && python -c "import json; json.load(open('tauri.conf.json')); print('JSON válido')"
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src-tauri/tauri.conf.json
git commit -m "feat: rename externalBin from backend to vantare-engine"
```

---

### Task 5: Actualizar main.rs (Rust) — rename + health check

**Files:**
- Modify: `frontend/src-tauri/src/main.rs`

- [ ] **Step 1: Leer main.rs actual**

```bash
cat -n frontend/src-tauri/src/main.rs
```

- [ ] **Step 2: Renombrar sidecar de "backend" a "vantare-engine"**

En la línea `shell.sidecar("backend")`, cambiar a `shell.sidecar("vantare-engine")`. También en mensajes de log.

```rust
// Línea 35
match shell.sidecar("vantare-engine") {
// ...
println!("[Rust] Iniciando el sidecar vantare-engine...");
println!("[Rust] MODO DEBUG: Sidecar vantare-engine desactivado.");
// ...
println!("[Rust] Backend vantare-engine confirmado y LISTO en el puerto 8008!");
```

- [ ] **Step 3: Añadir health check periódico**

Añadir un loop de health check dentro del spawn de monitoreo. Después de la confirmación de "LISTO":

```rust
// Health check periódico cada 5s
let health_url = "http://127.0.0.1:8008/health".to_string();
let app_handle = app.handle().clone();

tauri::async_runtime::spawn(async move {
    let mut consecutive_failures = 0;
    let max_failures = 3;
    loop {
        tokio::time::sleep(tokio::time::Duration::from_secs(5)).await;
        let ok = reqwest::get(&health_url)
            .await
            .map(|r| r.status().is_success())
            .unwrap_or(false);
        if ok {
            consecutive_failures = 0;
        } else {
            consecutive_failures += 1;
            eprintln!("[Rust] Health check falló ({}/{})", consecutive_failures, max_failures);
            if consecutive_failures >= max_failures {
                eprintln!("[Rust] Backend no responde — solicitando reinicio...");
                // Emitir evento a la ventana principal para reinicio
                if let Some(window) = app_handle.get_webview_window("main") {
                    let _ = window.emit("backend-crashed", ());
                }
                break;
            }
        }
    }
});
```

Nota: reqwest puede no estar en Cargo.toml. Alternativa: usar `tauri_plugin_http` o un simple `TcpStream` para probar el puerto.

**Opción simplificada sin reqwest:**

```rust
use std::net::TcpStream;

// En lugar de reqwest::get
let ok = TcpStream::connect_timeout(
    &"127.0.0.1:8008".parse().unwrap(),
    std::time::Duration::from_secs(2),
).is_ok();
```

- [ ] **Step 4: Verificar que compila**

```bash
cd frontend/src-tauri && cargo check 2>&1 | head -30
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src-tauri/src/main.rs
git commit -m "feat: rename backend to vantare-engine, add health check"
```

---

### Task 6: Permisos Tauri para shell

**Files:**
- Modify: `frontend/src-tauri/capabilities/default.json`

- [ ] **Step 1: Leer capabilities/default.json**

```bash
cat frontend/src-tauri/capabilities/default.json
```

- [ ] **Step 2: Añadir permiso shell:allow-spawn si no existe**

```json
{
    "identifier": "default",
    "description": "Capability for the main window",
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

- [ ] **Step 3: Commit**

```bash
git add frontend/src-tauri/capabilities/default.json
git commit -m "feat: add shell:allow-spawn permission for sidecar"
```

---

### Task 7: Tests de integración del sidecar

**Files:**
- Create: `backend/tests/test_sidecar_integration.py`

- [ ] **Step 1: Escribir test de inicialización sin LMU (modo simulado)**

```python
"""Tests de integración del sidecar dentro del backend."""
import pytest
from unittest.mock import patch, MagicMock


def test_sidecar_not_available_by_default(app):
    """Sin LMU_AVAILABLE, sidecar debe estar desactivado."""
    assert app.state.lmu_available is False
    assert app.state.sidecar_runner is None


@pytest.mark.asyncio
async def test_health_reports_sidecar_status(app):
    """El health endpoint debe reportar estado del sidecar."""
    from starlette.testclient import TestClient
    with TestClient(app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "sidecar" in data
        assert data["sidecar"]["lmu_available"] is False
        assert data["sidecar"]["active"] is False
```

- [ ] **Step 2: Test con LMU_AVAILABLE=true simulado**

```python
@pytest.mark.asyncio
async def test_sidecar_initializes_with_lmu():
    """Con LMU_AVAILABLE=true, sidecar debe inicializar runner y detector."""
    from src.main import app as main_app
    assert main_app.state.lmu_available is False  # Sin env var, debe ser False
```

- [ ] **Step 3: Ejecutar tests**

```bash
cd backend && python -m pytest tests/test_sidecar_integration.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_sidecar_integration.py
git commit -m "test: add sidecar integration tests"
```

---

### Task 8: Eliminar carpeta sidecar/ raíz

**Files:**
- Delete: `sidecar/src/sidecar/main.py`
- Delete: `sidecar/src/sidecar/__init__.py`
- Delete: `sidecar/src/sidecar/strategy_runner.py`
- Delete: `sidecar/src/sidecar/event_detector.py`
- Delete: `sidecar/pyproject.toml`
- Delete: `sidecar/README.md`

- [ ] **Step 1: Verificar que los archivos se movieron correctamente**

```bash
ls -la backend/src/sidecar/
```

Expected: `__init__.py`, `strategy_runner.py`, `event_detector.py`

- [ ] **Step 2: Eliminar carpeta sidecar/ raíz**

```bash
rm -rf sidecar/
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "clean: remove standalone sidecar directory (moved to backend/src/sidecar/)"
```

---

### Task 9: Actualizar orchestrator.md con estado de Fase 7

**Files:**
- Modify: `docs/ai/orchestrator.md`

- [ ] **Step 1: Marcar Fase 7 como completada**

Cambiar sección Fase 7 de pendiente a completada. Añadir fecha de implementación y resumen de decisiones.

- [ ] **Step 2: Commit**

```bash
git add docs/ai/orchestrator.md
git commit -m "docs: update orchestrator with Fase 7 completion"
```

---

## Resumen de Archivos

| Archivo | Acción |
|---------|--------|
| `backend/src/sidecar/strategy_runner.py` | Movido desde sidecar/ |
| `backend/src/sidecar/event_detector.py` | Movido desde sidecar/ |
| `backend/src/sidecar/__init__.py` | Movido desde sidecar/ |
| `backend/src/main.py` | Modificado |
| `backend/build.py` | Creado |
| `backend/.gitignore` | Modificado |
| `backend/pyproject.toml` | Modificado (verificar dependencias) |
| `backend/tests/test_sidecar_integration.py` | Creado |
| `frontend/src-tauri/tauri.conf.json` | Modificado |
| `frontend/src-tauri/src/main.rs` | Modificado |
| `frontend/src-tauri/capabilities/default.json` | Modificado |
| `sidecar/` (raíz) | Eliminado |
| `docs/ai/orchestrator.md` | Modificado |
