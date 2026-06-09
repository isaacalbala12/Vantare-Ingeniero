# Backend Hardening — Deuda Técnica Post-Auditoría Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corregir la deuda técnica marcada como “fuera de scope” tras la auditoría Gemini: inyección explícita de dependencias, scheduling monotónico en bucles WS, logging en excepciones silenciosas, simplificación de `_to_dict`, y baseline Ruff con gate en CI.

**Architecture:** Cambios pequeños y localizados sin reestructurar el monolito. `StrategyService` se inyecta igual que `event_store`/`history_store`. Los bucles WebSocket usan `time.monotonic()` para compensar el tiempo de procesamiento. La coerción de estado sale de `engine.py` a un módulo puro testeable. Ruff se adopta en fases: config → auto-fix → CI.

**Tech Stack:** Python 3.12+, FastAPI, asyncio, pytest, ruff

**Relación con otros planes:** Ejecutar **después** de `docs/superpowers/plans/2026-06-09-audit-gemini-backend-fixes.md` (P0/P1 concurrencia/persistencia). Este plan no duplica esas tareas.

**Pre-condiciones:**
- `cd backend` desde la raíz del repo
- Entorno con `pip install -e ./backend[dev]`

---

## Mapa de archivos

| Archivo | Cambio |
|---------|--------|
| `backend/src/main.py` | Pasar `strategy_service` al `IntelligenceEngine` |
| `backend/src/intelligence/engine.py` | Eliminar `sys.modules`; delegar `_to_dict` |
| `backend/src/intelligence/state_coercion.py` | **Create** — `coerce_state_dict()` |
| `backend/src/routers/websocket.py` | Scheduling monotónico 20 Hz / 0.5 Hz |
| `backend/src/persistence/event_store.py` | Log debug en cleanup esperado |
| `backend/src/services/update_service.py` | Log debug en fallos de red |
| `backend/pyproject.toml` | Config `[tool.ruff]` + dep dev |
| `.github/workflows/ci.yml` | Step `ruff check` |
| `backend/tests/test_engine_strategy_injection.py` | **Create** |
| `backend/tests/test_ws_loop_timing.py` | **Create** |
| `backend/tests/test_state_coercion.py` | **Create** |
| `backend/tests/test_update_service.py` | **Create** o modify si existe |
| `backend/tests/test_engine.py` | Actualizar tests `_to_dict` |

---

### Task 1: Inyectar StrategyService y eliminar sys.modules

**Files:**
- Modify: `backend/src/main.py:124-128`
- Modify: `backend/src/intelligence/engine.py:112-118`
- Create: `backend/tests/test_engine_strategy_injection.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_engine_strategy_injection.py`:

```python
"""Tests de inyección explícita de StrategyService en IntelligenceEngine."""

from unittest.mock import MagicMock

from src.intelligence.engine import IntelligenceEngine


def test_get_strategy_service_returns_injected_instance():
    svc = MagicMock(name="strategy_service")
    engine = IntelligenceEngine(
        broadcaster=MagicMock(),
        llm_client=MagicMock(),
        strategy_service=svc,
    )
    assert engine._get_strategy_service() is svc


def test_get_strategy_service_without_injection_returns_none():
    engine = IntelligenceEngine(
        broadcaster=MagicMock(),
        llm_client=MagicMock(),
        strategy_service=None,
    )
    assert engine._get_strategy_service() is None


def test_get_strategy_service_does_not_use_sys_modules(monkeypatch):
    """Tras el refactor, sys.modules no debe ser el mecanismo de resolución."""
    import sys

    fake_main = MagicMock()
    fake_main.app.state.strategy_service = MagicMock(name="from_sys_modules")
    monkeypatch.setitem(sys.modules, "src.main", fake_main)

    engine = IntelligenceEngine(
        broadcaster=MagicMock(),
        llm_client=MagicMock(),
        strategy_service=None,
    )
    assert engine._get_strategy_service() is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_engine_strategy_injection.py::test_get_strategy_service_does_not_use_sys_modules -v`

Expected: **FAIL** — retorna el mock de `sys.modules` en lugar de `None`.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/intelligence/engine.py`, replace `_get_strategy_service`:

```python
    def _get_strategy_service(self):
        return self.strategy_service
