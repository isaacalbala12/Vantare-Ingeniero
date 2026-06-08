# Tasks 23–28 — Core Race Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portar los 6 módulos CC de “core carrera” (`LapTimes`, `LapCounter`, `PushNow`, `SessionEndMessages`, `Fuel`, `PitStops`) a Python con mensajes deterministas, cutover de triggers/commentary legacy, y tests L1–L3.

**Architecture:** Cada módulo es un `CrewChiefEventModule` evaluado @ 20 Hz en `CrewChiefGameStateLoop`. Detectan **flancos** (lap complete, pit in/out, session over) comparando `ctx.previous` vs `ctx.current`. Templates ES vía `render_template()`. Triggers LLM (`PushNowTrigger`, `SessionEndTrigger`, etc.) se silencian cuando `is_cc_owned_event()` y el gate CC correspondiente está activo.

**Tech Stack:** Python 3.11+, pytest, `crewchief_templates_es.json`, `pit_prediction.py`, `fuel_safety.py`, `HistoryStore` / nuevo `FuelUsageStore`.

**Prerequisito:** Task 22 timings plan aplicado (o en paralelo si módulos independientes).

**LMU sector encoding (crítico — usar en todos los módulos):**

```python
# LMU mSector / current_sector: 0 = sector 3, 1 = sector 1, 2 = sector 2
def normalize_display_sector(raw: int) -> int:
    return {0: 3, 1: 1, 2: 2}.get(int(raw), int(raw))
```

**Defaults locked (CC-aligned):**
| Setting | Default |
|---------|---------|
| `enable_lap_time_messages` | `true` |
| `enable_lap_counter_messages` | `true` |
| `enable_session_end_messages` | `true` |
| `enable_fuel_messages` | `true` |
| `enable_push_now_messages` | `true` |
| `frequency_of_race_sector_delta_reports` | `5` (1–10) |
| `fuel_status_check_interval_s` | `5.0` |
| Fast lap tolerance | `0.05` s vs `lap_time_best` |
| Push window (laps) | `session_laps_left <= 3` |
| Push window (time) | `session_time_left <= 240` s (4 min CC) |
| Last lap | `session_laps_left == 1` → **ingeniero**, spotter `_eval_last_lap` OFF |

---

## Shared infrastructure (Task 23 Step 0 — do first)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/lap_edge.py`
- Create: `backend/tests/test_crewchief_lap_edge.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_lap_edge.py
from src.intelligence.crewchief_events.lap_edge import (
    lap_completed,
    normalize_display_sector,
    read_sector,
)


def test_lap_completed_on_lap_number_increase():
    assert lap_completed({"lap_number": 5}, {"lap_number": 6}) is True
    assert lap_completed({"lap_number": 5}, {"lap_number": 5}) is False


def test_normalize_lmu_sector():
    assert normalize_display_sector(0) == 3
    assert normalize_display_sector(1) == 1
    assert normalize_display_sector(2) == 2


def test_read_sector_prefers_current_sector():
    assert read_sector({"current_sector": 2, "sector": 1}) == 2
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_lap_edge.py -v`

- [ ] **Step 3: Implement**

```python
# backend/src/intelligence/crewchief_events/lap_edge.py
from __future__ import annotations


def normalize_display_sector(raw: int) -> int:
    return {0: 3, 1: 1, 2: 2}.get(int(raw), int(raw))


def read_sector(telemetry: dict) -> int:
    raw = telemetry.get("current_sector")
    if raw is None:
        raw = telemetry.get("sector")
    if raw is None:
        raw = telemetry.get("mSector")
    return int(raw if raw is not None else 1)


def lap_completed(previous: dict, current: dict) -> bool:
    prev_lap = int(previous.get("lap_number") or previous.get("completed_laps") or 0)
    curr_lap = int(current.get("lap_number") or current.get("completed_laps") or 0)
    return curr_lap > prev_lap and curr_lap > 0
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/lap_edge.py backend/tests/test_crewchief_lap_edge.py
git commit -m "feat(crewchief): shared lap edge and LMU sector helpers"
```

---

## File map (Tasks 23–28)

| Task | Create | Modify |
|------|--------|--------|
| 23 | `modules/lap_times.py`, `tests/test_crewchief_lap_times_module.py` | `templates`, `cutover_registry`, `proactive_monitors`, `__init__.py`, `main.py` |
| 24 | `modules/lap_counter.py`, `tests/test_crewchief_lap_counter_module.py` | `spotter.py`, `templates`, `cutover_registry`, suite |
| 25 | `modules/push_now.py`, `tests/test_crewchief_push_now_module.py` | `triggers.py`, `proactive_monitors`, `templates`, suite |
| 26 | `modules/session_end.py`, `tests/test_crewchief_session_end_module.py` | `triggers.py`, `proactive_monitors`, `templates`, suite |
| 27 | `fuel_usage_store.py`, `tests/test_fuel_usage_store.py` | `modules/fuel.py`, `triggers.py`, `spotter.py`, `templates`, suite |
| 28 | `modules/pit_stops.py`, `tests/test_crewchief_pit_stops_module.py` | `triggers.py`, `proactive_monitors`, `templates`, suite |

**Suite registration** (after each module, append to `main.py` + `modules/__init__.py`):

