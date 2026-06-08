# Task 22 — Timings / Gap Commentary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar el stub de `TimingsEvent` por un módulo determinista estilo `Timings.cs` que anuncie gaps por sector (LMU-22) y presión en batalla (LMU-27), con cola retrasada y re-validación (Task 16).

**Architecture:** `TimingsEvent` mantiene historial de gaps adelante/detrás, detecta tendencia (`INCREASING` / `DECREASING` / `HOLDING` / `CLOSE`) en `gap_trend.py`, y solo habla cuando cambia sector **y** cumple frecuencia sector-based + randomness CC. Mensajes usan `render_template()` + `validation_key` para `DelayedMessageQueue`. `GapClosedTrigger` (LLM) se corta vía cutover cuando timings emite battle.

**Tech Stack:** Python 3.11+, pytest, `crewchief_events` suite @ 20 Hz, templates JSON ES, `corner_names.py` opcional.

**Referencias:** LMU-10, LMU-22, LMU-27 en `.omo/evidence/cc-behavior-parity-matrix.yaml` · Task 16 `delayed_queue.py` · `complete-port.md` Task 22

**Scope locked (alpha):**
- Sector-based + trend + battle pressure + delayed re-validate = **MATCH funcional**
- Corner name en mensaje = **v1 opcional** (solo si `track_name` resuelve curva)
- `gapPoint` CC además de sector = **defer post-alpha** (solo sector en v1)
- Spotter `_eval_gaps` (UI 0.5s) **no se toca** — canal distinto

**Defaults locked (piloto 2026-06-07):**
| Setting | Valor v1 | Fuente |
|---------|----------|--------|
| `enable_gap_messages` | **`true`** | Piloto: paridad CC (LMU-10/22) |
| `frequency_of_gap_ahead_reports` | `5` | CC UserSettings 1–10 |
| `frequency_of_gap_behind_reports` | `5` | CC UserSettings 1–10 |
| `gap_message_randomness` | `5` | CC 0–10 |
| `min_gap_to_report_s` | `0.05` | CC minGapToReport |
| `max_gap_to_report_s` | `30.0` | CC reporta gaps largos en carrera |
| `trend_min_delta_s` | `0.3` | CC-ish: cambio audible |
| `close_gap_s` | `1.0` | LMU-27 test matrix |
| `pressure_behind_s` | `10.0` | gap_behind < 1s sostenido |
| `holding_up_s` | `30.0` | mismo rival delante, gap < 2s |
| `pressure_cooldown_s` | `60.0` | Piloto: presión repetible con cooldown |
| `near_race_end_laps` | `2` | CC nearRaceEnd |
| Spotter `_eval_gaps` | **OFF si `enable_gap_messages=true`** | Piloto: no duplicar UI + voz |

---

## File map

| File | Responsibility |
|------|----------------|
| `backend/src/intelligence/crewchief_events/gap_trend.py` | **CREATE** — enum + clasificación de tendencia |
| `backend/src/intelligence/crewchief_events/cc_gates.py` | **MODIFY** — gates `enable_gap_messages`, frecuencias |
| `backend/src/intelligence/crewchief_events/modules/timings.py` | **MODIFY** — lógica completa TimingsEvent |
| `backend/src/intelligence/crewchief_events/delayed_queue.py` | **MODIFY** — validators `gap:ahead:*`, `gap:behind:*` |
| `backend/src/intelligence/crewchief_events/cutover_registry.py` | **MODIFY** — nuevos event_ids |
| `backend/src/data/crewchief_templates_es.json` | **MODIFY** — plantillas gap completas |
| `backend/src/intelligence/triggers.py` | **MODIFY** — `GapClosedTrigger` retorna False si CC-owned |
| `backend/src/intelligence/proactive_monitors.py` | **MODIFY** — eliminar `_format_gap_update` muerto |
| `backend/tests/fixtures/timings/sector_gap_sequence.json` | **CREATE** |
| `backend/tests/fixtures/timings/helpers.py` | **CREATE** — replay ticks |
| `backend/tests/test_crewchief_gap_trend.py` | **CREATE** |
| `backend/tests/test_crewchief_timings_module.py` | **MODIFY** — suite L1 |
| `backend/tests/test_crewchief_delayed_queue.py` | **MODIFY** — validators nuevos |
| `backend/tests/test_crewchief_timings_cutover.py` | **CREATE** — LMU-27 vs GapClosedTrigger |

---

### Task 1: Gap trend classifier

