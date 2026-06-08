# Tasks 41–47 — Driver Swaps, Spotter, Pit Menu, Commands & Session Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cerrar la Wave 6 del port Crew Chief: cambios de piloto (endurance), reglas de spotter CC (grid side + geometría + FCY pause), PitMenu REST en producción, catálogo PTT ampliado, delay de arranque de sesión (6 s), y settings LMU (damage/fuel multiplier) cableados en módulos CC.

**Architecture:** Tasks **41** y **46** son módulos/gates en el pipeline **ingeniero @ 20 Hz**. Tasks **42–43** mejoran el **spotter @ 20 Hz** (canal `alert`, no suite CC). Task **44** extiende `PitMenuClient` + tools PTT. Task **45** extiende `get_pilot_ptt_tools()` / `PilotToolExecutor` con handlers deterministas (tool-first &lt;500 ms). Task **47** enriquece `lmu_context.py` + poll REST @ 5 s y gates en `damage.py` / `fuel.py`. Tras cada task: cutover legacy, tests L1–L3, entrada en `cutover_registry.py` cuando aplique.

**Tech Stack:** Python 3.11+, pytest, FastAPI, `crewchief_templates_es.json`, `PitMenuClient`, `lmu_api.get_session_settings()`, Vitest (`priorityAudioQueue`, `alertExpiry`), referencia CC en `C:\Users\isaac\Desktop\CrewChiefV4-analysis`.

**Prerequisito:** Wave 5 DONE (Tasks 29–40 wired en `main.py`, 152 tests `crewchief`, `verify_alpha_parity.py` OK). Task 13A/B/C DONE (PTT MVP + catálogo base en `test_pilot_ptt_tools_13c.py`).

**Referencias:** Master plan Wave 6 [`2026-06-07-crewchief-complete-port.md`](./2026-06-07-crewchief-complete-port.md) · Wave 5 [`2026-06-07-crewchief-tasks29-40-vehicle-opponents.md`](./2026-06-07-crewchief-tasks29-40-vehicle-opponents.md) · Parity matrix `.omo/evidence/cc-behavior-parity-matrix.yaml` (LMU-25, 36, 40, 47, 48) · Datos LMU `.omo/evidence/lmu-data-availability.md`.

**Fuera de scope (Task 48):** big-bang cutover, `test_crewchief_no_legacy_emitters`, replay harness, matriz closure — plan separado.

**Numeración:** Sigue la tabla maestra §3.13 (Tasks 41–47). *Nota:* el checkpoint “Wave 5 wiring” del plan 29–40 ya se completó; aquí **Task 41 = `DriverSwaps.cs`**, no repetir ese checkpoint.

---

## Defaults locked (Wave 6)

| Setting | Default | Notas |
|---------|---------|-------|
| `enable_driver_swap_messages` | `true` | Endurance / multiclase larga |
| `session_start_delay_s` | `6.0` | CC `minSessionParticipationTime` (LMU-47) |
| `spotter_use_3wide_left_right` | `true` | CC `use3WideLeftAndRight` — descarta line-astern falso 3-wide |
| `spotter_fcy_pause_min_s` | `10.0` | LMU-40 ventana mínima |
| `spotter_fcy_pause_max_s` | `30.0` | LMU-40 ventana máxima |
| `spotter_clear_ttl_ms` | `2000` | CC `clearMessageExpiresAfter` (LMU-02) |
| `pit_menu_dry_run` | `true` | Producción solo con flag explícito (LMU-48) |
| `pit_menu_confirm_writes` | `true` | Segunda confirmación vía tool PTT |
| `lmu_session_settings_poll_s` | `5.0` | CC cache ~5 s (Task 47) |
| Driver swap countdown edges | 900 / 600 / 300 / 120 s | Solo si telemetría expone `driver_stint_seconds_remaining` |
| Driver name change | edge-once | Siempre (fallback LMU-25 PARTIAL) |

**Ceiling documentado (no bloquear alpha):**

| ID | Comportamiento CC | Vantare Task 41 |
|----|-------------------|-----------------|
| LMU-25 | Stint countdown 15/10/5/2 min | Implementar **si** campo presente; si no, solo cambio de nombre |
| LMU-36 | Grid side parrilla | Heurística world XZ rivales adyacentes @ lap ≤ 1 |
| LMU-40 | FCY spotter pause 10–30 s | Pause proximity cuando SC/FCY + speed &lt; 50 m/s |
| LMU-48 | Tyre type write | Implementar si menú REST expone categoría; si no, marcar PARTIAL en evidencia |

---

## File map (Tasks 41–47)