```python
from .lap_times import LapTimesEvent
from .lap_counter import LapCounterEvent
from .push_now import PushNowEvent
from .session_end import SessionEndEvent
from .pit_stops import PitStopsEvent
# FuelEvent already registered — expand in place
```

---

### Task 23: `lap_times.py` — `LapTimes.cs` (LMU-21, LMU-32 partial)

**Scope v1:** fast lap, invalid lap, consistency últimas 5 vueltas, sector delta **proxy** (duración entre cambios de sector vs mejor personal). **Defer:** splits nativos LMU cuando existan en telemetría.

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/lap_times.py`
- Modify: `backend/src/data/crewchief_templates_es.json`
- Modify: `backend/src/intelligence/proactive_monitors.py` (remove fast_lap from `_on_lap_complete`)
- Test: `backend/tests/test_crewchief_lap_times_module.py`

- [ ] **Step 1: Add templates to JSON**

```json
  "lap_personal_best": {
    "default": "¡Vuelta rápida personal! {time} segundos."
  },
  "lap_invalid": {
    "default": "Esa vuelta no cuenta — saliste de pista o cortaste."
  },
  "lap_consistency_improving": {
    "default": "Ritmo mejorando — últimas vueltas más rápidas."
  },
  "lap_consistency_worsening": {
    "default": "Ritmo cayendo — cuida los neumáticos y el tráfico."
  },
  "lap_consistency_stable": {
    "default": "Ritmo consistente en las últimas vueltas."
  },
  "sector_personal_best": {
    "default": "Sector {sector} rápido — {delta} mejor que tu mejor."
  },
  "sector_off_pace": {
    "default": "Sector {sector} lento — {delta} por debajo de tu mejor."
  }
```

- [ ] **Step 2: Write failing tests**

```python
# backend/tests/test_crewchief_lap_times_module.py
from src.intelligence.crewchief_events.modules.lap_times import LapTimesEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session={"phase": "race", "session_type_int": 10, "enable_lap_time_messages": True},
        now_monotonic=100.0,
    )


def test_personal_best_on_lap_complete():
    module = LapTimesEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 5, "lap_time_previous": 0, "lap_time_best": 90.0},
            {"lap_number": 6, "lap_time_previous": 89.95, "lap_time_best": 89.95, "lap_valid": True},
        )
    )
    assert any(m.event_id == "lap_personal_best" for m in messages)


def test_invalid_lap_message():
    module = LapTimesEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 3},
            {"lap_number": 4, "lap_time_previous": 95.0, "lap_valid": False},
        )
    )
    assert any(m.event_id == "lap_invalid" for m in messages)


def test_consistency_improving_after_five_laps():
    module = LapTimesEvent()
    module._lap_times = [92.0, 91.5, 91.0, 90.8, 90.5]
    messages = module.evaluate(
        _ctx(
            {"lap_number": 10, "lap_time_previous": 90.5},
            {"lap_number": 11, "lap_time_previous": 90.2, "lap_valid": True},
        )
    )
    assert any(m.event_id == "lap_consistency_improving" for m in messages)


def test_sector_delta_on_sector_change():
    module = LapTimesEvent()
    module._sector_entered_at = 90.0
    module._best_sector_duration = {1: 30.0}
    messages = module.evaluate(
        _ctx(
            {"current_sector": 1, "lap_number": 5},
            {"current_sector": 2, "lap_number": 5},
        )
    )
    module._sector_entered_at = 100.0  # 10s sector vs 30s best won't fire fast
    # Force fast sector: 25s elapsed
    module._sector_entered_at = 75.0
    messages = module.evaluate(
        _ctx(
            {"current_sector": 1, "lap_number": 5},
            {"current_sector": 2, "lap_number": 5},
        )
    )
    assert any(m.event_id == "sector_personal_best" for m in messages)
```

- [ ] **Step 3: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_lap_times_module.py -v`

- [ ] **Step 4: Implement `LapTimesEvent`**

