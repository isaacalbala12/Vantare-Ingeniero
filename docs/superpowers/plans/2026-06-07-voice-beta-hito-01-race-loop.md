# Hito 1 — Global race_loop (P0 CC-on-WebSocket fix)

> **For agentic workers:** REQUIRED SUB-SKILL: subagent-driven-development or executing-plans.  
> **Orquestador INDEX:** [`2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md`](2026-06-07-voice-beta-ORCHESTRATOR-INDEX.md)

**Goal:** Un único loop 20 Hz evalúa spotter + CC **sin depender de WebSocket**. UI recibe telemetría @ 10 Hz desde `TelemetryHub`.

**Architecture:** `race_tick_loop` en lifespan reemplaza `spotter_eval_loop`. `telemetry_sender_loop` solo publica bytes; elimina `crewchief_loop.on_frame` (L167-177).

**Tech Stack:** Python 3.12, asyncio, FastAPI, pytest-asyncio.

---

## Preconditions (BLOCKING)

- [ ] CWD repo: `C:\Users\isaac\Desktop\Vantare-Ingeniero`
- [ ] Baseline smoke green:

```powershell
cd backend
python -m pytest tests/test_config_update_ack_ws.py tests/test_spotter.py -q --tb=line
```

- [ ] Confirm bug exists (read-only):

```powershell
Select-String -Path backend\src\routers\websocket.py -Pattern "crewchief_loop.on_frame"
```

Expected: match inside `telemetry_sender_loop` (~line 171).

---

## Scope

### Files ALLOWED

| Action | Path |
|--------|------|
| Create | `backend/src/race/__init__.py` |
| Create | `backend/src/race/telemetry_hub.py` |
| Create | `backend/src/race/tick_loop.py` |
| Create | `backend/tests/test_telemetry_hub.py` |
| Create | `backend/tests/test_race_tick_loop.py` |
| Create | `backend/tests/test_race_loop_no_ws.py` |
| Create | `backend/tests/test_ws_telemetry_hub.py` |
| Modify | `backend/src/main.py` (lifespan only) |
| Modify | `backend/src/routers/websocket.py` (telemetry_sender_loop, constants) |

### Files FORBIDDEN

- `backend/src/intelligence/crewchief_events/modules/**`
- `backend/src/voice/**` (Hito 2)
- `frontend/**`
- `shared-telemetry/**`, `shared-strategy/**`

---

## Task 1: TelemetryHub

**Files:** `backend/src/race/telemetry_hub.py`, `backend/tests/test_telemetry_hub.py`

- [ ] **Step 1:** Write failing tests (exact code in plan maestro Task 1)
- [ ] **Step 2:** `cd backend && python -m pytest tests/test_telemetry_hub.py -v` → FAIL import
- [ ] **Step 3:** Implement `TelemetryHub` with `copy.deepcopy` on get/update
- [ ] **Step 4:** pytest PASS (2 tests)
- [ ] **Step 5:** Commit `feat(race): add TelemetryHub for UI snapshot broadcast`

---

## Task 2: run_race_tick_once + race_tick_loop

**Files:** `backend/src/race/tick_loop.py`, `backend/tests/test_race_tick_loop.py`

**Order inside tick (INVARIANT — do not reorder):**

1. `strategy.snapshot_frame()` — if None, return
2. `strategy.get_latest_advice()` → dict
3. `spotter.evaluate_tick(frame_to_spotter_tick(...))` if spotter.enabled
4. `crewchief_loop.on_frame(...)` if `engine.engineer_enabled`
5. `telemetry_hub.update(snapshot, advice)`
6. `telemetry_hub.record_tick_time(time.monotonic())`

- [ ] Steps 1-5 TDD per plan maestro Task 2
- [ ] Commit `feat(race): add global race_tick_loop`

---

## Task 3: Wire main.py

**Replace:**

```python
from src.routers.websocket import spotter_eval_loop
spotter_task = asyncio.create_task(spotter_eval_loop(app.state))
```

**With:**

```python
from src.race.telemetry_hub import TelemetryHub
from src.race.tick_loop import RaceTickDeps, race_tick_loop

telemetry_hub = TelemetryHub()
app.state.telemetry_hub = telemetry_hub
# ... after crewchief_loop + intelligence_engine exist ...
race_deps = RaceTickDeps(
    strategy_service=strategy_service,
    spotter_service=spotter_service,
    crewchief_loop=app.state.crewchief_loop,
    intelligence_engine=intelligence_engine,
    telemetry_hub=telemetry_hub,
)
app.state.race_task = asyncio.create_task(race_tick_loop(race_deps))
logger.info("race_tick_loop spawned (20Hz global)")
```

**Shutdown:** cancel `app.state.race_task` instead of `spotter_task`.

**Log line fix:** Remove or update `"CrewChiefGameStateLoop wired at 20Hz via WebSocket telemetry"`.

- [ ] Implement + manual import check: `python -c "from src.main import app"`
- [ ] Commit `feat(race): wire race_tick_loop in lifespan`

---

## Task 4: Decouple websocket telemetry

**Changes in `websocket.py`:**

1. Add `UI_TELEMETRY_INTERVAL_S = 0.1`
2. Delete block L167-177 (`crewchief_loop.on_frame` in `telemetry_sender_loop`)
3. Read snapshot from `app_state.telemetry_hub.get_latest()` first; fallback `strategy.snapshot_frame()`
4. Sleep `UI_TELEMETRY_INTERVAL_S` not `TELEMETRY_INTERVAL_S`

**Keep unchanged:** `spotter_eval_loop` function may remain dead code until deleted in Hito 5 (optional delete now if no imports).

- [ ] Test `test_ws_telemetry_hub.py`: CC `on_frame` NOT called during WS send
- [ ] Commit `fix(ws): decouple UI telemetry from CC evaluation`

---

## Task 5: Acceptance test no WebSocket

**File:** `backend/tests/test_race_loop_no_ws.py`

- [ ] `hub.tick_count >= 3` after 0.25s simulated loop
- [ ] `cc.on_frame.call_count >= 3`
- [ ] Commit `test(race): CC evaluates without WebSocket clients`

---

## Hito 1 GATE (orquestador MUST verify)

All must pass before Hito 2:

```powershell
cd backend
python -m pytest tests/test_telemetry_hub.py tests/test_race_tick_loop.py tests/test_race_loop_no_ws.py tests/test_ws_telemetry_hub.py tests/test_config_update_ack_ws.py -v
```

```powershell
Select-String -Path src\routers\websocket.py -Pattern "crewchief_loop.on_frame"
```

Expected: **zero matches** inside `telemetry_sender_loop` (may still exist in tests/mocks elsewhere).

**Manual (optional):** Start backend without Tauri; confirm logs show tick activity / no WS required for CC.

| Criterio | V2 |
|----------|-----|
| CC sin WS | test_race_loop_no_ws ✅ |

---

## Failure modes

| Síntoma | Causa | Fix |
|---------|-------|-----|
| Double CC eval | Forgot to remove on_frame in WS | Task 4 |
| Spotter stopped | race_loop not wired or spotter.enabled false | Task 3 |
| UI no telemetry | hub not updated | Task 2 step 5 |
| Tests hang | race_tick_loop sleep in test without cancel | use cancel in test |

---

## DoD Hito 1

- [ ] `race_tick_loop` runs from lifespan
- [ ] `spotter_eval_loop` not spawned from lifespan
- [ ] CC not in `telemetry_sender_loop`
- [ ] All GATE tests green
- [ ] Orquestador marks INDEX gate ✅