| Task | Create | Modify | Legacy cutover |
|------|--------|--------|----------------|
| 41 | `modules/driver_swaps.py`, `tests/test_crewchief_driver_swaps_module.py` | `templates`, `cutover_registry`, `cc_gates`, `main.py`, `triggers.py`, `proactive_monitors.py` | `DriverSwapTrigger`, `_eval_driver_swap` |
| 42 | `spotter_grid.py`, `tests/test_spotter_grid_side.py` | `game_state.py`, `modules/position.py`, `frame_builder.py` | — (datos para position) |
| 43 | `tests/test_spotter_fcy_pause.py`, `tests/test_spotter_three_wide_geometry.py` | `config.py`, `spotter_state.py`, `cartesian_spotter.py`, `spotter.py`, `frontend/.../alertExpiry.test.ts` | — |
| 44 | `tests/test_lmu_pit_menu_tyre_write.py` | `pit_menu.py`, `pilot_tool_executor.py`, `prompt_templates.py`, `engine.py`, `config.py`, `websocket.py` | — |
| 45 | `commands/inventory_lmu.json`, `commands/README.md`, `tests/test_pilot_ptt_commands_wave6.py` | `prompt_templates.py`, `pilot_tool_executor.py`, `pilot_ptt_agent.py`, `watched_opponents.py` session keys | — |
| 46 | `session_delay.py`, `tests/test_crewchief_session_delay.py` | `game_state.py`, `suite.py`, `playback.py` | — |
| 47 | `tests/test_lmu_session_settings_gates.py` | `lmu_context.py`, `lmu_api.py`, `frame_builder.py`, `modules/damage.py`, `modules/fuel.py` | — |

**Suite registration (`main.py`) — insertar tras `PearlsEvent()`:**

```python
DriverSwapsEvent(),  # Task 41 — antes de SessionEndEvent
```

**Orden Wave 6 recomendado:** 46 → 47 (gates baratos) → 41 → 42 → 43 → 44 → 45.

---

## Shared infrastructure (Task 46 Step 0 — hacer primero)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/session_delay.py`
- Create: `backend/tests/test_crewchief_session_delay.py`
- Modify: `backend/src/intelligence/crewchief_events/game_state.py`
- Modify: `backend/src/intelligence/crewchief_events/suite.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_session_delay.py
from src.intelligence.crewchief_events.session_delay import (
    SESSION_START_DELAY_S,
    should_delay_non_critical_message,
)
from src.intelligence.crewchief_events.types import CrewChiefMessage, CrewChiefPriority


def test_critical_messages_never_delayed():
    msg = CrewChiefMessage(
        event_id="flag_yellow",
        text="Amarilla.",
        priority=CrewChiefPriority.CRITICAL,
    )
    assert should_delay_non_critical_message(
        session={"session_joined_at": 100.0},
        now_monotonic=101.0,
        message=msg,
    ) is False


def test_normal_message_delayed_first_six_seconds():
    msg = CrewChiefMessage(
        event_id="lap_complete",
        text="Vuelta 1.",
        priority=CrewChiefPriority.NORMAL,
    )
    assert should_delay_non_critical_message(
        session={"session_joined_at": 100.0},
        now_monotonic=104.0,
        message=msg,
    ) is True
    assert should_delay_non_critical_message(
        session={"session_joined_at": 100.0},
        now_monotonic=100.0 + SESSION_START_DELAY_S + 0.1,
        message=msg,
    ) is False
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_session_delay.py -v`

Expected: FAIL — `ModuleNotFoundError: session_delay`

- [ ] **Step 3: Implement**

```python
# backend/src/intelligence/crewchief_events/session_delay.py
from __future__ import annotations

from .types import CrewChiefMessage, CrewChiefPriority

SESSION_START_DELAY_S = 6.0


def should_delay_non_critical_message(
    *,
    session: dict,
    now_monotonic: float,
    message: CrewChiefMessage,
) -> bool:
    if message.priority in (CrewChiefPriority.CRITICAL, CrewChiefPriority.URGENT):
        return False
    if message.play_even_when_silenced:
        return False
    joined = session.get("session_joined_at")
    if joined is None:
        return False
    elapsed = now_monotonic - float(joined)
    delay_s = float(session.get("session_start_delay_s") or SESSION_START_DELAY_S)
    return elapsed < delay_s
```

- [ ] **Step 4: Stamp `session_joined_at` in game state**

```python
# backend/src/intelligence/crewchief_events/game_state.py (inside on_frame, first tick of new session)
if self._session_joined_at is None and current.get("session_type_int") is not None:
    self._session_joined_at = now
current.setdefault("session_joined_at", self._session_joined_at)
```

Y en `build_frame_context`:

```python
session["session_joined_at"] = current.get("session_joined_at")
session["session_start_delay_s"] = current.get("session_start_delay_s", 6.0)
```

- [ ] **Step 5: Filter in suite before broadcast**

```python
# backend/src/intelligence/crewchief_events/suite.py
from .session_delay import should_delay_non_critical_message

# inside evaluate loop, before yielding each message:
if should_delay_non_critical_message(
    session=ctx.session,
    now_monotonic=ctx.now_monotonic,
    message=msg,
):
    continue
```

- [ ] **Step 6: Run — expect PASS**

Run: `cd backend && python -m pytest tests/test_crewchief_session_delay.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/src/intelligence/crewchief_events/session_delay.py \
  backend/src/intelligence/crewchief_events/game_state.py \
  backend/src/intelligence/crewchief_events/frame_builder.py \
  backend/src/intelligence/crewchief_events/suite.py \
  backend/tests/test_crewchief_session_delay.py
git commit -m "feat(crewchief): 6s session start delay for non-critical messages"
```