```python
# backend/src/intelligence/crewchief_events/modules/lap_times.py
from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed, normalize_display_sector, read_sector
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

FAST_LAP_TOLERANCE_S = 0.05
SECTOR_FAST_DELTA_S = 0.15
SECTOR_SLOW_DELTA_S = 0.25
CONSISTENCY_LAP_COUNT = 5


class LapTimesEvent(CrewChiefEventModule):
    event_name = "lap_times"

    def __init__(self) -> None:
        self._lap_times: list[float] = []
        self._sector_entered_at: float = 0.0
        self._last_sector_raw: int | None = None
        self._best_sector_duration: dict[int, float] = {}
        self._last_consistency_at_lap: int = 0

    def clear_state(self) -> None:
        self.__init__()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_lap_time_messages", True):
            return []

        messages: list[CrewChiefMessage] = []
        messages.extend(self._eval_sector_timing(ctx))
        if lap_completed(ctx.previous, ctx.current):
            messages.extend(self._eval_lap_complete(ctx))
        return messages[:2]

    def _eval_lap_complete(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session):
            return []
        curr = ctx.current
        if curr.get("in_pits"):
            return []

        lap_time = float(curr.get("lap_time_previous") or 0)
        best = float(curr.get("lap_time_best") or 0)
        lap_valid = curr.get("lap_valid", True)
        out: list[CrewChiefMessage] = []

        if lap_valid is False:
            out.append(self._msg("lap_invalid", {}, CrewChiefPriority.NORMAL))
            return out

        if lap_time > 0:
            self._lap_times.append(lap_time)
            if len(self._lap_times) > 20:
                self._lap_times.pop(0)

        if lap_time > 0 and best > 0 and lap_time <= best + FAST_LAP_TOLERANCE_S:
            out.append(
                self._msg(
                    "lap_personal_best",
                    {"time": f"{lap_time:.3f}"},
                    CrewChiefPriority.IMPORTANT,
                )
            )

        lap_num = int(curr.get("lap_number") or 0)
        if len(self._lap_times) >= CONSISTENCY_LAP_COUNT and lap_num - self._last_consistency_at_lap >= 3:
            trend = self._consistency_trend()
            if trend:
                self._last_consistency_at_lap = lap_num
                out.append(self._msg(trend, {}, CrewChiefPriority.LOW))

        return out

    def _eval_sector_timing(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session):
            return []
        raw = read_sector(ctx.current)
        now = ctx.now_monotonic
        if self._last_sector_raw is None:
            self._last_sector_raw = raw
            self._sector_entered_at = now
            return []

        if raw == self._last_sector_raw:
            return []

        elapsed = now - self._sector_entered_at
        display = normalize_display_sector(self._last_sector_raw)
        best = self._best_sector_duration.get(display)
        msg: CrewChiefMessage | None = None
        if best is None or elapsed < best - SECTOR_FAST_DELTA_S:
            self._best_sector_duration[display] = elapsed
            if best is not None:
                delta = best - elapsed
                msg = self._msg(
                    "sector_personal_best",
                    {"sector": str(display), "delta": f"{delta:.1f}s"},
                    CrewChiefPriority.NORMAL,
                )
        elif best is not None and elapsed > best + SECTOR_SLOW_DELTA_S:
            delta = elapsed - best
            msg = self._msg(
                "sector_off_pace",
                {"sector": str(display), "delta": f"{delta:.1f}s"},
                CrewChiefPriority.LOW,
            )

        self._last_sector_raw = raw
        self._sector_entered_at = now
        return [msg] if msg else []

    def _consistency_trend(self) -> str | None:
        recent = self._lap_times[-CONSISTENCY_LAP_COUNT:]
        first_half = sum(recent[:2]) / 2
        second_half = sum(recent[-2:]) / 2
        spread = max(recent) - min(recent)
        if spread < 0.4:
            return "lap_consistency_stable"
        if second_half < first_half - 0.2:
            return "lap_consistency_improving"
        if second_half > first_half + 0.2:
            return "lap_consistency_worsening"
        return None

    @staticmethod
    def _msg(event_id: str, ctx: dict, priority: CrewChiefPriority) -> CrewChiefMessage:
        return CrewChiefMessage(
            event_id=event_id,
            text=render_template(event_id, ctx),
            priority=priority,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
        )
```

- [ ] **Step 5: Cutover proactive — remove fast_lap from `_on_lap_complete`**

Delete lines in `proactive_monitors.py`:

```python
        if lap_time > 0 and best > 0 and lap_time <= best + 0.05:
            events.append(
                ("fast_lap", f"¡Vuelta rápida personal! {lap_time:.3f}s.", "MEDIUM")
            )
```

Add to `cutover_registry.py` `CC_OWNED_EVENT_IDS`: `lap_personal_best`, `lap_invalid`, `lap_consistency_improving`, `lap_consistency_worsening`, `lap_consistency_stable`, `sector_personal_best`, `sector_off_pace`.

- [ ] **Step 6: Register in suite + run tests**

Run: `cd backend && python -m pytest tests/test_crewchief_lap_times_module.py -v`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/src/intelligence/crewchief_events/modules/lap_times.py backend/tests/test_crewchief_lap_times_module.py backend/src/data/crewchief_templates_es.json backend/src/intelligence/proactive_monitors.py backend/src/intelligence/crewchief_events/cutover_registry.py backend/src/main.py backend/src/intelligence/crewchief_events/modules/__init__.py
git commit -m "feat(crewchief): LapTimes module with fast lap and sector proxy"
```

---

### Task 24: `lap_counter.py` — `LapCounter.cs` (LMU-08, LMU-21)

**Scope:** Anuncio vuelta N (cada vuelta en race), última vuelta por **ingeniero** (cutover spotter), edge once.

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/lap_counter.py`
- Modify: `backend/src/intelligence/spotter.py` (`_eval_last_lap` gate)
- Test: `backend/tests/test_crewchief_lap_counter_module.py`

- [ ] **Step 1: Templates**

```json
  "lap_counter_announce": {
    "default": "Vuelta {lap}."
  },
  "last_lap_race": {
    "default": "¡Última vuelta de la carrera!"
  }
```

- [ ] **Step 2: Failing tests**