**Files:**
- Create: `backend/src/intelligence/crewchief_events/gap_trend.py`
- Test: `backend/tests/test_crewchief_gap_trend.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_crewchief_gap_trend.py
from src.intelligence.crewchief_events.gap_trend import GapTrend, classify_gap_trend


def test_increasing_when_samples_rise():
    samples = [2.0, 2.3, 2.6]
    assert classify_gap_trend(samples) == GapTrend.INCREASING


def test_decreasing_when_samples_fall():
    samples = [2.0, 1.7, 1.4]
    assert classify_gap_trend(samples) == GapTrend.DECREASING


def test_holding_when_samples_flat():
    samples = [2.0, 2.05, 1.98]
    assert classify_gap_trend(samples) == GapTrend.HOLDING


def test_close_when_last_sample_under_threshold():
    samples = [1.5, 1.2, 0.9]
    assert classify_gap_trend(samples, close_threshold_s=1.0) == GapTrend.CLOSE


def test_unknown_with_fewer_than_three_samples():
    assert classify_gap_trend([2.0, 2.5]) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_crewchief_gap_trend.py -v`

Expected: FAIL — `ModuleNotFoundError: gap_trend`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/src/intelligence/crewchief_events/gap_trend.py
from __future__ import annotations

from enum import Enum