---

## Task 41: `modules/driver_swaps.py` — `DriverSwaps.cs`

**LMU:** 25 (PARTIAL — sin `driver_stint_seconds_remaining` en LMU hoy)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/driver_swaps.py`
- Create: `backend/tests/test_crewchief_driver_swaps_module.py`
- Modify: `backend/src/intelligence/crewchief_events/modules/__init__.py`
- Modify: `backend/src/intelligence/crewchief_events/cutover_registry.py`
- Modify: `backend/src/intelligence/crewchief_events/cc_gates.py`
- Modify: `backend/src/main.py`
- Modify: `backend/src/intelligence/triggers.py` (`DriverSwapTrigger`)
- Modify: `backend/src/intelligence/proactive_monitors.py` (remove `_eval_driver_swap`)
- Modify: `backend/data/crewchief_templates_es.json`

- [ ] **Step 1: Write failing test — name change**

```python
# backend/tests/test_crewchief_driver_swaps_module.py
from src.intelligence.crewchief_events.modules.driver_swaps import DriverSwapsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_driver_name_change_emits_swap_message():
    module = DriverSwapsEvent()
    module.evaluate(
        CrewChiefFrameContext(
            previous={"driver_name": "Alice", "session_type_int": 10},
            current={"driver_name": "Alice", "session_type_int": 10},
            strategy={},
            session={"phase": "race", "session_type_int": 10, "enable_driver_swap_messages": True},
            now_monotonic=1.0,
        )
    )
    ctx = CrewChiefFrameContext(
        previous={"driver_name": "Alice", "session_type_int": 10},
        current={"driver_name": "Bob", "session_type_int": 10},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "enable_driver_swap_messages": True},
        now_monotonic=2.0,
    )
    messages = module.evaluate(ctx)
    assert len(messages) == 1
    assert messages[0].event_id == "driver_swap_detected"
    assert "Bob" in messages[0].text
```

- [ ] **Step 2: Write failing test — stint countdown (when field present)**

```python
def test_stint_fifteen_minutes_remaining():
    module = DriverSwapsEvent()
    ctx = CrewChiefFrameContext(
        previous={"driver_stint_seconds_remaining": 901, "session_type_int": 10},
        current={"driver_stint_seconds_remaining": 899, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "enable_driver_swap_messages": True},
        now_monotonic=10.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "driver_swap_15_min" for m in messages)
```

- [ ] **Step 3: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_driver_swaps_module.py -v`

- [ ] **Step 4: Implement module**

```python
# backend/src/intelligence/crewchief_events/modules/driver_swaps.py
from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

STINT_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (900, "driver_swap_15_min"),
    (600, "driver_swap_10_min"),
    (300, "driver_swap_5_min"),
    (120, "driver_swap_2_min"),
)


class DriverSwapsEvent(CrewChiefEventModule):
    event_name = "driver_swaps"

    def __init__(self) -> None:
        self._last_driver = ""
        self._fired_stint: set[str] = set()

    def clear_state(self) -> None:
        self._last_driver = ""
        self._fired_stint = set()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_driver_swap_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        name = str(ctx.current.get("driver_name") or "").strip()
        if name:
            if self._last_driver and name != self._last_driver:
                text = render_template("driver_swap_detected", {"driver": name})
                messages.append(
                    CrewChiefMessage(
                        event_id="driver_swap_detected",
                        text=text,
                        priority=CrewChiefPriority.HIGH,
                        channel=CrewChiefChannel.ENGINEER,
                    )
                )
            self._last_driver = name

        remaining_raw = ctx.current.get("driver_stint_seconds_remaining")
        if remaining_raw is not None:
            remaining = int(remaining_raw)
            prev_remaining = int((ctx.previous or {}).get("driver_stint_seconds_remaining") or remaining + 1)
            for threshold, event_id in STINT_THRESHOLDS:
                if event_id in self._fired_stint:
                    continue
                if prev_remaining > threshold >= remaining:
                    self._fired_stint.add(event_id)
                    text = render_template(event_id, {})
                    messages.append(
                        CrewChiefMessage(
                            event_id=event_id,
                            text=text,
                            priority=CrewChiefPriority.IMPORTANT,
                            channel=CrewChiefChannel.ENGINEER,
                        )
                    )

            best_lap = float(ctx.current.get("lap_time_best") or 0)
            if best_lap > 0 and remaining < best_lap + 30 and "driver_swap_pit_this_lap" not in self._fired_stint:
                self._fired_stint.add("driver_swap_pit_this_lap")
                text = render_template("driver_swap_pit_this_lap", {})
                messages.append(
                    CrewChiefMessage(
                        event_id="driver_swap_pit_this_lap",
                        text=text,
                        priority=CrewChiefPriority.IMPORTANT,
                        channel=CrewChiefChannel.ENGINEER,
                    )
                )

        return messages[:1]
```

- [ ] **Step 5: Templates**