```python
def test_announces_lap_number_on_complete():
    module = LapCounterEvent()
    messages = module.evaluate(_ctx({"lap_number": 4}, {"lap_number": 5, "session_type_int": 10}))
    assert any(m.event_id == "lap_counter_announce" and "5" in m.text for m in messages)


def test_last_lap_once_when_one_lap_left():
    module = LapCounterEvent()
    m1 = module.evaluate(_ctx({"session_laps_left": 1.5}, {"session_laps_left": 1.0, "session_type_int": 10}))
    m2 = module.evaluate(_ctx({"session_laps_left": 1.0}, {"session_laps_left": 1.0, "session_type_int": 10}))
    assert any(m.event_id == "last_lap_race" for m in m1)
    assert not any(m.event_id == "last_lap_race" for m in m2)
```

- [ ] **Step 3: Implement**

```python
# backend/src/intelligence/crewchief_events/modules/lap_counter.py
from __future__ import annotations

from src.intelligence.crewchief_events.lap_edge import lap_completed
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class LapCounterEvent(CrewChiefEventModule):
    event_name = "lap_counter"

    def __init__(self) -> None:
        self._last_lap_announced = False

    def clear_state(self) -> None:
        self._last_lap_announced = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        if not session_enable_flag(ctx.session, "enable_lap_counter_messages", True):
            return []
        if not is_racing_green(ctx.current, ctx.session):
            return []

        messages: list[CrewChiefMessage] = []
        laps_left = ctx.current.get("session_laps_left")
        if laps_left is not None and float(laps_left) > 1.0:
            self._last_lap_announced = False

        if laps_left is not None and float(laps_left) <= 1.0 and not self._last_lap_announced:
            self._last_lap_announced = True
            messages.append(
                CrewChiefMessage(
                    event_id="last_lap_race",
                    text=render_template("last_lap_race", {}),
                    priority=CrewChiefPriority.IMPORTANT,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=10000,
                    play_even_when_silenced=True,
                )
            )

        if lap_completed(ctx.previous, ctx.current):
            lap = int(ctx.current.get("lap_number") or 0)
            if lap > 0 and self._should_announce_lap(lap, ctx.session):
                messages.append(
                    CrewChiefMessage(
                        event_id="lap_counter_announce",
                        text=render_template("lap_counter_announce", {"lap": str(lap)}),
                        priority=CrewChiefPriority.LOW,
                        channel=CrewChiefChannel.ENGINEER,
                        ttl_ms=6000,
                    )
                )
        return messages[:2]

    @staticmethod
    def _should_announce_lap(lap: int, session: dict) -> bool:
        level = str(session.get("verbosity_level") or "normal").lower()
        if level == "detailed":
            return True
        return lap % 5 == 0
```

- [ ] **Step 4: Spotter gate for last lap**

In `spotter.py` `_eval_last_lap`, first line:

```python
        if getattr(self, "_enable_lap_counter_messages", True):
            return []
```

Wire in `apply_runtime_config`: `enableLapCounterMessages` (default True).

- [ ] **Step 5: Run tests + commit**

Run: `cd backend && python -m pytest tests/test_crewchief_lap_counter_module.py -v`

```bash
git commit -m "feat(crewchief): LapCounter module; engineer owns last lap"
```

---

### Task 25: `push_now.py` — `PushNow.cs` (LMU-19)

**Scope:** Deterministic push win/hold/improve near race end using best-lap math (no LLM).

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/push_now.py`
- Modify: `backend/src/intelligence/triggers.py` (`PushNowTrigger` cutover)
- Modify: `proactive_monitors.py` (remove push_now commentary)
- Test: `backend/tests/test_crewchief_push_now_module.py`

- [ ] **Step 1: Failing test**

```python
def test_push_to_hold_when_rival_behind_faster():
    module = PushNowEvent()
    competitors = [
        {"standing_position": 4, "lap_time_best": 88.0, "driver_index": 1},
        {"standing_position": 5, "lap_time_best": 90.0, "driver_index": 0, "in_pits": False},
        {"standing_position": 6, "lap_time_best": 89.0, "driver_index": 2},
    ]
    messages = module.evaluate(
        _ctx(
            {"session_laps_left": 4.0, "standing_position": 5, "lap_time_best": 90.0, "gap_behind": 1.5},
            {
                "session_laps_left": 3.0,
                "standing_position": 5,
                "lap_time_best": 90.0,
                "gap_behind": 1.5,
                "competitors": competitors,
                "session_type_int": 10,
                "in_pits": False,
            },
        )
    )
    assert any(m.event_id == "push_to_hold" for m in messages)
```

- [ ] **Step 2: Implement push logic**

```python
# backend/src/intelligence/crewchief_events/modules/push_now.py
from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

PUSH_LAPS_LEFT = 3
PUSH_TIME_LEFT_S = 240.0