```

Remove unused `import sys` at top of `engine.py` if no other references remain.

In `backend/src/main.py`, pass the service already creado en línea 84:

```python
    intelligence_engine = IntelligenceEngine(
        broadcast_callback=broadcast_sync,
        history_store=history_store,
        event_store=event_store,
        strategy_service=strategy_service,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_engine_strategy_injection.py tests/test_engine.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/main.py backend/src/intelligence/engine.py backend/tests/test_engine_strategy_injection.py
git commit -m "refactor: inject StrategyService explicitly, drop sys.modules lookup"
```

---

### Task 2: Scheduling monotónico en telemetry_sender_loop (20 Hz)

**Files:**
- Modify: `backend/src/routers/websocket.py:77-120`
- Create: `backend/tests/test_ws_loop_timing.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ws_loop_timing.py`:

```python
"""Tests de utilidades de timing para bucles WebSocket."""

import time

from src.routers.websocket import TELEMETRY_INTERVAL_S, compute_loop_sleep


def test_compute_loop_sleep_returns_remaining_interval():
    start = time.monotonic()
    time.sleep(0.03)
    delay = compute_loop_sleep(TELEMETRY_INTERVAL_S, start)
    assert 0.015 <= delay <= 0.025


def test_compute_loop_sleep_never_negative():
    start = time.monotonic()
    time.sleep(0.08)
    delay = compute_loop_sleep(TELEMETRY_INTERVAL_S, start)
    assert delay == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_ws_loop_timing.py -v`

Expected: **FAIL** — `ImportError: cannot import name 'compute_loop_sleep'`.

- [ ] **Step 3: Write minimal implementation**

At module level in `backend/src/routers/websocket.py` (after imports):

```python
import time

TELEMETRY_INTERVAL_S = 0.05
STRATEGY_INTERVAL_S = 2.0


def compute_loop_sleep(interval_s: float, loop_started_at: float) -> float:
    """Segundos restantes para mantener la frecuencia objetivo del bucle."""
    elapsed = time.monotonic() - loop_started_at
    return max(0.0, interval_s - elapsed)
```

Replace `telemetry_sender_loop` body to use monotonic scheduling:

```python
async def telemetry_sender_loop(websocket: WebSocket, app_state) -> None:
    """Emite telemetría cruda a 20Hz (cada 50ms) y evalúa el Spotter en cada tick."""
    reader = getattr(app_state, "telemetry_reader", None)
    if not reader:
        logger.warning("Telemetry reader not found in app state")
        return

    while True:
        loop_started_at = time.monotonic()
        try:
            sidecar_frame = getattr(app_state, "latest_strategy_frame", None)
            if sidecar_frame and sidecar_frame.get("frame"):
                state_dict = sidecar_frame["frame"]
                logger.debug("Usando telemetry del sidecar")
            else:
                state = reader.get_state()
                if state is not None:
                    state_dict = state.model_dump(mode="json")
                else:
                    await asyncio.sleep(TELEMETRY_INTERVAL_S)
                    continue
                logger.debug("Usando TelemetryReader (offline)")

            spotter = getattr(app_state, "spotter_service", None)
            if spotter:
                sidecar_advice = sidecar_frame.get("advice") if sidecar_frame else None
                spotter_tick = frame_to_spotter_tick(state_dict, sidecar_advice)
                spotter.evaluate_tick(spotter_tick)

            raw = mp_encode(state_dict)
            await websocket.send_bytes(raw)

            await asyncio.sleep(compute_loop_sleep(TELEMETRY_INTERVAL_S, loop_started_at))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Error sending telemetry: %s", e)
            break
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_ws_loop_timing.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/routers/websocket.py backend/tests/test_ws_loop_timing.py
git commit -m "fix: monotonic scheduling for 20Hz telemetry loop"
```

---

### Task 3: Scheduling monotónico en strategy_sender_loop (0.5 Hz)

**Files:**
- Modify: `backend/src/routers/websocket.py:123-187`
- Modify: `backend/tests/test_ws_loop_timing.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_ws_loop_timing.py`:

```python
def test_strategy_interval_constant():
    from src.routers.websocket import STRATEGY_INTERVAL_S

    assert STRATEGY_INTERVAL_S == 2.0
```

(This test pasa inmediatamente tras Task 2; sirve como ancla de contrato.)

- [ ] **Step 2: Implement strategy loop change**

In `strategy_sender_loop`, wrap each iteration:

```python
    while True:
        loop_started_at = time.monotonic()
        try:
            if not manager.active_connections:
                await asyncio.sleep(STRATEGY_INTERVAL_S)
                continue

            # ... existing body unchanged ...

            await asyncio.sleep(compute_loop_sleep(STRATEGY_INTERVAL_S, loop_started_at))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Error sending strategy advice: %s", e)
            break
```

Replace the hardcoded `await asyncio.sleep(2.0)` at end of loop with `compute_loop_sleep(STRATEGY_INTERVAL_S, loop_started_at)`.

Also fix f-string logs in this function while touching it (lazy logging):

```python
logger.debug("Error sending strategy advice: %s", e)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_ws_loop_timing.py -v`

Expected: **PASS**

- [ ] **Step 4: Commit**

```bash
git add backend/src/routers/websocket.py backend/tests/test_ws_loop_timing.py
git commit -m "fix: monotonic scheduling for 0.5Hz strategy loop"
```

---

### Task 4: Logging debug en excepciones silenciosas

**Files:**
- Modify: `backend/src/persistence/event_store.py:116-124`
- Modify: `backend/src/services/update_service.py:29-45`
- Create: `backend/tests/test_update_service.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_update_service.py`:

```python
"""Tests de update_service."""

from unittest.mock import AsyncMock, patch

import pytest

from src.services import update_service


@pytest.mark.asyncio
async def test_fetch_latest_release_logs_debug_on_network_error(caplog):
    with patch("src.services.update_service.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.get.side_effect = OSError("network down")
        mock_client_cls.return_value = mock_client

        with caplog.at_level("DEBUG", logger="vantare.update"):
            result = await update_service.fetch_latest_release()

    assert result is None
    assert any("fetch_latest_release failed" in r.message for r in caplog.records)
```

Add logger to `update_service.py` if missing:

```python
import logging

logger = logging.getLogger("vantare.update")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_update_service.py::test_fetch_latest_release_logs_debug_on_network_error -v`

Expected: **FAIL** — no log record matched.

- [ ] **Step 3: Write minimal implementation**

In `backend/src/services/update_service.py`:

```python
    except Exception as exc:
        logger.debug("fetch_latest_release failed: %s", exc)
        return None
```

In `backend/src/persistence/event_store.py`, replace inner bare `pass`:

```python
                except (ValueError, chromadb.errors.NotFoundError, chromadb.errors.InternalError) as exc:
                    logger.debug("ChromaDB collection already absent during clear: %s", exc)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_update_service.py -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/services/update_service.py backend/src/persistence/event_store.py backend/tests/test_update_service.py
git commit -m "chore: add debug logging for expected cleanup and update failures"
```

---

### Task 5: Extraer coerce_state_dict y simplificar _to_dict

**Files:**
- Create: `backend/src/intelligence/state_coercion.py`
- Modify: `backend/src/intelligence/engine.py:571-599`
- Create: `backend/tests/test_state_coercion.py`
- Modify: `backend/tests/test_engine.py:161-167`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_state_coercion.py`:

```python
"""Tests de coerce_state_dict."""

from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from src.intelligence.state_coercion import coerce_state_dict


class SampleModel(BaseModel):
    speed: int = 180
    lap_number: int = 3


def test_coerce_none_returns_empty_dict():
    assert coerce_state_dict(None) == {}


def test_coerce_dict_returns_same_mapping():
    data = {"speed": 200}
    assert coerce_state_dict(data) is data


def test_coerce_pydantic_model():
    model = SampleModel()
    result = coerce_state_dict(model)
    assert result == {"speed": 180, "lap_number": 3}


def test_coerce_mock_for_tests():
    mock = MagicMock()
    mock.speed = 150
    mock.lap_number = 2
    mock.foo = MagicMock()
    result = coerce_state_dict(mock, allow_mock=True)
    assert result["speed"] == 150
    assert result["lap_number"] == 2
    assert "foo" not in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_state_coercion.py -v`

Expected: **FAIL** — `ModuleNotFoundError: state_coercion`.

- [ ] **Step 3: Write minimal implementation**

Create `backend/src/intelligence/state_coercion.py`:

```python
"""Convierte objetos de telemetría/estrategia a dict plano para el engine."""

from __future__ import annotations

from typing import Any


def coerce_state_dict(obj: Any, *, allow_mock: bool = False) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    if allow_mock:
        from unittest.mock import Mock

        if isinstance(obj, Mock):
            result: dict[str, Any] = {}
            for key in dir(obj):
                if key.startswith("_"):
                    continue
                try:
                    value = getattr(obj, key)
                except AttributeError:
                    continue
                if isinstance(value, Mock):
                    continue
                result[key] = value
            return result
    try:
        return vars(obj)
    except TypeError:
        return {}
```

In `backend/src/intelligence/engine.py`, replace `_to_dict`:

```python
    def _to_dict(self, obj) -> dict:
        """Helper para convertir estado (Pydantic, dict, Mock en tests) a dict."""
        from src.intelligence.state_coercion import coerce_state_dict

        import sys

        allow_mock = "pytest" in sys.modules
        return coerce_state_dict(obj, allow_mock=allow_mock)
```

Update `backend/tests/test_engine.py` tests — they should still pass unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_state_coercion.py tests/test_engine.py::TestIntelligenceEngine::test_to_dict_with_none tests/test_engine.py::TestIntelligenceEngine::test_to_dict_with_dict -v`

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/state_coercion.py backend/src/intelligence/engine.py backend/tests/test_state_coercion.py
git commit -m "refactor: extract coerce_state_dict from IntelligenceEngine"
```

---

### Task 6: Configurar Ruff en el backend

**Files:**
- Modify: `backend/pyproject.toml`

- [ ] **Step 1: Add ruff dependency and config**

In `backend/pyproject.toml`, extend dev dependencies:

```toml
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.5",
    "pytest-cov>=5.0.0",
    "pytest-timeout>=2.0.0",
    "ruff>=0.9.0",
]
```

Append:

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
src = ["src"]

[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort
    "UP",  # pyupgrade
    "B",   # bugbear
    "SIM", # simplify
]
ignore = [
    "E501",  # line length — revisar manualmente después
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"]  # assert en tests OK
```

- [ ] **Step 2: Install and capture baseline**

Run:

```bash
cd backend
pip install -e ".[dev]"
python -m ruff check src/ --statistics
```

Expected: imprime conteo por regla (baseline documentado en el commit message).

- [ ] **Step 3: Auto-fix safe violations**

Run:

```bash
cd backend
python -m ruff check src/ --fix
python -m ruff format src/
```

Re-run tests after mass fix:

```bash
python -m pytest tests/ -q --timeout=120 -x
```

Expected: tests siguen pasando (corregir manualmente cualquier rotura de imports).

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/src/
git commit -m "chore: add ruff config and auto-fix backend/src"
```

---

### Task 7: Gate Ruff en CI

**Files:**
- Modify: `.github/workflows/ci.yml:30-40`

- [ ] **Step 1: Add CI step after dependency install**

In `.github/workflows/ci.yml`, inside job `test-backend`, after `Install Python dependencies`:

```yaml
      - name: Ruff lint
        run: |
          cd backend
          python -m ruff check src/
          python -m ruff format src/ --check
```

- [ ] **Step 2: Verify locally**

Run:

```bash
cd backend
python -m ruff check src/
python -m ruff format src/ --check
```

Expected: exit code 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: enforce ruff lint and format on backend/src"
```

---

### Task 8: Verificación final

**Files:** (read-only)

- [ ] **Step 1: Run focused regression suite**

```bash
cd backend && python -m pytest \
  tests/test_engine_strategy_injection.py \
  tests/test_ws_loop_timing.py \
  tests/test_state_coercion.py \
  tests/test_update_service.py \
  tests/test_engine.py \
  -v
```

Expected: **All PASS**

- [ ] **Step 2: Smoke import**

```bash
cd backend && python -c "from src.main import app; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Manual checklist**

1. Arrancar backend; confirmar logs de `StrategyService` + `IntelligenceEngine` sin errores de import
2. Conectar WebSocket; verificar telemetría estable (~20 Hz nominal) sin drift acumulativo visible en logs de debug
3. Panel Avanzado → check update: fallo de red no debe spamear ERROR, solo DEBUG si log level bajo

---

## Self-Review

| Requisito discutido con el usuario | Task |
|-----------------------------------|------|
| Eliminar `sys.modules` DI | Task 1 |
| Drift sleep 20 Hz | Task 2 |
| Drift sleep 0.5 Hz (estrategia) | Task 3 |
| `except` silencioso → log debug | Task 4 |
| `_to_dict()` reflexivo → módulo puro | Task 5 |
| Ruff ~1000 warnings + CI | Tasks 6–7 |

**Placeholder scan:** ninguno.

**Type consistency:** `compute_loop_sleep(interval_s: float, loop_started_at: float) -> float` usado en ambos bucles; `coerce_state_dict` retorna `dict[str, Any]`; `strategy_service` inyectado en constructor existente.

**Gaps:** no incluye refactor masivo de f-strings en logs fuera de los archivos tocados (Ruff `--fix` cubre parte en Task 6).

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-09-backend-hardening-deuda-tecnica.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