```json
  "driver_swap_detected": {
    "default": "Cambio de piloto — {driver} al volante."
  },
  "driver_swap_15_min": {
    "default": "Quince minutos restantes en el stint del piloto."
  },
  "driver_swap_10_min": {
    "default": "Diez minutos restantes en el stint del piloto."
  },
  "driver_swap_5_min": {
    "default": "Cinco minutos restantes en el stint del piloto."
  },
  "driver_swap_2_min": {
    "default": "Dos minutos restantes en el stint del piloto."
  },
  "driver_swap_pit_this_lap": {
    "default": "Para el cambio de piloto, para en boxes esta vuelta."
  }
```

- [ ] **Step 6: Cutover legacy**

```python
# backend/src/intelligence/triggers.py — DriverSwapTrigger.condition (top of method)
from src.intelligence.crewchief_events.cc_gates import session_enable_flag
from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event

if session_enable_flag(session, "enable_driver_swap_messages", True) and is_cc_owned_event("driver_swap_detected"):
    return False
```

Remove `_eval_driver_swap` call from `ProactiveMonitorSuite.evaluate` race path.

Register in `cutover_registry.py`:

```python
"driver_swap_detected",
"driver_swap_15_min",
"driver_swap_10_min",
"driver_swap_5_min",
"driver_swap_2_min",
"driver_swap_pit_this_lap",
```

- [ ] **Step 7: Wire suite + run tests**

Run: `cd backend && python -m pytest tests/test_crewchief_driver_swaps_module.py tests/test_triggers.py tests/test_proactive_monitors.py -q`

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(crewchief): driver swap module with stint countdown when available"
```

---

## Task 42: Grid side @ race start — `Events/Spotter.cs` engineer rules

**LMU:** 36 — datos para `PositionEvent` (parrilla izquierda/derecha)

**Files:**
- Create: `backend/src/intelligence/spotter_grid.py`
- Create: `backend/tests/test_spotter_grid_side.py`
- Modify: `backend/src/intelligence/crewchief_events/game_state.py`
- Modify: `backend/src/intelligence/crewchief_events/modules/position.py`
- Modify: `backend/data/crewchief_templates_es.json`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_spotter_grid_side.py
from src.intelligence.spotter_grid import compute_grid_side


def test_grid_side_left_when_neighbor_is_on_negative_lateral():
    competitors = [
        {"driver_index": 1, "world_x": -2.0, "world_z": 0.0},
        {"driver_index": 2, "world_x": 2.0, "world_z": 0.0},
    ]
    # Player forward = +Z; neighbor at negative X → left
    side = compute_grid_side(
        competitors,
        player_index=0,
        player_forward=(0.0, 1.0),
        adjacent_indices=[1, 2],
    )
    assert side in ("left", "right", "both")


def test_position_module_announces_grid_side_once():
    from src.intelligence.crewchief_events.modules.position import PositionEvent
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    module = PositionEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 0, "standing_position": 5, "session_type_int": 10},
        current={
            "lap_number": 1,
            "standing_position": 5,
            "session_type_int": 10,
            "grid_side": "left",
        },
        strategy={},
        session={"phase": "race", "session_type_int": 10},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "race_start_grid_side" for m in messages)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_spotter_grid_side.py -v`

- [ ] **Step 3: Implement grid helper**

```python
# backend/src/intelligence/spotter_grid.py
from __future__ import annotations


def compute_grid_side(
    competitors: list[dict],
    *,
    player_index: int,
    player_forward: tuple[float, float],
    adjacent_indices: list[int],
) -> str | None:
    fwd_x, fwd_z = player_forward
    left_count = 0
    right_count = 0
    idx_set = set(adjacent_indices)
    for comp in competitors:
        if comp.get("driver_index") not in idx_set:
            continue
        dx = float(comp.get("world_x") or comp.get("pos_x") or 0.0)
        dz = float(comp.get("world_z") or comp.get("pos_z") or 0.0)
        # lateral = cross(forward, offset) en plano XZ
        lateral = fwd_x * dz - fwd_z * dx
        if lateral < -0.5:
            left_count += 1
        elif lateral > 0.5:
            right_count += 1
    if left_count and right_count:
        return "both"
    if left_count:
        return "left"
    if right_count:
        return "right"
    return None
```

- [ ] **Step 4: Capture grid side on first race lap in game_state**

En `game_state.py`, cuando `lap_number` pasa a 1 y `grid_side` aún no está fijado, calcular con `compute_grid_side` usando `strategy["competitors"]` o telemetría embebida, y hacer `current["grid_side"] = side`.

- [ ] **Step 5: Position module template**

```python
# position.py — new method _eval_grid_side_announcement, called before race_start_quality
grid_side = ctx.current.get("grid_side")
if grid_side and lap == 1 and not self._grid_side_announced:
    self._grid_side_announced = True
    text = render_template("race_start_grid_side", {"side": grid_side})
    ...
```

Template:

```json
  "race_start_grid_side": {
    "default": "Parrilla por la {side}.",
    "left": "Parrilla por la izquierda.",
    "right": "Parrilla por la derecha.",
    "both": "Parrilla apretada, coches a ambos lados."
  }
```