class PushNowEvent(CrewChiefEventModule):
    event_name = "push_now"

    def __init__(self) -> None:
        self._played_near_end = False

    def clear_state(self) -> None:
        self._played_near_end = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous or not is_racing_green(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_push_now_messages", True):
            return []
        if ctx.current.get("in_pits"):
            return []
        if self._played_near_end:
            return []

        laps_left = float(ctx.current.get("session_laps_left") or 999)
        time_left = float(ctx.current.get("session_time_left") or 99999)
        near_end = (0 < laps_left <= PUSH_LAPS_LEFT) or (0 < time_left <= PUSH_TIME_LEFT_S)
        if not near_end:
            return []

        event_id = self._pick_push_message(ctx)
        if not event_id:
            return []

        self._played_near_end = True
        pos = int(ctx.current.get("standing_position") or 0)
        return [
            CrewChiefMessage(
                event_id=event_id,
                text=render_template(event_id, {"position": str(pos)}),
                priority=CrewChiefPriority.NORMAL,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=10000,
            )
        ]

    def _pick_push_message(self, ctx: CrewChiefFrameContext) -> str | None:
        tele = ctx.current
        my_best = float(tele.get("lap_time_best") or 0)
        my_pos = int(tele.get("standing_position") or 99)
        laps_left = float(tele.get("session_laps_left") or 3)
        gap_ahead = float(tele.get("gap_ahead") or tele.get("time_gap_car_ahead") or 99)
        gap_behind = float(tele.get("gap_behind") or tele.get("time_gap_car_behind") or 99)

        ahead_best, behind_best = self._neighbor_bests(tele, my_pos)
        if my_best <= 0:
            return "push_to_win"

        if ahead_best > 0 and my_best < ahead_best:
            catch_time = (ahead_best - my_best) * laps_left
            if catch_time > gap_ahead and my_pos <= 4:
                if my_pos == 2:
                    return "push_to_win"
                if my_pos == 3:
                    return "push_to_win"
                if my_pos == 4:
                    return "push_to_win"
                return "push_to_win"

        if behind_best > 0 and behind_best < my_best:
            loss_time = (my_best - behind_best) * laps_left
            if loss_time > gap_behind:
                return "push_to_hold"

        return "push_to_win"

    @staticmethod
    def _neighbor_bests(tele: dict, my_pos: int) -> tuple[float, float]:
        ahead_best = 0.0
        behind_best = 0.0
        for comp in tele.get("competitors") or []:
            pos = int(comp.get("standing_position") or 0)
            best = float(comp.get("lap_time_best") or 0)
            if best <= 0:
                continue
            if pos == my_pos - 1:
                ahead_best = best
            elif pos == my_pos + 1:
                behind_best = best
        return ahead_best, behind_best
```

- [ ] **Step 3: Cutover `PushNowTrigger`**

In `PushNowTrigger.condition`, after pits check:

```python
        from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event
        from src.intelligence.crewchief_events.cc_gates import session_enable_flag
        if session_enable_flag(session, "enable_push_now_messages", True) and is_cc_owned_event("push_to_win"):
            self._push_active = False
            return False
```

Remove proactive push block in `_eval_strategy`.

- [ ] **Step 4: Run + commit**

Run: `cd backend && python -m pytest tests/test_crewchief_push_now_module.py -v`

---

### Task 26: `session_end.py` — `SessionEndMessages.cs` (LMU-28)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/session_end.py`
- Test: `backend/tests/test_crewchief_session_end_module.py`

- [ ] **Step 1: Templates**

```json
  "session_disqualified": {
    "default": "Descalificado. Sesión terminada."
  },
  "session_dnf": {
    "default": "Abandonaste la carrera."
  },
  "session_bad_finish": {
    "default": "P{position}. Has perdido {lost} posiciones respecto a la salida."
  }
```

(`session_victory`, `session_podium`, `session_finish` already exist.)

- [ ] **Step 2: Failing tests**

```python
def test_victory_on_p1_session_over():
    module = SessionEndEvent()
    messages = module.evaluate(
        _ctx(
            {"session_over": False, "standing_position": 1, "start_standing_position": 3},
            {"session_over": True, "standing_position": 1, "start_standing_position": 3, "lap_number": 20},
        )
    )
    assert any(m.event_id == "session_victory" for m in messages)


def test_podium_p3():
    module = SessionEndEvent()
    messages = module.evaluate(
        _ctx(
            {"session_over": False},
            {"session_over": True, "standing_position": 3, "start_standing_position": 5, "lap_number": 15},
        )
    )
    assert any(m.event_id == "session_podium" for m in messages)
```

- [ ] **Step 3: Implement**

```python
# backend/src/intelligence/crewchief_events/modules/session_end.py
from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class SessionEndEvent(CrewChiefEventModule):
    event_name = "session_end"

    def __init__(self) -> None:
        self._announced = False

    def clear_state(self) -> None:
        self._announced = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous or self._announced:
            return []
        if not session_enable_flag(ctx.session, "enable_session_end_messages", True):
            return []

        prev_over = bool(ctx.previous.get("session_over"))
        curr_over = bool(ctx.current.get("session_over"))
        lap = int(ctx.current.get("lap_number") or 0)
        if lap < 2:
            return []

        ending = curr_over and not prev_over
        laps_left = float(ctx.current.get("session_laps_left") or 99)
        if not ending and not (0 < laps_left <= 0.5):
            return []

        self._announced = True
        return [self._build_message(ctx)]

    def _build_message(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage:
        tele = ctx.current
        pos = int(tele.get("standing_position") or 0)
        start = int(tele.get("start_standing_position") or tele.get("start_class_position") or pos)
        gain = start - pos
        lost = pos - start

        if tele.get("disqualified") or tele.get("num_penalties", 0) >= 99:
            event_id = "session_disqualified"
        elif tele.get("dnf") or tele.get("retired"):
            event_id = "session_dnf"
        elif pos == 1:
            event_id = "session_victory"
        elif pos <= 3:
            event_id = "session_podium"
        elif gain >= 3:
            event_id = "session_finish"
        elif lost >= 5:
            event_id = "session_bad_finish"
        else:
            event_id = "session_finish"

        text = render_template(
            event_id,
            {"position": str(pos), "gain": str(gain), "lost": str(lost), "good_gain": gain >= 3},
        )
        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=15000,
            play_even_when_silenced=True,
        )
```

- [ ] **Step 4: Cutover `SessionEndTrigger` + proactive `session_end`**

Same pattern as PushNow. Remove proactive block:

```python
            if race and not self._session_end_announced:
                ...
                events.append(("session_end", ...))
```

- [ ] **Step 5: Run + commit**

Run: `cd backend && python -m pytest tests/test_crewchief_session_end_module.py -v`

---

### Task 27: Expand `fuel.py` — `Fuel.cs` (LMU-06, LMU-14, LMU-45)

**Files:**
- Create: `backend/src/persistence/fuel_usage_store.py`
- Modify: `backend/src/intelligence/crewchief_events/modules/fuel.py`
- Modify: `backend/src/intelligence/triggers.py` (`FuelCriticalTrigger` cutover)
- Modify: `backend/src/intelligence/spotter.py` (`_eval_fuel_critical` gate when `enable_fuel_messages`)
- Test: `backend/tests/test_fuel_usage_store.py`, extend `test_crewchief_fuel_module.py`

- [ ] **Step 1: Fuel usage store test + impl**

```python
# backend/tests/test_fuel_usage_store.py
from src.persistence.fuel_usage_store import FuelUsageStore


def test_save_and_load_car_track_combo(tmp_path, monkeypatch):
    monkeypatch.setattr("src.persistence.fuel_usage_store.DATA_DIR", str(tmp_path))
    store = FuelUsageStore(auto_load=False)
    store.record_sample("LMU", "Oreca 07", "Spa", consumption_l=2.45)
    store.save()
    store2 = FuelUsageStore(auto_load=True)
    samples = store2.get_samples("LMU", "Oreca 07", "Spa")
    assert len(samples) == 1
    assert samples[0]["consumption_l"] == 2.45
```

```python
# backend/src/persistence/fuel_usage_store.py
"""Persistencia CC-style fuel usage por juego/coche/pista (max 5 muestras)."""
from __future__ import annotations

import json
import os
import random
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
FUEL_USAGE_FILE = os.path.join(DATA_DIR, "fuel_usage.json")
MAX_SAMPLES = 5
SAVE_PROBABILITY = 0.1  # CC random 10 samples


class FuelUsageStore:
    def __init__(self, auto_load: bool = True) -> None:
        self._data: dict[str, list[dict[str, Any]]] = {}
        if auto_load:
            self.load()

    @staticmethod
    def _key(game: str, car: str, track: str) -> str:
        return f"{game}|{car}|{track}"

    def record_sample(self, game: str, car: str, track: str, consumption_l: float) -> None:
        if consumption_l <= 0 or random.random() > SAVE_PROBABILITY:
            return
        key = self._key(game, car, track)
        rows = self._data.setdefault(key, [])
        rows.append({"consumption_l": round(consumption_l, 3)})
        if len(rows) > MAX_SAMPLES:
            del rows[0]

    def get_samples(self, game: str, car: str, track: str) -> list[dict[str, Any]]:
        return list(self._data.get(self._key(game, car, track), []))

    def save(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(FUEL_USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def load(self) -> None:
        if not os.path.exists(FUEL_USAGE_FILE):
            return
        with open(FUEL_USAGE_FILE, encoding="utf-8") as f:
            self._data = json.load(f)
```

- [ ] **Step 2: Templates**

```json
  "fuel_laps_remaining": {
    "default": "Combustible para unas {laps} vueltas.",
    "variants": {
      "level=3": "Quedan unas 3 vueltas de combustible.",
      "level=2": "Quedan unas 2 vueltas de combustible.",
      "level=1": "Queda menos de 1 vuelta de combustible."
    }
  },
  "fuel_box_this_lap": {
    "default": "Entra a boxes esta vuelta — te quedas sin combustible."
  }
```

- [ ] **Step 3: Expand FuelEvent**

Key behaviors:
- Check every `fuel_status_check_interval_s` (5s) using `ctx.now_monotonic`
- Tiers: `<3`, `<2`, `<1` laps → `fuel_laps_remaining` with level variant (edge once per tier)
- Keep existing `fuel_about_to_run_out` when `fuel_laps_remaining < 0.5` and sector raw == 0 (LMU sector 3)
- Sector 3 box message: `fuel_box_this_lap` when `<1.5` laps and `read_sector(ctx.current) == 0`
- On lap complete: record consumption to `FuelUsageStore` if `fuel_used_last_lap` in telemetry/strategy
- Use `fuel_safety.fuel_critical_from_tick` finish-safe to **suppress** false positives

Add to `FuelEvent.__init__`:

```python
        self._last_check_at = 0.0
        self._warned_tiers: set[int] = set()
        self._fuel_store = FuelUsageStore()
```

In `evaluate`, gate with `session_enable_flag(session, "enable_fuel_messages", True)`.

- [ ] **Step 4: Tests**

```python
def test_fuel_three_laps_tier():
    module = FuelEvent()
    module._last_check_at = 0.0
    messages = module.evaluate(
        CrewChiefFrameContext(
            previous={"fuel_laps_remaining": 3.5},
            current={"fuel_laps_remaining": 2.8, "session_type_int": 10, "in_pits": False},
            strategy={},
            session={"phase": "race", "enable_fuel_messages": True},
            now_monotonic=10.0,
        )
    )
    assert any(m.event_id == "fuel_laps_remaining" for m in messages)


def test_fuel_box_this_lap_sector_three():
    module = FuelEvent()
    messages = module.evaluate(
        CrewChiefFrameContext(
            previous={"fuel_laps_remaining": 1.6, "current_sector": 1},
            current={"fuel_laps_remaining": 1.2, "current_sector": 0, "session_type_int": 10},
            strategy={},
            session={"phase": "race", "enable_fuel_messages": True},
            now_monotonic=20.0,
        )
    )
    assert any(m.event_id == "fuel_box_this_lap" for m in messages)
```

- [ ] **Step 5: Cutover FuelCriticalTrigger + spotter fuel**

`FuelCriticalTrigger.condition` → return False when `enable_fuel_messages` and CC owns `fuel_laps_remaining`.

`spotter._eval_fuel_critical` → return [] when `_enable_fuel_messages` True (default).

- [ ] **Step 6: Run + commit**

Run: `cd backend && python -m pytest tests/test_crewchief_fuel_module.py tests/test_fuel_usage_store.py -v`

---

### Task 28: `pit_stops.py` — `PitStops.cs` (LMU-16, LMU-17)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/pit_stops.py`
- Modify: `triggers.py` (PitWindowOpened/Closing cutover)
- Modify: `proactive_monitors.py` (remove `_eval_strategy` pit block + `_eval_pit_timing`)
- Test: `backend/tests/test_crewchief_pit_stops_module.py`

- [ ] **Step 1: Templates**

```json
  "pit_window_open": {
    "default": "Ventana de boxes abierta — vuelta {open_lap} a {close_lap}."
  },
  "pit_window_closing": {
    "default": "Ventana de boxes cierra en {laps} vueltas."
  },
  "pit_entry": {
    "default": "Entrada a boxes."
  },
  "pit_exit": {
    "default": "Salida de boxes.",
    "variants": {
      "position=5": "Salida de boxes — P{position}."
    }
  },
  "pit_stop_prediction": {
    "default": "{message}"
  }
```

- [ ] **Step 2: Failing tests**

```python
def test_pit_window_open_edge():
    module = PitStopsEvent()
    messages = module.evaluate(
        _ctx(
            {"lap_number": 10},
            {"lap_number": 10},
            strategy={"pit_window": {"pit_window_open": False}},
        )
    )
    messages = module.evaluate(
        _ctx(
            {"lap_number": 10},
            {"lap_number": 11, "in_pits": False},
            strategy={"pit_window": {"pit_window_open": True, "optimal_pit_lap": 12, "window_close_lap": 18}},
        )
    )
    assert any(m.event_id == "pit_window_open" for m in messages)


def test_pit_entry_exit_edges():
    module = PitStopsEvent()
    entry = module.evaluate(_ctx({"in_pits": False}, {"in_pits": True, "lap_number": 8}))
    exit_m = module.evaluate(_ctx({"in_pits": True}, {"in_pits": False, "standing_position": 5, "lap_number": 8}))
    assert any(m.event_id == "pit_entry" for m in entry)
    assert any(m.event_id == "pit_exit" for m in exit_m)
```

- [ ] **Step 3: Implement**

```python
# backend/src/intelligence/crewchief_events/modules/pit_stops.py
from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.pit_prediction import (
    count_pit_context,
    estimate_position_after_pit_stop,
    format_pit_exit_prediction,
)

from ..base import CrewChiefEventModule
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class PitStopsEvent(CrewChiefEventModule):
    event_name = "pit_stops"

    def __init__(self) -> None:
        self._window_open_played = False
        self._window_closing_played = False
        self._was_in_pits = False
        self._last_prediction_at = 0.0

    def clear_state(self) -> None:
        self.__init__()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not ctx.previous:
            return []
        messages: list[CrewChiefMessage] = []
        messages.extend(self._eval_window(ctx))
        messages.extend(self._eval_player_pits(ctx))
        messages.extend(self._eval_prediction(ctx))
        return messages[:2]

    def _eval_window(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        pw = ctx.strategy.get("pit_window") or {}
        open_now = bool(pw.get("pit_window_open")) and not ctx.current.get("in_pits")
        if open_now and not self._window_open_played:
            self._window_open_played = True
            open_lap = int(pw.get("optimal_pit_lap") or ctx.current.get("lap_number") or 0)
            close_lap = int(pw.get("window_close_lap") or open_lap + 5)
            return [
                CrewChiefMessage(
                    event_id="pit_window_open",
                    text=render_template("pit_window_open", {"open_lap": str(open_lap), "close_lap": str(close_lap)}),
                    priority=CrewChiefPriority.IMPORTANT,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=12000,
                )
            ]
        if not open_now:
            self._window_open_played = False
            self._window_closing_played = False

        if open_now and not self._window_closing_played:
            laps_in_window = int(pw.get("optimal_pit_lap") or 0) - int(ctx.current.get("lap_number") or 0)
            if 0 <= laps_in_window <= 2:
                self._window_closing_played = True
                return [
                    CrewChiefMessage(
                        event_id="pit_window_closing",
                        text=render_template("pit_window_closing", {"laps": str(max(laps_in_window, 1))}),
                        priority=CrewChiefPriority.IMPORTANT,
                        channel=CrewChiefChannel.ENGINEER,
                        ttl_ms=10000,
                    )
                ]
        return []

    def _eval_player_pits(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        in_pits = bool(ctx.current.get("in_pits"))
        was = bool(ctx.previous.get("in_pits"))
        out: list[CrewChiefMessage] = []
        if in_pits and not was:
            out.append(
                CrewChiefMessage(
                    event_id="pit_entry",
                    text=render_template("pit_entry", {}),
                    priority=CrewChiefPriority.NORMAL,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=8000,
                )
            )
        if was and not in_pits:
            pos = int(ctx.current.get("standing_position") or 0)
            out.append(
                CrewChiefMessage(
                    event_id="pit_exit",
                    text=render_template("pit_exit", {"position": str(pos)}),
                    priority=CrewChiefPriority.NORMAL,
                    channel=CrewChiefChannel.ENGINEER,
                    ttl_ms=8000,
                )
            )
        self._was_in_pits = in_pits
        return out

    def _eval_prediction(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session):
            return []
        now = ctx.now_monotonic
        if now - self._last_prediction_at < 90.0:
            return []
        competitors = ctx.current.get("competitors") or []
        pos = int(ctx.current.get("standing_position") or 0)
        ahead, behind = count_pit_context(competitors)
        est = estimate_position_after_pit_stop(pos, ahead, behind)
        pit_open = bool((ctx.strategy.get("pit_window") or {}).get("pit_window_open"))
        text = format_pit_exit_prediction(pos, est, pit_open)
        if not text:
            return []
        self._last_prediction_at = now
        return [
            CrewChiefMessage(
                event_id="pit_stop_prediction",
                text=render_template("pit_stop_prediction", {"message": text}),
                priority=CrewChiefPriority.LOW,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=15000,
            )
        ]
```

**Note:** `_eval_prediction` should fire at most once per 90s — add `self._last_prediction_at` cooldown (port from proactive).

- [ ] **Step 4: Cutover pit window triggers + proactive pit blocks**

- [ ] **Step 5: Run full slice**

```powershell
cd backend
python -m pytest tests/test_crewchief_lap_times_module.py tests/test_crewchief_lap_counter_module.py tests/test_crewchief_push_now_module.py tests/test_crewchief_session_end_module.py tests/test_crewchief_fuel_module.py tests/test_crewchief_pit_stops_module.py tests/test_fuel_usage_store.py -v
python scripts/verify_alpha_parity.py
```

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(crewchief): core race modules tasks 23-28"
```

---

## Self-review checklist

| complete-port Task | Covered |
|--------------------|---------|
| 23 LapTimes sector/best/consistency/invalid | Task 23 (sector via timing proxy) |
| 24 LapCounter lap N + last lap | Task 24 + spotter cutover |
| 25 PushNow deterministic | Task 25 |
| 26 SessionEnd templates | Task 26 |
| 27 Fuel critical + persistence | Task 27 |
| 28 PitStops window/entry/exit/prediction | Task 28 |
| Cutover legacy triggers/commentary | Each task |
| Register in 20 Hz suite | File map |

**Explicit defer:**
- Task 47 session fuel multiplier (not in 23–28 scope)
- Native LMU sector split fields (when added to `TelemetryFrame`, extend Task 23)
- SessionEnd `playRant` (LMU rants — P2)

---

## Preguntas — RESUELTAS (piloto 2026-06-07)

| # | Decisión |
|---|----------|
| 1 | **Lap counter:** cada vuelta en modo **detallado**, cada **5** en modo **normal** |
| 2 | **Solo carrera** (qualifying/practice OFF) |
| 3 | **Fuel spotter OFF** cuando ingeniero fuel ON |
| 4 | **Pit prediction normal:** solo si combustible **< 3 vueltas**. **Detallado:** cada **180 s** desde vuelta **5**, o bajo demanda (PTT) |

Implementar en Task 24 (`lap_counter.py`) y Task 28 (`pit_stops.py`) vía `session["verbosity_level"]` (`normal` | `detailed`).

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-07-crewchief-tasks23-28-core-race.md`.**

**Recommended order:** Shared lap_edge → 23 → 24 → 25 → 26 → 27 → 28 → full pytest slice.

**Two execution options:**

1. **Subagent-Driven (recommended)** — one subagent per task, review between tasks  
2. **Inline Execution** — implement 23→28 in this session with checkpoints

**Which approach?**

Also updated: [`2026-06-07-crewchief-task22-timings.md`](2026-06-07-crewchief-task22-timings.md) with your decisions (gaps ON, spotter OFF, pressure cooldown 60s, Task 10 spotter gate).