class GapTrend(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    HOLDING = "holding"
    CLOSE = "close"


TREND_MIN_DELTA_S = 0.3
HOLDING_MAX_SPREAD_S = 0.15


def classify_gap_trend(
    samples: list[float],
    *,
    close_threshold_s: float = 1.0,
    trend_min_delta_s: float = TREND_MIN_DELTA_S,
    holding_max_spread_s: float = HOLDING_MAX_SPREAD_S,
) -> GapTrend | None:
    if len(samples) < 3:
        return None
    last_three = samples[-3:]
    if last_three[-1] < close_threshold_s:
        return GapTrend.CLOSE
    delta = last_three[-1] - last_three[0]
    spread = max(last_three) - min(last_three)
    if spread <= holding_max_spread_s:
        return GapTrend.HOLDING
    if delta >= trend_min_delta_s:
        return GapTrend.INCREASING
    if delta <= -trend_min_delta_s:
        return GapTrend.DECREASING
    return GapTrend.HOLDING
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_crewchief_gap_trend.py -v`

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/gap_trend.py backend/tests/test_crewchief_gap_trend.py
git commit -m "feat(timings): add gap trend classifier for Task 22"
```

---

### Task 2: CC gap gates in session config

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/cc_gates.py`
- Test: `backend/tests/test_crewchief_gap_gates.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_crewchief_gap_gates.py
from src.intelligence.crewchief_events.cc_gates import (
    gap_frequency_sectors,
    should_emit_gap_message,
    is_near_race_end,
)


def test_gap_messages_on_by_default():
    tele = {"session_type_int": 10, "in_pits": False}
    assert should_emit_gap_message(tele, {}) is True


def test_gap_messages_off_when_disabled():
    session = {"enable_gap_messages": False}
    tele = {"session_type_int": 10, "in_pits": False}
    assert should_emit_gap_message(tele, session) is False


def test_gap_suppressed_in_pits():
    session = {"enable_gap_messages": True}
    tele = {"session_type_int": 10, "in_pits": True}
    assert should_emit_gap_message(tele, session) is False


def test_frequency_five_yields_six_to_eleven_sectors():
    session = {"frequency_of_gap_ahead_reports": 5, "gap_message_randomness": 5}
    low, high = gap_frequency_sectors(session, "ahead")
    assert low == 6  # 1 + (10-5) + 0
    assert high == 11  # 1 + (10-5) + 5


def test_near_race_end_last_two_laps():
    assert is_near_race_end({"session_laps_left": 2.0}) is True
    assert is_near_race_end({"session_laps_left": 5.0}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_crewchief_gap_gates.py -v`

Expected: FAIL — imports missing

- [ ] **Step 3: Write minimal implementation**

Append to `cc_gates.py`:

```python
DEFAULT_ENABLE_GAP_MESSAGES = True
DEFAULT_GAP_AHEAD_FREQUENCY = 5
DEFAULT_GAP_BEHIND_FREQUENCY = 5
DEFAULT_GAP_MESSAGE_RANDOMNESS = 5
NEAR_RACE_END_LAPS = 2


def should_emit_gap_message(telemetry: dict, session: dict) -> bool:
    if not session_enable_flag(session, "enable_gap_messages", DEFAULT_ENABLE_GAP_MESSAGES):
        return False
    if bool(telemetry.get("in_pits")):
        return False
    if not is_race_session_ctx(telemetry, session):
        return False
    if is_near_race_end(telemetry):
        return False
    return True


def is_near_race_end(telemetry: dict) -> bool:
    laps_left = telemetry.get("session_laps_left")
    if laps_left is None:
        return False
    return 0 < float(laps_left) <= NEAR_RACE_END_LAPS


def gap_frequency_sectors(session: dict, which: str) -> tuple[int, int]:
    key = (
        "frequency_of_gap_ahead_reports"
        if which == "ahead"
        else "frequency_of_gap_behind_reports"
    )
    default = DEFAULT_GAP_AHEAD_FREQUENCY if which == "ahead" else DEFAULT_GAP_BEHIND_FREQUENCY
    freq = int(session.get(key, default))
    freq = max(1, min(10, freq))
    randomness = int(session.get("gap_message_randomness", DEFAULT_GAP_MESSAGE_RANDOMNESS))
    randomness = max(0, min(10, randomness))
    base = 1 + (10 - freq)
    return base, base + randomness
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_crewchief_gap_gates.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/cc_gates.py backend/tests/test_crewchief_gap_gates.py
git commit -m "feat(timings): add CC gap session gates"
```

---

### Task 3: Gap message templates (ES)

**Files:**
- Modify: `backend/src/data/crewchief_templates_es.json`
- Test: `backend/tests/test_crewchief_templates.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_crewchief_templates.py`:

```python
def test_gap_templates_cover_all_trends():
    from src.intelligence.crewchief_events.templates import render_template

    assert "2.1" in render_template("gap_ahead_increasing", {"gap": "2.1"})
    assert "1.4" in render_template("gap_ahead_decreasing", {"gap": "1.4"})
    assert render_template("gap_ahead_holding", {"gap": "2.0"})
    assert render_template("gap_behind_increasing", {"gap": "0.8"})
    assert render_template("gap_behind_decreasing", {"gap": "1.2"})
    assert render_template("gap_being_pressured", {})
    assert render_template("gap_holding_us_up", {})
    assert "Blanchimont" in render_template(
        "gap_ahead_decreasing",
        {"gap": "1.2", "corner": "Blanchimont"},
        variant_key="with_corner=true",
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_crewchief_templates.py::test_gap_templates_cover_all_trends -v`

Expected: FAIL — unknown template keys

- [ ] **Step 3: Add templates to JSON**

Replace/extend gap section in `crewchief_templates_es.json`:

```json
  "gap_ahead_increasing": {
    "default": "Gap con el de delante: {gap} segundos. Se abre.",
    "variants": {
      "with_corner=true": "En {corner}, gap adelante {gap}. Se abre."
    }
  },
  "gap_ahead_decreasing": {
    "default": "El coche de delante está más cerca. Gap {gap}.",
    "variants": {
      "with_corner=true": "En {corner}, gap adelante {gap}. Te acercas."
    }
  },
  "gap_ahead_holding": {
    "default": "Gap estable adelante: {gap} segundos."
  },
  "gap_behind_increasing": {
    "default": "Rival más cerca por detrás. Gap {gap}."
  },
  "gap_behind_decreasing": {
    "default": "Te alejas del de detrás. Gap {gap}."
  },
  "gap_behind_holding": {
    "default": "Gap estable detrás: {gap} segundos."
  },
  "gap_being_pressured": {
    "default": "Te están presionando por detrás. Defiende la posición."
  },
  "gap_holding_us_up": {
    "default": "El de delante te está frenando. Busca el adelantamiento."
  }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m pytest tests/test_crewchief_templates.py::test_gap_templates_cover_all_trends -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/data/crewchief_templates_es.json backend/tests/test_crewchief_templates.py
git commit -m "feat(timings): add gap trend and battle templates ES"
```

---

### Task 4: TimingsEvent — sector gate + ahead trend

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/modules/timings.py`
- Test: `backend/tests/test_crewchief_timings_module.py`

- [ ] **Step 1: Write the failing tests**

Replace/extend `test_crewchief_timings_module.py`:

```python
from src.intelligence.crewchief_events.modules.timings import TimingsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(prev: dict, curr: dict, session: dict | None = None) -> CrewChiefFrameContext:
    return CrewChiefFrameContext(
        previous=prev,
        current=curr,
        strategy={},
        session=session or {"phase": "race", "session_type_int": 10, "enable_gap_messages": True},
        now_monotonic=30.0,
    )


def test_gap_disabled_by_default():
    module = TimingsEvent()
    messages = module.evaluate(
        _ctx(
            {"time_gap_car_ahead": 2.0, "sector": 1},
            {"time_gap_car_ahead": 1.2, "sector": 2},
            session={"phase": "race", "session_type_int": 10},
        )
    )
    assert messages == []


def test_gap_in_front_decreasing_uses_sector_gate():
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0  # force ready
    messages = module.evaluate(
        _ctx(
            {"time_gap_car_ahead": 2.0, "sector": 1, "session_type_int": 10},
            {"time_gap_car_ahead": 1.2, "sector": 2, "session_type_int": 10},
        )
    )
    assert messages[0].event_id == "gap_ahead_decreasing"
    assert "1.2" in messages[0].text
    assert messages[0].validation_key == "gap:ahead:decreasing"


def test_gap_in_front_increasing_on_sector_change():
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    for gap in (2.0, 2.3, 2.6):
        module.evaluate(
            _ctx(
                {"time_gap_car_ahead": gap - 0.1, "sector": 1},
                {"time_gap_car_ahead": gap, "sector": 1},
            )
        )
    messages = module.evaluate(
        _ctx(
            {"time_gap_car_ahead": 2.6, "sector": 2},
            {"time_gap_car_ahead": 2.9, "sector": 3},
        )
    )
    assert any(m.event_id == "gap_ahead_increasing" for m in messages)


def test_no_gap_message_same_sector():
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    ctx = _ctx(
        {"time_gap_car_ahead": 2.0, "sector": 2},
        {"time_gap_car_ahead": 1.5, "sector": 2},
    )
    assert module.evaluate(ctx) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_crewchief_timings_module.py -v`

Expected: FAIL — missing attributes / wrong event_id

- [ ] **Step 3: Implement TimingsEvent core**

```python
# backend/src/intelligence/crewchief_events/modules/timings.py
from __future__ import annotations

import random

from src.intelligence.corner_names import format_lap_distance
from src.intelligence.crewchief_events.cc_gates import (
    gap_frequency_sectors,
    should_emit_gap_message,
)
from src.intelligence.crewchief_events.gap_trend import GapTrend, classify_gap_trend
from src.intelligence.crewchief_events.templates import render_template

from ..base import CrewChiefEventModule
from ..session_gates import is_racing_green
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

MIN_GAP_S = 0.05
MAX_GAP_S = 30.0
PRESSURE_BEHIND_S = 10.0
HOLDING_UP_S = 30.0
CLOSE_GAP_S = 1.0


class TimingsEvent(CrewChiefEventModule):
    event_name = "timings"

    def __init__(self) -> None:
        self._last_sector: int | None = None
        self._gap_samples_ahead: list[float] = []
        self._gap_samples_behind: list[float] = []
        self._sectors_since_last_ahead = 0
        self._sectors_since_last_behind = 0
        self._sectors_until_next_ahead = 0
        self._sectors_until_next_behind = 0
        self._pressure_behind_since: float | None = None
        self._last_pressure_at: float = 0.0
        self._holding_up_since: float | None = None
        self._last_ahead_opponent_key: str | None = None
        self._rng = random.Random(42)

    def clear_state(self) -> None:
        self.__init__()

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if not is_racing_green(ctx.current, ctx.session) or not ctx.previous:
            return []
        if not should_emit_gap_message(ctx.current, ctx.session):
            return []

        sector = self._sector(ctx.current)
        sector_changed = self._last_sector is not None and sector != self._last_sector
        self._last_sector = sector

        ahead, behind = self._gaps(ctx.current)
        self._gap_samples_ahead.append(ahead)
        self._gap_samples_behind.append(behind)
        if len(self._gap_samples_ahead) > 20:
            self._gap_samples_ahead.pop(0)
        if len(self._gap_samples_behind) > 20:
            self._gap_samples_behind.pop(0)

        messages: list[CrewChiefMessage] = []

        if pressure := self._eval_pressure_behind(ctx, behind):
            messages.append(pressure)
        if holding := self._eval_holding_up(ctx, ahead):
            messages.append(holding)

        if sector_changed:
            self._sectors_since_last_ahead += 1
            self._sectors_since_last_behind += 1
            if self._sectors_since_last_ahead >= self._sectors_until_next_ahead:
                if msg := self._maybe_gap_ahead(ctx, ahead):
                    messages.append(msg)
                    self._sectors_since_last_ahead = 0
                    self._sectors_until_next_ahead = self._next_wait(ctx.session, "ahead")
            if self._sectors_since_last_behind >= self._sectors_until_next_behind:
                if msg := self._maybe_gap_behind(ctx, behind):
                    messages.append(msg)
                    self._sectors_since_last_behind = 0
                    self._sectors_until_next_behind = self._next_wait(ctx.session, "behind")

        return messages[:2]

    def _next_wait(self, session: dict, which: str) -> int:
        low, high = gap_frequency_sectors(session, which)
        return self._rng.randint(low, high)

    def _maybe_gap_ahead(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        if not (MIN_GAP_S < gap < MAX_GAP_S):
            return None
        trend = classify_gap_trend(self._gap_samples_ahead, close_threshold_s=CLOSE_GAP_S)
        if trend is None:
            return None
        event_id = {
            GapTrend.INCREASING: "gap_ahead_increasing",
            GapTrend.DECREASING: "gap_ahead_decreasing",
            GapTrend.HOLDING: "gap_ahead_holding",
            GapTrend.CLOSE: "gap_ahead_decreasing",
        }[trend]
        return self._build_gap_message(ctx, event_id, gap, validation=f"gap:ahead:{trend.value}")

    def _maybe_gap_behind(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        if not (MIN_GAP_S < gap < MAX_GAP_S):
            return None
        trend = classify_gap_trend(self._gap_samples_behind, close_threshold_s=CLOSE_GAP_S)
        if trend is None:
            return None
        event_id = {
            GapTrend.INCREASING: "gap_behind_increasing",
            GapTrend.DECREASING: "gap_behind_decreasing",
            GapTrend.HOLDING: "gap_behind_holding",
            GapTrend.CLOSE: "gap_behind_increasing",
        }[trend]
        return self._build_gap_message(ctx, event_id, gap, validation=f"gap:behind:{trend.value}")

    def _build_gap_message(
        self,
        ctx: CrewChiefFrameContext,
        event_id: str,
        gap: float,
        *,
        validation: str,
    ) -> CrewChiefMessage:
        corner = self._corner_phrase(ctx.current)
        variant_key = "with_corner=true" if corner else None
        text = render_template(
            event_id,
            {"gap": f"{gap:.1f}", "corner": corner or ""},
            variant_key=variant_key,
        )
        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key=validation,
        )

    def _eval_pressure_behind(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        now = ctx.now_monotonic
        if gap >= CLOSE_GAP_S:
            self._pressure_behind_since = None
            return None
        if self._pressure_behind_since is None:
            self._pressure_behind_since = now
            return None
        if now - self._pressure_behind_since < PRESSURE_BEHIND_S:
            return None
        if now - self._last_pressure_at < 60.0:
            return None
        self._pressure_behind_since = None
        self._last_pressure_at = now
        return CrewChiefMessage(
            event_id="gap_being_pressured",
            text=render_template("gap_being_pressured", {}),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key="gap:behind:pressure",
        )

    def _eval_holding_up(self, ctx: CrewChiefFrameContext, gap: float) -> CrewChiefMessage | None:
        now = ctx.now_monotonic
        key = self._ahead_opponent_key(ctx.current)
        if key != self._last_ahead_opponent_key:
            self._holding_up_since = None
            self._last_ahead_opponent_key = key
        if gap >= 2.0 or key is None:
            self._holding_up_since = None
            return None
        if self._holding_up_since is None:
            self._holding_up_since = now
            return None
        if now - self._holding_up_since < HOLDING_UP_S:
            return None
        self._holding_up_since = None
        return CrewChiefMessage(
            event_id="gap_holding_us_up",
            text=render_template("gap_holding_us_up", {}),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=8000,
            validation_key="gap:ahead:holding_up",
        )

    @staticmethod
    def _sector(telemetry: dict) -> int:
        raw = telemetry.get("sector")
        if raw is None:
            raw = telemetry.get("mSector")
        return int(raw or 1)

    @staticmethod
    def _gaps(telemetry: dict) -> tuple[float, float]:
        ahead = telemetry.get("time_gap_car_ahead") or telemetry.get("gap_ahead") or 999.0
        behind = telemetry.get("time_gap_car_behind") or telemetry.get("gap_behind") or 999.0
        return float(ahead), float(behind)

    @staticmethod
    def _corner_phrase(telemetry: dict) -> str | None:
        track = str(telemetry.get("track_name") or "")
        dist = telemetry.get("lap_distance") or telemetry.get("distance_on_lap")
        if not track or dist is None:
            return None
        name = format_lap_distance(track, float(dist))
        if name.startswith("km "):
            return None
        return name

    @staticmethod
    def _ahead_opponent_key(telemetry: dict) -> str | None:
        my_pos = int(telemetry.get("standing_position") or 99)
        for comp in telemetry.get("competitors") or []:
            if int(comp.get("standing_position") or 99) == my_pos - 1:
                return str(comp.get("driver_index"))
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_crewchief_timings_module.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/modules/timings.py backend/tests/test_crewchief_timings_module.py
git commit -m "feat(timings): sector-based gap ahead/behind with trends"
```

---

### Task 5: Delayed queue validators for gap trends

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/delayed_queue.py`
- Test: `backend/tests/test_crewchief_delayed_queue.py`

- [ ] **Step 1: Write failing tests**

Add to `test_crewchief_delayed_queue.py`:

```python
def test_gap_ahead_decreasing_still_valid_after_delay():
    from src.intelligence.crewchief_events.delayed_queue import is_message_still_valid
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    msg = CrewChiefMessage(
        event_id="gap_ahead_decreasing",
        text="Gap 1.2",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
        validation_key="gap:ahead:decreasing",
    )
    ctx = CrewChiefFrameContext(
        previous={"time_gap_car_ahead": 2.0},
        current={"time_gap_car_ahead": 1.2},
        strategy={},
        session={},
        now_monotonic=2.0,
    )
    assert is_message_still_valid(msg, ctx) is True


def test_gap_ahead_decreasing_invalid_if_gap_widens():
    from src.intelligence.crewchief_events.delayed_queue import is_message_still_valid
    from src.intelligence.crewchief_events.types import CrewChiefFrameContext

    msg = CrewChiefMessage(
        event_id="gap_ahead_decreasing",
        text="Gap 1.2",
        priority=CrewChiefPriority.NORMAL,
        channel=CrewChiefChannel.ENGINEER,
        validation_key="gap:ahead:decreasing",
    )
    ctx = CrewChiefFrameContext(
        previous={"time_gap_car_ahead": 1.2},
        current={"time_gap_car_ahead": 2.5},
        strategy={},
        session={},
        now_monotonic=2.0,
    )
    assert is_message_still_valid(msg, ctx) is False
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_delayed_queue.py::test_gap_ahead_decreasing_still_valid_after_delay -v`

- [ ] **Step 3: Extend `is_message_still_valid`**

Replace gap validation block in `delayed_queue.py`:

```python
def is_message_still_valid(
    message: CrewChiefMessage,
    ctx: CrewChiefFrameContext | None,
) -> bool:
    if ctx is None:
        return True

    key = message.validation_key or ""
    curr = ctx.current
    prev = ctx.previous or {}

    if key.startswith("gap:ahead:"):
        trend = key.split(":", 2)[-1]
        curr_gap = float(curr.get("time_gap_car_ahead") or curr.get("gap_ahead") or 999.0)
        prev_gap = float(prev.get("time_gap_car_ahead") or prev.get("gap_ahead") or curr_gap)
        if not (0.05 < curr_gap < 30.0):
            return False
        if trend == "decreasing":
            return prev_gap - curr_gap >= 0.2
        if trend == "increasing":
            return curr_gap - prev_gap >= 0.2
        if trend == "holding":
            return abs(curr_gap - prev_gap) <= 0.2
        if trend == "holding_up":
            return curr_gap < 2.0
        return True

    if key.startswith("gap:behind:"):
        trend = key.split(":", 2)[-1]
        curr_gap = float(curr.get("time_gap_car_behind") or curr.get("gap_behind") or 999.0)
        prev_gap = float(prev.get("time_gap_car_behind") or prev.get("gap_behind") or curr_gap)
        if not (0.05 < curr_gap < 30.0):
            return False
        if trend == "pressure":
            return curr_gap < 1.0
        if trend == "increasing":
            return curr_gap - prev_gap >= 0.2 or curr_gap < 1.0
        if trend == "decreasing":
            return prev_gap - curr_gap >= 0.2
        if trend == "holding":
            return abs(curr_gap - prev_gap) <= 0.2
        return True

    if key == "gap:ahead":
        prev_gap = float(prev.get("time_gap_car_ahead") or 999.0)
        curr_gap = float(curr.get("time_gap_car_ahead") or 999.0)
        if curr_gap >= 999.0 or curr_gap <= 0.05:
            return False
        return prev_gap - curr_gap >= 0.3

    if key.startswith("gap:"):
        gap = float(curr.get("time_gap_car_ahead") or curr.get("time_gap_car_behind") or 999.0)
        return 0.05 < gap < 5.0

    if key.startswith("position:"):
        expected = key.split(":", 1)[-1]
        current = ctx.current_position
        return current is not None and str(current) == expected

    return True
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && python -m pytest tests/test_crewchief_delayed_queue.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/delayed_queue.py backend/tests/test_crewchief_delayed_queue.py
git commit -m "feat(timings): delayed queue re-validation for gap trends"
```

---

### Task 6: Cutover LMU-27 — disable GapClosedTrigger LLM

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/cutover_registry.py`
- Modify: `backend/src/intelligence/triggers.py`
- Test: `backend/tests/test_crewchief_timings_cutover.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_timings_cutover.py
from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event
from src.intelligence.triggers import GapClosedTrigger


def test_gap_battle_events_are_cc_owned():
    assert is_cc_owned_event("gap_being_pressured")
    assert is_cc_owned_event("gap_holding_us_up")


def test_gap_closed_trigger_suppressed_when_cc_owns_battle():
    trigger = GapClosedTrigger()
    tele = {"gap_ahead": 1.0, "gap_behind": 99.0, "in_pits": False, "session_type": "race"}
    assert trigger.condition(tele, {}, {"phase": "race"}) is False
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_timings_cutover.py -v`

- [ ] **Step 3: Implement cutover**

In `cutover_registry.py`, extend `CC_OWNED_EVENT_IDS`:

```python
    "gap_ahead_increasing",
    "gap_ahead_decreasing",
    "gap_ahead_holding",
    "gap_behind_increasing",
    "gap_behind_decreasing",
    "gap_behind_holding",
    "gap_being_pressured",
    "gap_holding_us_up",
```

In `triggers.py` `GapClosedTrigger.condition`, at top after pits check:

```python
        from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event
        from src.intelligence.crewchief_events.cc_gates import should_emit_gap_message

        if should_emit_gap_message(telemetry, session) and is_cc_owned_event("gap_being_pressured"):
            self._battle_active = False
            return False
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/crewchief_events/cutover_registry.py backend/src/intelligence/triggers.py backend/tests/test_crewchief_timings_cutover.py
git commit -m "feat(timings): cutover GapClosedTrigger when CC gap messages enabled"
```

---

### Task 7: Sequence fixture + replay test (L3)

**Files:**
- Create: `backend/tests/fixtures/timings/sector_gap_sequence.json`
- Create: `backend/tests/fixtures/timings/helpers.py`
- Test: extend `test_crewchief_timings_module.py`

- [ ] **Step 1: Create fixture**

```json
{
  "meta": {
    "module": "timings",
    "event_id": "gap_ahead_decreasing",
    "lmu_id": "LMU-22",
    "description": "Sector 1→2 with gap closing 2.0→1.2"
  },
  "session": {
    "phase": "race",
    "session_type_int": 10,
    "enable_gap_messages": true,
    "frequency_of_gap_ahead_reports": 10,
    "gap_message_randomness": 0
  },
  "frames": [
    {"sector": 1, "time_gap_car_ahead": 2.0, "session_type_int": 10, "in_pits": false},
    {"sector": 1, "time_gap_car_ahead": 1.8, "session_type_int": 10, "in_pits": false},
    {"sector": 1, "time_gap_car_ahead": 1.5, "session_type_int": 10, "in_pits": false},
    {"sector": 2, "time_gap_car_ahead": 1.2, "session_type_int": 10, "in_pits": false}
  ],
  "expect": {
    "min_messages": 1,
    "event_ids": ["gap_ahead_decreasing"]
  }
}
```

- [ ] **Step 2: Create helper**

```python
# backend/tests/fixtures/timings/helpers.py
from __future__ import annotations

import json
from pathlib import Path

from src.intelligence.crewchief_events.modules.timings import TimingsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext

FIXTURES = Path(__file__).parent


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def replay_timings_fixture(name: str) -> list:
    data = load_fixture(name)
    module = TimingsEvent()
    module._sectors_until_next_ahead = 0
    module._sectors_until_next_behind = 0
    session = data.get("session", {})
    frames = data["frames"]
    collected = []
    prev = None
    for i, frame in enumerate(frames):
        if prev is None:
            prev = frame
            continue
        ctx = CrewChiefFrameContext(
            previous=prev,
            current=frame,
            strategy={},
            session=session,
            now_monotonic=float(i),
        )
        collected.extend(module.evaluate(ctx))
        prev = frame
    return collected
```

- [ ] **Step 3: Write replay test**

```python
def test_sector_gap_sequence_fixture():
    from tests.fixtures.timings.helpers import load_fixture, replay_timings_fixture

    messages = replay_timings_fixture("sector_gap_sequence.json")
    expect = load_fixture("sector_gap_sequence.json")["expect"]
    ids = [m.event_id for m in messages]
    assert len(messages) >= expect["min_messages"]
    assert expect["event_ids"][0] in ids
```

- [ ] **Step 4: Run test — expect PASS**

Run: `cd backend && python -m pytest tests/test_crewchief_timings_module.py::test_sector_gap_sequence_fixture -v`

- [ ] **Step 5: Commit**

```bash
git add backend/tests/fixtures/timings/ backend/tests/test_crewchief_timings_module.py
git commit -m "test(timings): sector gap sequence fixture replay"
```

---

### Task 8: Remove dead proactive gap code

**Files:**
- Modify: `backend/src/intelligence/proactive_monitors.py`

- [ ] **Step 1: Delete unused gap helpers**

Remove from `proactive_monitors.py`:
- constant `GAP_REPORT_INTERVAL_S = 45.0`
- field `self._last_gap_report_at` in `__init__` / reset if present
- method `_format_gap_update` entirely

- [ ] **Step 2: Verify no references**

Run: `cd backend && rg "_format_gap_update|GAP_REPORT_INTERVAL" src tests`

Expected: no matches

- [ ] **Step 3: Run regression**

Run: `cd backend && python -m pytest tests/test_crewchief_timings_module.py tests/test_crewchief_gap_gates.py tests/test_crewchief_delayed_queue.py tests/test_crewchief_timings_cutover.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/src/intelligence/proactive_monitors.py
git commit -m "chore(timings): remove dead proactive gap commentary code"
```

---

### Task 10: Spotter gaps OFF when engineer gaps ON

**Files:**
- Modify: `backend/src/intelligence/spotter.py`
- Test: `backend/tests/test_spotter_runtime_config.py` (extend) or `backend/tests/test_crewchief_timings_spotter_gate.py` (create)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_timings_spotter_gate.py
from src.intelligence.spotter import SpotterService


def test_spotter_skips_gap_alerts_when_cc_gap_messages_enabled():
    spotter = SpotterService()
    spotter.apply_runtime_config({"enableGapMessages": True})
    tick = {"gap_ahead": 0.3, "gap_behind": 99.0, "session_type": "race", "speed_ms": 30.0}
    assert spotter._eval_gaps(tick) == []
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_timings_spotter_gate.py -v`

- [ ] **Step 3: Gate `_eval_gaps` in spotter.py**

At top of `_eval_gaps`:

```python
    def _eval_gaps(self, tick: dict) -> List[AlertMessage]:
        if getattr(self, "_enable_gap_messages", False):
            return []
        now = time.monotonic()
        ...
```

In `apply_runtime_config`:

```python
        if "enableGapMessages" in cfg:
            self._enable_gap_messages = bool(cfg["enableGapMessages"])
```

Default `_enable_gap_messages = True` in `__init__` (CC default).

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/src/intelligence/spotter.py backend/tests/test_crewchief_timings_spotter_gate.py
git commit -m "feat(timings): mute spotter gap UI when CC gap messages enabled"
```

---

### Task 11: Verification gate (Task 22 done)

- [ ] **Run full CC timings slice**

```powershell
cd backend
python -m pytest tests/test_crewchief_gap_trend.py tests/test_crewchief_gap_gates.py tests/test_crewchief_timings_module.py tests/test_crewchief_delayed_queue.py tests/test_crewchief_timings_cutover.py -v
python scripts/verify_alpha_parity.py
```

Expected: all PASS; parity script OK

- [ ] **Update matrix note (agent)**

In `.omo/evidence/cc-behavior-parity-matrix.yaml`, set LMU-22 `paridad` to `PARTIAL` if `enable_gap_messages` default false, or `MATCH` if pilot chooses default true.

- [ ] **Commit verification artifacts if any script output changed**

---

## Self-review checklist

| Spec requirement | Task |
|------------------|------|
| Sector-based (not 45s timer) | Task 4, 7, 8 |
| Increasing/decreasing/holding | Task 1, 3, 4 |
| Landmark/corner optional | Task 4 `_corner_phrase` |
| DelayedMessage + re-validate | Task 5 |
| Battle pressure LMU-27 | Task 4 `_eval_pressure_behind`, Task 6 |
| Fixture sector_gap_sequence.json | Task 7 |
| enable_gap_messages gate | Task 2 |
| Cutover legacy GapClosedTrigger | Task 6 |
| Dead proactive gap code removed | Task 8 |

**Deferred (explicit, not placeholder):**
- `gapPoint` mid-lap CC trigger — post-alpha Task 22b
- UI toggle `enable_gap_messages` in frontend ConfigTab — Task 44 or follow-up
- Full corner map for all LMU tracks — post-alpha

---

## Preguntas — RESUELTAS (piloto 2026-06-07)

| # | Decisión |
|---|----------|
| 1 | **ON por defecto** (`enable_gap_messages=true`, como CC) |
| 2 | **A** — nombre de curva solo si hay mapa |
| 3 | **B** — spotter gaps UI **OFF** cuando ingeniero gaps ON |
| 4 | **A** — presión repetible con cooldown **60 s** |

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-07-crewchief-task22-timings.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between tasks

**2. Inline Execution** — implement tasks 1–9 in this session with checkpoints

**Which approach?**

Also: tasks **23–28** (`lap_times`, `lap_counter`, `push_now`, `session_end`, `fuel` ampliado, `pit_stops`) still need the same treatment — say if you want those plans next in separate files.