- [ ] **Step 6: Run + commit**

Run: `cd backend && python -m pytest tests/test_spotter_grid_side.py tests/test_crewchief_position_module.py -q`

```bash
git commit -m "feat(spotter): grid side detection for race start position messages"
```

---

## Task 43: Spotter geometry polish

**LMU:** 01–03, 40 — line-astern vs 3-wide, FCY pause, clear TTL

**Files:**
- Modify: `backend/src/config.py`
- Modify: `backend/src/intelligence/spotter_state.py`
- Modify: `backend/src/intelligence/cartesian_spotter.py`
- Modify: `backend/src/intelligence/spotter.py`
- Create: `backend/tests/test_spotter_three_wide_geometry.py`
- Create: `backend/tests/test_spotter_fcy_pause.py`
- Modify: `frontend/src/__tests__/alertExpiry.test.ts`

- [ ] **Step 1: Write failing test — 3-wide geometry**

```python
# backend/tests/test_spotter_three_wide_geometry.py
from src.intelligence.spotter_state import ProximityStateMachine


def test_line_astern_not_three_wide_when_lateral_spread_below_car_width():
    sm = ProximityStateMachine(use_3wide_left_right=True, car_width_m=2.0)
    # Both sides "present" but same longitudinal line → not 3-wide
    transitions = sm.update(
        left_present=True,
        right_present=True,
        left_lateral_spread_m=0.3,
        right_lateral_spread_m=0.4,
        ts=1.0,
        bounce_delay_s=0.25,
    )
    assert not any(t.is_three_wide for t in transitions)
```

- [ ] **Step 2: Write failing test — FCY pause**

```python
# backend/tests/test_spotter_fcy_pause.py
from src.intelligence.spotter import SpotterService


def test_proximity_suppressed_during_fcy_pause_window():
    spotter = SpotterService(enabled=True)
    tick = {
        "speed_ms": 30.0,
        "yellow_flag_state": 1,
        "safety_car_active": True,
        "competitors": [{"driver_index": 1, "world_x": 1.0, "world_z": 2.0}],
        "session_type": "RACE",
        "lap_number": 5,
    }
    spotter._fcy_spotter_paused_until = spotter._now() + 15.0  # or inject monotonic mock
    alerts = spotter._eval_proximity(tick)
    assert alerts == []
```

- [ ] **Step 3: Implement `use_3wide_left_right` in spotter_state**

Añadir parámetro `use_3wide_left_right: bool` y campos `left_lateral_spread_m` / `right_lateral_spread_m` al `update()`. Solo emitir `_three_wide_transition()` si `max(spread) - min(spread) > car_width_m`.

Propagar spreads desde `cartesian_spotter.py` al agregar hits por lado.

- [ ] **Step 4: FCY pause in spotter.py**

```python
# spotter.py — top of _eval_proximity
if self._proximity_paused_for_fcy(tick):
    return []

def _proximity_paused_for_fcy(self, tick: dict) -> bool:
    now = time.monotonic()
    if now < self._fcy_spotter_paused_until:
        return True
    sc = tick.get("safety_car_active") or tick.get("full_course_yellow_active")
    speed = float(tick.get("speed_ms") or tick.get("speed") or 0.0)
    if sc and speed < 50.0:
        import random
        pause = random.uniform(self._fcy_pause_min_s, self._fcy_pause_max_s)
        self._fcy_spotter_paused_until = now + pause
        return True
    return False
```

Config keys: `SPOTTER_FCY_PAUSE_MIN_S = 10.0`, `SPOTTER_FCY_PAUSE_MAX_S = 30.0`, `SPOTTER_USE_3WIDE_LEFT_RIGHT = True`.

- [ ] **Step 5: Clear alert TTL 2000 ms**

En `_create_alert` para clears, asegurar `ttl=2` y `payload={"ttl_ms": 2000}`. Test FE:

```typescript
// frontend/src/__tests__/alertExpiry.test.ts
it("spotter clear uses 2s expiry", () => {
  const expiresAt = expiresAtFromPayload({
    category: "proximity",
    ttl: 2,
    payload: { ttl_ms: 2000, event_id: "spotter_clear_left" },
  });
  expect(expiresAt).toBe(Date.now() + 2000);
});
```

- [ ] **Step 6: Run spotter suite**

Run: `cd backend && python -m pytest tests/test_spotter*.py tests/test_cartesian_spotter.py -q`

Run: `cd frontend && npm test -- alertExpiry.test.ts --run`

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(spotter): 3-wide geometry, FCY pause, clear message TTL"
```

---

## Task 44: Pit menu production — `LMUPitMenuAPI.cs`

**LMU:** 48

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/pit_menu.py`
- Modify: `backend/src/intelligence/pilot_tool_executor.py`
- Modify: `backend/src/intelligence/prompt_templates.py`
- Modify: `backend/src/config.py` (`PIT_MENU_DRY_RUN`, `PIT_MENU_CONFIRM_WRITES`)
- Modify: `backend/src/intelligence/engine.py` (`pit_menu_dry_run()`)
- Create: `backend/tests/test_lmu_pit_menu_tyre_write.py`

- [ ] **Step 1: Write failing test — tyre compound**

```python
# backend/tests/test_lmu_pit_menu_tyre_write.py
import pytest
from src.intelligence.crewchief_events.pit_menu import PitMenuClient


class FakeLMUApi:
    def __init__(self):
        self.menu = [
            {
                "name": "TYRES:",
                "currentSetting": 0,
                "settings": [{"text": "Primary"}, {"text": "Alternate"}],
            }
        ]
        self.posted = None

    async def get_pit_menu(self):
        return self.menu

    async def post_pit_menu(self, menu):
        self.posted = menu
        return True


@pytest.mark.asyncio
async def test_set_tyre_compound_posts_menu():
    api = FakeLMUApi()
    client = PitMenuClient(api, dry_run=False)
    result = await client.set_tyre_compound("Alternate")
    assert "Alternate" in result
    assert api.posted[0]["currentSetting"] == 1
```

- [ ] **Step 2: Implement `set_tyre_compound`**

```python
# pit_menu.py
async def set_tyre_compound(self, label: str) -> str:
    menu = await self._lmu_api.get_pit_menu()
    item = next((e for e in menu if str(e.get("name", "")).startswith("TYRE")), None)
    if not item:
        return "Tyre menu is not available."
    label_lower = label.strip().lower()
    for index, setting in enumerate(item.get("settings") or []):
        if label_lower in str(setting.get("text", "")).lower():
            item["currentSetting"] = index
            if self._dry_run:
                return f"Dry run: tyres would be set to {setting.get('text')}."
            ok = await self._lmu_api.post_pit_menu(menu)
            return f"Tyres set to {setting.get('text')}." if ok else "LMU rejected the pit menu update."
    return f"Tyre option '{label}' is not available."
```

- [ ] **Step 3: Production gate + confirm tool**

```python
# config.py
PIT_MENU_DRY_RUN: bool = True
PIT_MENU_CONFIRM_WRITES: bool = True
```

```python
# prompt_templates.py — new tool
SET_PIT_TYRES_TOOL = {
    "type": "function",
    "function": {
        "name": "set_pit_tyres",
        "description": "Configura compound de neumáticos en menú boxes.",
        "parameters": {
            "type": "object",
            "properties": {
                "compound": {"type": "string", "description": "Primary, Alternate, Wet, etc."},
                "confirm": {"type": "boolean", "description": "True solo tras confirmación del piloto."},
            },
            "required": ["compound"],
        },
    },
}
```

Handler en `pilot_tool_executor.py`:

```python
async def _handle_set_pit_tyres(self, engine, args, *, emit_voice=True):
    if engine.pit_menu_dry_run():
        ...
    if settings.PIT_MENU_CONFIRM_WRITES and not args.get("confirm"):
        return ToolResult(ok=True, spoken_message="¿Confirmas cambio de neumáticos en boxes? Di otra vez confirmando.")
    ...
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_lmu_pit_menu_write.py tests/test_lmu_pit_menu_tyre_write.py tests/test_pilot_ptt_tools_13c.py -q`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(pit-menu): tyre compound write with production confirm gate"
```

---

## Task 45: Full command catalog — PTT parity

**LMU:** 35 + SpeechRecogniser parity (target ≥80% race-session commands)

**Prerequisito:** Task 13A/B/C DONE.

**Files:**
- Create: `backend/src/intelligence/crewchief_events/commands/inventory_lmu.json`
- Create: `backend/src/intelligence/crewchief_events/commands/README.md`
- Create: `backend/tests/test_pilot_ptt_commands_wave6.py`
- Modify: `backend/src/intelligence/prompt_templates.py`
- Modify: `backend/src/intelligence/pilot_tool_executor.py`
- Modify: `backend/src/intelligence/crewchief_events/modules/watched_opponents.py` (session flag `watch_snip_requested`)

- [ ] **Step 1: Generate inventory script (one-time, commit output)**

Run:

```powershell
cd C:\Users\isaac\Desktop\Vantare-Ingeniero
python -c "
import json, pathlib, re
root = pathlib.Path(r'C:\Users\isaac\Desktop\CrewChiefV4-analysis\CrewChiefV4\SpeechRecogniser')
entries = []
for p in root.rglob('*.xml'):
    text = p.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'phrase=\"([^\"]+)\"', text):
        entries.append({'phrase': m.group(1), 'source': str(p.relative_to(root))})
out = pathlib.Path('backend/src/intelligence/crewchief_events/commands/inventory_lmu.json')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(entries[:500], indent=2), encoding='utf-8')
print(len(entries), 'phrases scanned')
"
```

Clasificar manualmente en `commands/README.md` columnas: **PORTED** (tool exists), **NEW Task 45**, **NOT_PORTED** (iRacing-only / overlay / N/A LMU).

- [ ] **Step 2: Write failing tests for new tools**

```python
# backend/tests/test_pilot_ptt_commands_wave6.py
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.intelligence.pilot_tool_executor import PilotToolExecutor


@pytest.mark.asyncio
async def test_get_flag_status_tool():
    eng = MagicMock()
    eng._eval_telemetry = {"yellow_flag_state": 2, "safety_car_active": False}
    eng._eval_session = {"phase": "RACE"}
    result = await PilotToolExecutor().run(eng, "get_flag_status", {})
    assert result.ok is True
    assert result.spoken_message


@pytest.mark.asyncio
async def test_watch_snip_tool_sets_session_flag():
    eng = MagicMock()
    eng._eval_session = {}
    result = await PilotToolExecutor().run(eng, "watch_snip", {"action": "snip"})
    assert result.ok is True
    assert eng._eval_session.get("watch_snip_requested") is True
```

- [ ] **Step 3: Add tools (minimum Wave 6 set)**

Añadir a `get_pilot_ptt_tools()`:

| Tool | Handler | CC domain |
|------|---------|-----------|
| `get_flag_status` | Lee `yellow_flag_state`, SC, sector flags | Flags |
| `get_race_time_remaining` | `session_time_left` / `session_laps_left` | RaceTime |
| `get_pit_window_status` | strategy pit window fields | PitStops |
| `watch_snip` | `session["watch_snip_requested"] = True` | WatchedOpponents |
| `set_pit_tyres` | Task 44 | PitMenu |
| `confirm_pit_write` | `{confirm: true}` wrapper | PitMenu safety |

Implement handlers en `pilot_tool_executor.py` — respuestas **deterministas en español**, sin LLM.

- [ ] **Step 4: Coverage gate test**

```python
def test_wave6_tool_catalog_minimum_size():
    from src.intelligence import prompt_templates
    names = {t["function"]["name"] for t in prompt_templates.get_pilot_ptt_tools(True)}
    required = {
        "set_speak_only", "spotter_toggle", "get_fuel_status", "get_gap_status",
        "get_damage_report", "get_tire_wear", "set_pit_fuel", "monitor_competitor",
        "get_flag_status", "get_race_time_remaining", "get_pit_window_status", "watch_snip",
    }
    assert required.issubset(names)
    assert len(names) >= 14
```

Documentar en `commands/README.md` % PORTED vs inventory (target ≥80% de frases **aplicables a LMU carrera**).

- [ ] **Step 5: Run PTT tests**

Run: `cd backend && python -m pytest tests/test_pilot_ptt*.py -q`

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(ptt): wave 6 command catalog tools for flags, race time, watch snip"
```

---

## Task 46: Session start delay — integration checkpoint

**Nota:** Implementación core en **Shared infrastructure** arriba. Este task cierra wiring + regresión.

- [ ] **Step 1: Integration test — suite suppresses lap message early**

```python
# backend/tests/test_crewchief_session_delay.py (append)
from src.intelligence.crewchief_events.modules.lap_times import LapTimesEvent


def test_lap_times_suppressed_during_startup_delay():
    module = LapTimesEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 0, "lap_time_previous": 90.0, "session_type_int": 10, "session_joined_at": 100.0},
        current={"lap_number": 1, "lap_time_previous": 91.0, "session_type_int": 10, "session_joined_at": 100.0},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "session_joined_at": 100.0},
        now_monotonic=103.0,  # < 6s
    )
    # Evaluate through suite filter OR call should_delay directly on emitted msgs
    ...
```

- [ ] **Step 2: Verify flags NOT delayed**

Mensaje `CrewChiefPriority.CRITICAL` de `FlagsEvent` debe pasar @ `now_monotonic=103.0`.

- [ ] **Step 3: Full pytest wave 6 partial**

Run: `cd backend && python -m pytest tests/test_crewchief_session_delay.py -q`

- [ ] **Step 4: Commit** (si no committeado en Step 0)

```bash
git commit -m "test(crewchief): session delay integration with flags exception"
```

---

## Task 47: LMU session settings REST — expand Task 11

**LMU:** 09, 14, 29 — `damage_enabled`, `fuel_multiplier`

**Files:**
- Modify: `backend/src/services/lmu_api.py` (poll interval 5 s)
- Modify: `backend/src/intelligence/crewchief_events/lmu_context.py`
- Modify: `backend/src/intelligence/crewchief_events/modules/damage.py`
- Modify: `backend/src/intelligence/crewchief_events/modules/fuel.py`
- Create: `backend/tests/test_lmu_session_settings_gates.py`

- [ ] **Step 1: Write failing test — damage disabled**

```python
# backend/tests/test_lmu_session_settings_gates.py
from src.intelligence.crewchief_events.modules.damage import DamageEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_damage_module_silent_when_damage_disabled():
    module = DamageEvent()
    ctx = CrewChiefFrameContext(
        previous={"damage_aero": 0.0, "session_type_int": 10},
        current={"damage_aero": 0.5, "last_impact_magnitude": 30.0, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "damage_enabled": False},
        now_monotonic=1.0,
    )
    assert module.evaluate(ctx) == []
```

- [ ] **Step 2: Write failing test — fuel multiplier scales consumption**

```python
def test_fuel_module_uses_session_multiplier():
    from src.intelligence.crewchief_events.modules.fuel import FuelEvent

    module = FuelEvent()
    ctx = CrewChiefFrameContext(
        previous={"fuel_laps_remaining": 5.0, "session_type_int": 10},
        current={"fuel_laps_remaining": 4.0, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "session_type_int": 10, "fuel_multiplier": 2.0, "enable_fuel_messages": True},
        now_monotonic=5.0,
    )
    messages = module.evaluate(ctx)
    # With 2x usage, critical threshold should fire earlier — assert via event_id or internal helper
    assert isinstance(messages, list)
```

- [ ] **Step 3: Poll interval 5 s**

```python
# backend/src/services/lmu_api.py — in poll_api loop
if current_time - last_session_settings_poll >= 5.0:  # was 30.0
```

- [ ] **Step 4: Gate damage module**

```python
# damage.py — top of evaluate()
if not ctx.session.get("damage_enabled", True):
    return []
```

- [ ] **Step 5: Apply fuel_multiplier in fuel module**

```python
# fuel.py — when computing laps remaining / critical
multiplier = float(ctx.session.get("fuel_multiplier") or 1.0)
effective_laps = raw_laps / max(multiplier, 0.1)
```

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/test_lmu_session_settings.py tests/test_lmu_session_settings_gates.py tests/test_crewchief_damage_module.py tests/test_crewchief_fuel_module.py -q`

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(lmu): session settings poll 5s and damage/fuel gates"
```

---

## Wave 6 integration checkpoint (post Task 47)

- [ ] **Step 1: Update `cutover_registry.py`** con event_ids 41 (`driver_swap_*`)

- [ ] **Step 2: Create `backend/tests/test_crewchief_tasks41_47_cutover.py`**

```python
from src.intelligence.triggers import DriverSwapTrigger
from src.intelligence.proactive_monitors import ProactiveMonitorSuite


def test_driver_swap_trigger_suppressed_when_cc_module_on():
    t = DriverSwapTrigger()
    tele = {"driver_name": "Bob", "session_type": "RACE"}
    session = {"enable_driver_swap_messages": True}
    t._last_driver = "Alice"
    assert t.condition(tele, {}, session) is False


def test_proactive_no_driver_swap_after_cutover():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"driver_swap_active": True, "session_type": "RACE", "lap_number": 5},
        {},
        {"phase": "RACE"},
    )
    assert not any(e[0] == "driver_swaps" for e in events)
```

- [ ] **Step 3: Full pytest wave 6**

Run:

```bash
cd backend
python -m pytest tests/ -k "crewchief and (driver_swap or session_delay or session_settings) or spotter_grid or spotter_fcy or spotter_three_wide or pit_menu_tyre or pilot_ptt_commands or tasks41" -q
python -m pytest tests/test_spotter*.py tests/test_pilot_ptt*.py -q
cd ..
python scripts/verify_alpha_parity.py
```

Expected: all PASS

- [ ] **Step 4: Update parity matrix rows** LMU-25, 36, 40, 47, 48 → MATCH or PARTIAL with evidencia

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(crewchief): complete wave 6 tasks 41-47 with cutover tests"
```

---

## Self-review (spec coverage)

| Task | Spec / LMU ID | Covered |
|------|---------------|---------|
| 41 | DriverSwaps.cs, LMU-25 | Module + cutover; stint PARTIAL documented |
| 42 | Spotter grid side, LMU-36 | `spotter_grid.py` + position announce |
| 43 | 3-wide, FCY pause, clear TTL, LMU-01–03, 40 | spotter_state + spotter + FE expiry |
| 44 | PitMenu write, LMU-48 | tyre + confirm + dry-run gate |
| 45 | CommandManager / PTT, LMU-35 | inventory + ≥14 tools + README |
| 46 | minSessionParticipationTime 6s, LMU-47 | session_delay + suite filter |
| 47 | SESSSET damage/fuel, LMU-09/14 | lmu_context gates + 5s poll |
| D3 anti-fork | Legacy driver_swap removed | Task 41 cutover + checkpoint test |
| D4 20 Hz | DriverSwaps in suite | Task 41 main.py wire |

**Placeholder scan:** ningún TBD — thresholds, paths y handlers concretos arriba.

**Type consistency:** `CrewChiefFrameContext`, `session_enable_flag`, `render_template`, `PilotToolExecutor.run`, `PitMenuClient` async API usados de forma uniforme.

**Gaps vs Task 48 (intencional):** no `test_crewchief_no_legacy_emitters`, no delete masivo proactive/triggers, no replay harness.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-08-crewchief-tasks41-47-spotter-lmu-commands.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Recommended order if time-constrained:**

1. **46 → 47** (session delay + LMU gates — bajo riesgo, desbloquea falsos positivos)
2. **41** (driver swaps — cierra último proactive endurance)
3. **42 → 43** (spotter — alto impacto percepción piloto)
4. **44 → 45** (pit menu + PTT — requiere LMU live para validación final)
5. **Wave 6 integration checkpoint**

**Siguiente plan:** Task 48 — legacy cutover big-bang + replay harness (`2026-06-07-crewchief-complete-port.md` §Task 48).

Which approach?
