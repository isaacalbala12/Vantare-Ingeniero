# Tasks 29–40 — Vehicle, Opponents & Pearls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar la Wave 5 del port Crew Chief: módulos de vehículo (neumáticos, motor, batería, DRS), multiclase/orden congelado ampliados, rivales + watched opponents, estrategia determinista, perlas y tiempo de carrera — todos como `CrewChiefEventModule` @ 20 Hz con cutover de `proactive_monitors.py` / `triggers.py`.

**Architecture:** Cada módulo evalúa `CrewChiefFrameContext` (prev/curr @ 20 Hz). Mensajes vía `render_template()` → `CrewChiefMessage` → canal **ingeniero**. Los módulos **33–35** expanden skeletons existentes; **29–32, 36–40** son nuevos. Tras cada task: registrar en `cutover_registry.py`, silenciar emisor legacy, añadir gate `enable_*` en `cc_gates.py` cuando aplique.

**Tech Stack:** Python 3.11+, pytest, `crewchief_templates_es.json`, `sector_analysis.py`, `time_format.py`, `pearls_of_wisdom.py`, `shared_strategy.competitors.evaluate_monitored_events`.

**Prerequisito:** Tasks 22–28 DONE (timings, lap, push, session end, fuel, pits wired en `main.py`).

**Referencias:** Master plan §Wave 5 [`2026-06-07-crewchief-complete-port.md`](./2026-06-07-crewchief-complete-port.md) · Parity matrix `.omo/evidence/cc-behavior-parity-matrix.yaml` · Pipeline tests [`2026-06-07-crewchief-pipeline-test-template.md`](./2026-06-07-crewchief-pipeline-test-template.md).

**Fuera de scope (Task 41+):** `driver_swaps.py` → plan separado / Task 41.

---

## Defaults locked (piloto — Wave 5)

| Setting | Default | Notas |
|---------|---------|-------|
| `enable_tyre_temp_messages` | `true` | Temp hot/cooking por rueda |
| `enable_tyre_wear_messages` | `true` | Desgaste medio ≥75% |
| `enable_brake_wear_messages` | `true` | Max brake ≥80% (TyreMonitor CC) |
| `enable_engine_warnings` | `true` | Water/oil >105°C |
| `enable_battery_messages` | `true` | Hypercar SOC |
| `enable_overtaking_aids_messages` | `true` | DRS/PTP edge |
| `enable_multiclass_messages` | `true` | Ya en suite skeleton |
| `enable_frozen_order_messages` | `true` | Instrucción estable 2s |
| `enable_opponent_messages` | `true` | Pit exit, fast lap rival |
| `enable_watched_opponent_messages` | `true` | Solo índices en `session["watched_driver_indices"]` |
| `enable_strategy_messages` | `true` | Sector fuel analysis determinista |
| `enable_pearl_messages` | `true` | Max 2 normal / 4 detailed por carrera |
| `enable_race_time_messages` | `true` | Tiempo/vueltas restantes |
| Tyre hot threshold | `105.0` °C | Alineado `TiresThermalOverheatingTrigger` |
| Tyre cooking threshold | `120.0` °C | Front axle “cooking” |
| Tyre wear warn | `75.0` % avg | Desde proactive actual |
| Brake wear warn | `80.0` % max | Desde proactive actual |
| Engine temp warn | `105.0` °C | water **or** oil |
| Battery low SOC | `20.0` % | Alineado `HybridDeployMapTrigger` |
| Multiclass settle | `6.0` s | CC parity matrix |
| Multiclass check interval | `4.0` s | Entre evaluaciones candidatas |
| Race time report (normal) | cada **5** vueltas | Verbosidad normal |
| Race time report (detailed) | cada **2** vueltas | Verbosidad detailed |
| Pearl frequency | `verbosity.max_pearls_per_race` | 2 normal / 4 detailed (existente) |

**LMU sector encoding:** usar `lap_edge.read_sector()` / `normalize_display_sector()` — ver plan Tasks 23–28.

---

## File map (Tasks 29–40)

| Task | Create | Modify (expand) | Legacy cutover |
|------|--------|---------------|----------------|
| 29 | `modules/tyre_monitor.py`, `vehicle_thresholds.py`, tests | `templates`, `cutover_registry`, `cc_gates`, `proactive_monitors`, `triggers.py` | `_eval_car_monitors` tyre/brake, `TyreDegAccelTrigger`, `TiresThermalOverheatingTrigger`, `BrakeWearCriticalTrigger` |
| 30 | `modules/engine_monitor.py`, tests | templates, cutover, proactive | `_eval_car_monitors` engine block |
| 31 | `modules/battery.py`, tests | templates, cutover, `triggers.py` | `HybridDeployMapTrigger` |
| 32 | `modules/overtaking_aids.py`, tests | templates, cutover, proactive | `_eval_drs` |
| 33 | — | `modules/multiclass.py`, tests, cutover | `MulticlassWarningTrigger`, proactive multiclass |
| 34 | — | `modules/frozen_order.py`, tests, cutover | `_eval_frozen_order` proactive |
| 35 | — | `modules/opponents.py`, tests, cutover | `_eval_competitors` pit/pos/gap |
| 36 | `modules/opponent_messages.py`, tests | templates, cutover, proactive | `_eval_competitor_fast_laps` |
| 37 | `modules/watched_opponents.py`, tests | templates, cutover, `session` keys | `_eval_competitors` watched subset |
| 38 | `modules/strategy.py`, tests | templates, cutover, proactive | `_eval_strategy` sector block |
| 39 | `modules/pearls.py`, tests | templates, cutover, `engine.py` | `_maybe_emit_pearls`, `_check_fast_lap_pearl`, `_emit_pearl` |
| 40 | `modules/race_time.py`, tests | templates, cutover | — (nuevo) |

**Suite registration (`main.py`) — orden objetivo post Wave 5:**

```python
# Tras Task 40, orden CC recomendado:
[
    FlagsEvent(), FrozenOrderEvent(), MulticlassEvent(), penalties_module,
    DamageEvent(), RainEvent(), PositionEvent(),
    LapTimesEvent(), LapCounterEvent(), RaceTimeEvent(),  # 40
    PushNowEvent(), FuelEvent(), PitStopsEvent(),
    TyreMonitorEvent(), EngineMonitorEvent(), BatteryEvent(),  # 29–31
    OvertakingAidsEvent(),  # 32
    TimingsEvent(),
    OpponentsEvent(), OpponentMessagesEvent(), WatchedOpponentsEvent(),  # 35–37
    StrategyEvent(), PearlsEvent(),  # 38–39
    SessionEndEvent(),
]
```

**Verificación final Wave 5:**

```bash
cd backend
python -m pytest tests/ -k "crewchief and (tyre or engine or battery or overtaking or multiclass or frozen or opponent or watched or strategy or pearl or race_time)" -q
python ../scripts/verify_alpha_parity.py
```

---

## Shared infrastructure (Task 29 Step 0 — do first)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/vehicle_thresholds.py`
- Create: `backend/tests/test_crewchief_vehicle_thresholds.py`
- Modify: `backend/src/intelligence/crewchief_events/cc_gates.py` (añadir gates Wave 5)
- Modify: `backend/src/data/crewchief_templates_es.json` (batch templates Wave 5 — ver cada task)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_vehicle_thresholds.py
from src.intelligence.crewchief_events.vehicle_thresholds import (
    avg_tyre_wear,
    hottest_tyre_wheel,
    max_brake_wear,
    tyre_temp_level,
)


def test_tyre_temp_level_hot_and_cooking():
    assert tyre_temp_level({"tyre_temp_fl": 110.0}) == ("fl", "hot")
    assert tyre_temp_level({"tyre_temp_fl": 125.0, "tyre_temp_fr": 100.0}) == ("fl", "cooking")


def test_avg_tyre_wear_from_strategy():
    strategy = {"tyre_wear": {"fl": 70, "fr": 80, "rl": 76, "rr": 74}}
    assert avg_tyre_wear({}, strategy) == 75.0


def test_max_brake_wear():
    strategy = {"brake_wear": {"fl": 60, "fr": 82, "rl": 55, "rr": 50}}
    assert max_brake_wear({}, strategy) == 82.0
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_vehicle_thresholds.py -v`

- [ ] **Step 3: Implement**

```python
# backend/src/intelligence/crewchief_events/vehicle_thresholds.py
from __future__ import annotations

TYRE_HOT_C = 105.0
TYRE_COOKING_C = 120.0
TYRE_WEAR_WARN_PCT = 75.0
BRAKE_WEAR_WARN_PCT = 80.0
ENGINE_TEMP_WARN_C = 105.0
BATTERY_LOW_SOC = 20.0

_WHEELS = ("fl", "fr", "rl", "rr")


def _wear_dict(telemetry: dict, strategy: dict, key: str) -> dict:
    block = strategy.get(key) or {}
    if isinstance(block, dict) and block:
        return block
    out = {}
    for w in _WHEELS:
        v = telemetry.get(f"{key}_{w}")
        if v is not None:
            out[w] = float(v)
    return out


def avg_tyre_wear(telemetry: dict, strategy: dict) -> float:
    wear = _wear_dict(telemetry, strategy, "tyre_wear")
    if not wear:
        vals = [float(telemetry.get(f"tyre_wear_{w}", 0) or 0) for w in _WHEELS]
    else:
        vals = [float(wear.get(w, 0) or 0) for w in _WHEELS]
    return sum(vals) / 4.0 if vals else 0.0


def max_brake_wear(telemetry: dict, strategy: dict) -> float:
    wear = _wear_dict(telemetry, strategy, "brake_wear")
    if not wear:
        vals = [float(telemetry.get(f"brake_wear_{w}", 0) or 0) for w in _WHEELS]
    else:
        vals = [float(wear.get(w, 0) or 0) for w in _WHEELS]
    return max(vals) if vals else 0.0


def tyre_temp_level(telemetry: dict) -> tuple[str, str] | None:
    hottest_w = None
    hottest_t = 0.0
    for w in _WHEELS:
        t = telemetry.get(f"tyre_temp_{w}")
        if t is None:
            continue
        tf = float(t)
        if tf > hottest_t:
            hottest_t = tf
            hottest_w = w
    if hottest_w is None:
        return None
    if hottest_t >= TYRE_COOKING_C:
        return hottest_w, "cooking"
    if hottest_t >= TYRE_HOT_C:
        return hottest_w, "hot"
    return None


def engine_overheat(telemetry: dict) -> tuple[str, float] | None:
    for key in ("engine_water_temp", "oil_temp", "engine_oil_temp"):
        raw = telemetry.get(key)
        if raw is not None and float(raw) > ENGINE_TEMP_WARN_C:
            return key, float(raw)
    return None


def battery_low(telemetry: dict) -> bool:
    charge = float(telemetry.get("battery_charge", 100.0))
    drain = float(telemetry.get("battery_drain", 0.0))
    regen = float(telemetry.get("battery_regen", 0.0))
    return charge < BATTERY_LOW_SOC and (regen - drain) < 0.0
```

- [ ] **Step 4: Extend `cc_gates.py`**

```python
# Añadir al final de cc_gates.py (patrón session_enable_flag):
DEFAULT_ENABLE_TYRE_MESSAGES = True
DEFAULT_ENABLE_ENGINE_MESSAGES = True
DEFAULT_ENABLE_BATTERY_MESSAGES = True
DEFAULT_ENABLE_OVERTAKING_AIDS = True
DEFAULT_ENABLE_OPPONENT_MESSAGES = True
DEFAULT_ENABLE_WATCHED_OPPONENT = True
DEFAULT_ENABLE_STRATEGY_MESSAGES = True
DEFAULT_ENABLE_PEARL_MESSAGES = True
DEFAULT_ENABLE_RACE_TIME_MESSAGES = True
```

- [ ] **Step 5: Run — expect PASS**

- [ ] **Step 6: Commit**

```bash
git add backend/src/intelligence/crewchief_events/vehicle_thresholds.py \
  backend/tests/test_crewchief_vehicle_thresholds.py \
  backend/src/intelligence/crewchief_events/cc_gates.py
git commit -m "feat(crewchief): shared vehicle threshold helpers for wave 5"
```

---

### Task 29: `modules/tyre_monitor.py` — `TyreMonitor.cs` (LMU-11, LMU-18)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/tyre_monitor.py`
- Create: `backend/tests/test_crewchief_tyre_monitor_module.py`
- Modify: `backend/src/data/crewchief_templates_es.json`
- Modify: `backend/src/intelligence/crewchief_events/cutover_registry.py`
- Modify: `backend/src/intelligence/proactive_monitors.py` (quitar tyre/brake de `_eval_car_monitors`)
- Modify: `backend/src/intelligence/triggers.py` (cutover 3 triggers)
- Modify: `backend/src/intelligence/crewchief_events/modules/__init__.py`, `backend/src/main.py`

**Templates a añadir:**

```json
  "tyre_wear_high": {
    "default": "Desgaste alto de neumáticos — media {wear}%."
  },
  "tyre_cooking": {
    "default": "Neumáticos delanteros cocinándose — baja el ritmo.",
    "variants": {
      "wheel=fl": "Neumático delantero izquierdo cocinándose.",
      "wheel=fr": "Neumático delantero derecho cocinándose.",
      "axle=front": "Neumáticos delanteros cocinándose."
    }
  }
```

(`tyre_hot` ya existe en templates.)

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_tyre_monitor_module.py
from src.intelligence.crewchief_events.modules.tyre_monitor import TyreMonitorEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def _ctx(curr: dict, strategy: dict | None = None, now: float = 10.0):
    return CrewChiefFrameContext(
        previous={"session_type_int": 10, "in_pits": False},
        current={**curr, "session_type_int": 10, "in_pits": False},
        strategy=strategy or {},
        session={"phase": "race", "enable_tyre_temp_messages": True, "enable_tyre_wear_messages": True},
        now_monotonic=now,
    )


def test_hot_tyre_message_once():
    module = TyreMonitorEvent()
    m1 = module.evaluate(_ctx({"tyre_temp_fl": 110.0}))
    m2 = module.evaluate(_ctx({"tyre_temp_fl": 110.0}, now=11.0))
    assert any(x.event_id == "tyre_hot" for x in m1)
    assert not any(x.event_id == "tyre_hot" for x in m2)


def test_wear_high_from_strategy():
    module = TyreMonitorEvent()
    messages = module.evaluate(
        _ctx({}, strategy={"tyre_wear": {"fl": 78, "fr": 76, "rl": 74, "rr": 72}})
    )
    assert any(m.event_id == "tyre_wear_high" for m in messages)


def test_brake_wear_high():
    module = TyreMonitorEvent()
    messages = module.evaluate(
        _ctx({}, strategy={"brake_wear": {"fl": 60, "fr": 85, "rl": 50, "rr": 55}})
    )
    assert any(m.event_id == "brake_wear_high" for m in messages)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && python -m pytest tests/test_crewchief_tyre_monitor_module.py -v`

- [ ] **Step 3: Implement module**

```python
# backend/src/intelligence/crewchief_events/modules/tyre_monitor.py
from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.crewchief_events.vehicle_thresholds import (
    TYRE_WEAR_WARN_PCT,
    avg_tyre_wear,
    max_brake_wear,
    tyre_temp_level,
)

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority

CHECK_INTERVAL_S = 5.0


class TyreMonitorEvent(CrewChiefEventModule):
    event_name = "tyre_monitor"

    def __init__(self) -> None:
        self._warned_temp: set[str] = set()
        self._warned_wear = False
        self._warned_brake = False
        self._last_check_at = 0.0

    def clear_state(self) -> None:
        self._warned_temp.clear()
        self._warned_wear = False
        self._warned_brake = False
        self._last_check_at = 0.0

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session) or ctx.current.get("in_pits"):
            return []
        now = ctx.now_monotonic
        if now - self._last_check_at < CHECK_INTERVAL_S:
            return []
        self._last_check_at = now

        out: list[CrewChiefMessage] = []
        if session_enable_flag(ctx.session, "enable_tyre_temp_messages", True):
            if msg := self._eval_temp(ctx):
                out.append(msg)
        if session_enable_flag(ctx.session, "enable_tyre_wear_messages", True):
            if msg := self._eval_wear(ctx):
                out.append(msg)
        if session_enable_flag(ctx.session, "enable_brake_wear_messages", True):
            if msg := self._eval_brake(ctx):
                out.append(msg)
        return out[:2]

    def _eval_temp(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        level = tyre_temp_level(ctx.current)
        if not level:
            return None
        wheel, kind = level
        key = f"{kind}:{wheel}"
        if key in self._warned_temp:
            return None
        self._warned_temp.add(key)
        event_id = "tyre_cooking" if kind == "cooking" else "tyre_hot"
        axle = "front" if wheel in ("fl", "fr") else "rear"
        text = render_template(event_id, {"wheel": wheel, "axle": axle})
        return CrewChiefMessage(
            event_id=event_id,
            text=text,
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=10000,
        )

    def _eval_wear(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        avg = avg_tyre_wear(ctx.current, ctx.strategy)
        if avg < TYRE_WEAR_WARN_PCT or self._warned_wear:
            return None
        self._warned_wear = True
        return CrewChiefMessage(
            event_id="tyre_wear_high",
            text=render_template("tyre_wear_high", {"wear": f"{avg:.0f}"}),
            priority=CrewChiefPriority.NORMAL,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=12000,
        )

    def _eval_brake(self, ctx: CrewChiefFrameContext) -> CrewChiefMessage | None:
        mx = max_brake_wear(ctx.current, ctx.strategy)
        if mx < 80.0 or self._warned_brake:
            return None
        self._warned_brake = True
        return CrewChiefMessage(
            event_id="brake_wear_high",
            text=render_template("brake_wear_high", {"wear": f"{mx:.0f}"}),
            priority=CrewChiefPriority.IMPORTANT,
            channel=CrewChiefChannel.ENGINEER,
            ttl_ms=12000,
        )
```

- [ ] **Step 4: Cutover triggers**

En `BrakeWearCriticalTrigger`, `TyreDegAccelTrigger`, `TiresThermalOverheatingTrigger.condition`:

```python
from src.intelligence.crewchief_events.cc_gates import session_enable_flag
from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event

if session_enable_flag(session, "enable_tyre_temp_messages", True) and is_cc_owned_event("tyre_hot"):
    self._critical_active = False  # o _deg_active / _overheating_active según trigger
    return False
```

Añadir a `cutover_registry.py`: `tyre_hot`, `tyre_cooking`, `tyre_wear_high`, `brake_wear_high`.

- [ ] **Step 5: Proactive cleanup**

Eliminar bloques tyre/brake de `_eval_car_monitors` (líneas ~233–257 en `proactive_monitors.py`).

- [ ] **Step 6: Wire suite** — `TyreMonitorEvent()` en `main.py` tras `PitStopsEvent`.

- [ ] **Step 7: Run tests — expect PASS**

Run: `cd backend && python -m pytest tests/test_crewchief_tyre_monitor_module.py tests/test_crewchief_vehicle_thresholds.py -v`

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(crewchief): TyreMonitor module with temp/wear/brake cutover"
```

---

### Task 30: `modules/engine_monitor.py` — `EngineMonitor.cs` (LMU-29, PARTIAL)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/engine_monitor.py`
- Create: `backend/tests/test_crewchief_engine_monitor_module.py`
- Modify: templates, cutover, proactive, suite

**Ceiling documentado:** LMU no expone oil_pressure fiable → solo water/oil temp >105°C.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_engine_monitor_module.py
from src.intelligence.crewchief_events.modules.engine_monitor import EngineMonitorEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_engine_water_overheat_once():
    module = EngineMonitorEvent()
    ctx = CrewChiefFrameContext(
        previous={"session_type_int": 10},
        current={"engine_water_temp": 108.0, "session_type_int": 10, "in_pits": False},
        strategy={},
        session={"phase": "race", "enable_engine_warnings": True},
        now_monotonic=1.0,
    )
    m1 = module.evaluate(ctx)
    m2 = module.evaluate(ctx)
    assert any(m.event_id == "engine_overheat" for m in m1)
    assert not m2
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Template + module**

```json
  "engine_overheat": {
    "default": "Temperatura motor elevada — {temp} grados."
  }
```

```python
# backend/src/intelligence/crewchief_events/modules/engine_monitor.py
from __future__ import annotations

from src.intelligence.crewchief_events.templates import render_template
from src.intelligence.crewchief_events.vehicle_thresholds import engine_overheat

from ..base import CrewChiefEventModule
from ..cc_gates import session_enable_flag
from ..session_gates import should_suppress_race_event
from ..types import CrewChiefChannel, CrewChiefFrameContext, CrewChiefMessage, CrewChiefPriority


class EngineMonitorEvent(CrewChiefEventModule):
    event_name = "engine_monitor"

    def __init__(self) -> None:
        self._warned = False

    def clear_state(self) -> None:
        self._warned = False

    def evaluate(self, ctx: CrewChiefFrameContext) -> list[CrewChiefMessage]:
        if should_suppress_race_event(ctx.current, ctx.session):
            return []
        if not session_enable_flag(ctx.session, "enable_engine_warnings", True):
            return []
        if ctx.current.get("in_pits") or self._warned:
            return []
        hit = engine_overheat(ctx.current)
        if not hit:
            return []
        _key, temp = hit
        self._warned = True
        return [
            CrewChiefMessage(
                event_id="engine_overheat",
                text=render_template("engine_overheat", {"temp": f"{temp:.0f}"}),
                priority=CrewChiefPriority.IMPORTANT,
                channel=CrewChiefChannel.ENGINEER,
                ttl_ms=15000,
            )
        ]
```

- [ ] **Step 4: Remove engine block from `_eval_car_monitors`**

- [ ] **Step 5: Register + cutover `engine_overheat`**

- [ ] **Step 6: Run + commit**

```bash
git commit -m "feat(crewchief): EngineMonitor module (water/oil temp partial)"
```

---

### Task 31: `modules/battery.py` — `Battery.cs`

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/battery.py`
- Create: `backend/tests/test_crewchief_battery_module.py`
- Modify: `triggers.py` (`HybridDeployMapTrigger` cutover), templates, suite

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_battery_module.py
from src.intelligence.crewchief_events.modules.battery import BatteryEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_battery_low_soc_message():
    module = BatteryEvent()
    ctx = CrewChiefFrameContext(
        previous={"session_type_int": 10},
        current={
            "battery_charge": 15.0,
            "battery_drain": 3.0,
            "battery_regen": 1.0,
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "enable_battery_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert messages[0].event_id == "battery_low_soc"
    assert "batería" in messages[0].text.lower()
```

- [ ] **Step 2: Template + implement**

```json
  "battery_low_soc": {
    "default": "Batería híbrida baja — optimiza despliegue y recuperación."
  },
  "battery_harvest": {
    "default": "Buena recuperación de energía en frenada."
  }
```

Implement `BatteryEvent` usando `vehicle_thresholds.battery_low()`; edge-once `_low_warned`.

- [ ] **Step 3: HybridDeployMapTrigger cutover**

```python
if session_enable_flag(session, "enable_battery_messages", True) and is_cc_owned_event("battery_low_soc"):
    self._critical_active = False
    return False
```

- [ ] **Step 4: Run + commit**

---

### Task 32: `modules/overtaking_aids.py` — `OvertakingAidsMonitor.cs` (PARTIAL)

**Files:**
- Create: `backend/src/intelligence/crewchief_events/modules/overtaking_aids.py`
- Create: `backend/tests/test_crewchief_overtaking_aids_module.py`
- Modify: proactive `_eval_drs`, templates, suite

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_crewchief_overtaking_aids_module.py
from src.intelligence.crewchief_events.modules.overtaking_aids import OvertakingAidsEvent
from src.intelligence.crewchief_events.types import CrewChiefFrameContext


def test_drs_available_edge():
    module = OvertakingAidsEvent()
    ctx = CrewChiefFrameContext(
        previous={"drs_state": False, "session_type_int": 10},
        current={"drs_state": True, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "enable_overtaking_aids_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert messages[0].event_id == "drs_available"
```

- [ ] **Step 2: Templates**

```json
  "drs_available": { "default": "DRS disponible." },
  "drs_unavailable": { "default": "DRS no disponible." },
  "ptp_available": { "default": "Power to pass disponible." }
```

- [ ] **Step 3: Implement** — detectar flancos `drs_state` / `rear_flap_activated` / `ptp_active` si telemetría expone campo.

- [ ] **Step 4: Remove `_eval_drs` from proactive; delete `_last_drs` if unused**

- [ ] **Step 5: Run + commit**

---

### Task 33: Expand `modules/multiclass.py` — `MulticlassWarnings.cs` (LMU-12)

**Estado actual:** skeleton con un solo mensaje `multiclass_faster_behind` y settle 3s.

**Files:**
- Modify: `backend/src/intelligence/crewchief_events/modules/multiclass.py`
- Modify: `backend/tests/test_crewchief_multiclass_module.py`
- Modify: templates, `triggers.py` (`MulticlassWarningTrigger` cutover)

**Escenarios CC a cubrir (MVP Wave 5):**

| event_id | Condición |
|----------|-----------|
| `multiclass_faster_behind` | Clase más rápida detrás, gap -200m..0, closing |
| `multiclass_slower_ahead` | Clase más lenta delante, gap 0..200m |
| `multiclass_class_leader_behind` | Rival detrás es líder de su clase |

Reutilizar `_class_rank` de `triggers.py` — **mover** a `vehicle_thresholds.py` o nuevo `multiclass_utils.py`:

```python
# backend/src/intelligence/crewchief_events/multiclass_utils.py
_CLASS_RANK = {"GT3": 1, "LMP3": 2, "LMP2": 3, "GTE": 3, "HYPERCAR": 5, "LMH": 5, "HY": 5}

def class_rank(name: str) -> int: ...
def is_similar_class(a: str, b: str) -> bool: ...
```

- [ ] **Step 1: Write failing tests** (añadir a test file existente)

```python
def test_slower_class_ahead_warning():
    module = MulticlassEvent(settle_seconds=6.0)
    frame = {
        "session_type_int": 10,
        "player_class": "Hypercar",
        "competitors": [
            {"driver_index": 3, "class_name": "GT3", "gap_to_player": 0.8, "relative_speed_ms": -2.0},
        ],
    }
    first = CrewChiefFrameContext(None, frame, {}, {"phase": "race"}, 10.0)
    second = CrewChiefFrameContext(frame, frame, {}, {"phase": "race"}, 16.5)
    assert module.evaluate(first) == []
    assert any(m.event_id == "multiclass_slower_ahead" for m in module.evaluate(second))
```

- [ ] **Step 2: Expand module + templates**

- [ ] **Step 3: MulticlassWarningTrigger cutover** (mismo patrón gap/flags)

- [ ] **Step 4: Run + commit**

---

### Task 34: Expand `modules/frozen_order.py` — `FrozenOrderMonitor.cs` (LMU-07)

**Estado actual:** solo `frozen_order_instruction` con mensaje de telemetría.

**Ampliar:**
- Flanco `frozen_order_active` false→true → `frozen_order` (“Orden congelado”)
- Flanco true→false → `frozen_order_cleared`
- Mantener `frozen_order_instruction` con stability 2s

- [ ] **Step 1: Write failing test**

```python
def test_frozen_order_start_edge():
    module = FrozenOrderEvent()
    messages = module.evaluate(
        CrewChiefFrameContext(
            previous={"frozen_order_active": False, "session_type_int": 10},
            current={"frozen_order_active": True, "session_type_int": 10},
            strategy={},
            session={"phase": "race", "enable_frozen_order_messages": True},
            now_monotonic=1.0,
        )
    )
    assert any(m.event_id == "frozen_order" for m in messages)
```

- [ ] **Step 2: Implement edges + remove `_eval_frozen_order` from proactive**

- [ ] **Step 3: Run + commit**

---

### Task 35: Expand `modules/opponents.py` — `Opponents.cs` (LMU-26)

**Estado actual:** solo `opponent_pitting`.

**Ampliar:**
- `opponent_pit_exit` — flanco `in_pits` true→false (adyacente: ±1 posición)
- `opponent_position_change` — cambio standing ±1 posición vs player
- Cooldown 45s por rival (`session` o state interno)

- [ ] **Step 1: Write failing test**

```python
def test_opponent_pit_exit_adjacent():
    module = OpponentsEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "standing_position": 4,
            "competitors": [{"driver_index": 7, "driver_name": "Rival", "in_pits": True, "standing_position": 3}],
            "session_type_int": 10,
        },
        current={
            "standing_position": 4,
            "competitors": [{"driver_index": 7, "driver_name": "Rival", "in_pits": False, "standing_position": 5}],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "enable_opponent_messages": True},
        now_monotonic=5.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "opponent_pit_exit" for m in messages)
```

- [ ] **Step 2: Implement + templates `opponent_pit_exit`, `opponent_position_change`**

- [ ] **Step 3: Trim `_eval_competitors` proactive** (pit entry/exit/pos duplicados)

- [ ] **Step 4: Run + commit**

---

### Task 36: `modules/opponent_messages.py` — `OpponentMessages.cs`

**Port:** rival fast lap (desde `_eval_competitor_fast_laps`), solo verbosidad ≥ LOW/detailed gate.

- [ ] **Step 1: Write failing test**

```python
def test_rival_fast_lap_message():
    module = OpponentMessagesEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "competitors": [{"driver_index": 2, "lap_number": 4, "lap_time_previous": 0, "lap_time_best": 98.0}],
            "session_type_int": 10,
        },
        current={
            "competitors": [
                {
                    "driver_index": 2,
                    "driver_name": "Rival B",
                    "lap_number": 5,
                    "lap_time_previous": 97.9,
                    "lap_time_best": 97.9,
                }
            ],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "verbosity_level": "detailed", "enable_opponent_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "opponent_fast_lap" for m in messages)
```

- [ ] **Step 2: Implement** — tolerancia PB `0.05s` (igual LapTimes)

- [ ] **Step 3: Remove `_eval_competitor_fast_laps` from proactive**

- [ ] **Step 4: Run + commit**

---

### Task 37: `modules/watched_opponents.py` — `WatchedOpponents.cs` (LMU-34)

**Session keys:**

```python
session["watched_driver_indices"]  # list[int], default []
session["watch_snip_requested"]    # bool, one-shot from voice command (Task 44)
```

**Mensajes:** pit entry/exit, gap change >1s, PB lap — **solo** rivales watched.

- [ ] **Step 1: Write failing test**

```python
def test_watched_opponent_pit_entry_only_when_watched():
    module = WatchedOpponentsEvent()
    ctx = CrewChiefFrameContext(
        previous={
            "competitors": [{"driver_index": 9, "driver_name": "Target", "in_pits": False}],
            "session_type_int": 10,
        },
        current={
            "competitors": [{"driver_index": 9, "driver_name": "Target", "in_pits": True, "standing_position": 2}],
            "session_type_int": 10,
        },
        strategy={},
        session={"phase": "race", "watched_driver_indices": [9], "enable_watched_opponent_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "watched_opponent_pitting" for m in messages)
```

- [ ] **Step 2: Implement + templates `watched_opponent_*`**

- [ ] **Step 3: Anti-spam** — cooldown 30s por `(driver_index, event_type)`

- [ ] **Step 4: Run + commit**

---

### Task 38: `modules/strategy.py` — `Strategy.cs`

**Port determinista** del bloque sector fuel en `_eval_strategy` (sin LLM):

- Input: `fuel_per_lap_raw`, `fuel_per_lap_last`, `track_name`, `track_length` desde telemetría/strategy
- Output: 1 mensaje cada 60s max con mejor insight atacar/defender (`format_sector_analysis` → template corto TTS)

- [ ] **Step 1: Write failing test**

```python
def test_strategy_sector_message_throttled():
    module = StrategyEvent()
    strategy = {
        "fuel_per_lap_raw": [1.0] * 100,
        "fuel_per_lap_last": [0.9] * 100,
        "track_length": 7000,
    }
    curr = {"track_name": "Spa", "session_type_int": 10, "fuel_per_lap_raw": strategy["fuel_per_lap_raw"], "fuel_per_lap_last": strategy["fuel_per_lap_last"]}
    ctx = CrewChiefFrameContext(
        previous=curr,
        current=curr,
        strategy=strategy,
        session={"phase": "race", "enable_strategy_messages": True, "verbosity_level": "detailed"},
        now_monotonic=100.0,
    )
    m1 = module.evaluate(ctx)
    m2 = module.evaluate(CrewChiefFrameContext(curr, curr, strategy, ctx.session, 110.0))
    assert m1  # first after 60s window
    assert not m2  # throttled
```

- [ ] **Step 2: Template `strategy_sector_advice`**

```json
  "strategy_sector_advice": {
    "default": "{advice}"
  }
```

- [ ] **Step 3: Remove sector block from proactive `_eval_strategy`**

- [ ] **Step 4: Run + commit**

---

### Task 39: `modules/pearls.py` — `PearlsOfWisdom.cs` (LMU-24)

**Mover lógica de `engine.py`:**
- `OVERTAKE` / `COMEBACK` / `FAST_LAP` / `STANDARD` (cada 12 vueltas en detailed)
- Usar `PearlsService` existente; canal **ingeniero** (no category `pearl` silenciado)

- [ ] **Step 1: Write failing test**

```python
def test_pearl_on_position_gain():
    module = PearlsEvent()
    ctx = CrewChiefFrameContext(
        previous={"standing_position": 6, "session_type_int": 10},
        current={"standing_position": 5, "session_type_int": 10},
        strategy={},
        session={"phase": "race", "enable_pearl_messages": True, "verbosity_level": "normal"},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "pearl_overtake" for m in messages)
```

- [ ] **Step 2: Implement PearlsEvent** — wrap `PearlsService.on_event()`, track `_worst_position` interno para COMEBACK

- [ ] **Step 3: Remove from engine.py:**

```python
# Eliminar llamadas en evaluate_cycle:
#   self._maybe_emit_pearls(telemetry_dict)
#   self._check_fast_lap_pearl(telemetry_dict)
#   self._emit_standard_pearl_every_n_laps(...)
```

Mantener `PearlsService` en engine solo si otros paths lo necesitan; preferir instancia en `PearlsEvent`.

- [ ] **Step 4: Templates `pearl_overtake`, `pearl_comeback`, `pearl_fast_lap`, `pearl_standard`**

- [ ] **Step 5: Run + commit**

---

### Task 40: `modules/race_time.py` — `RaceTime.cs`

**Port:** anuncios de tiempo/vueltas restantes en carrera.

- [ ] **Step 1: Write failing test**

```python
from src.intelligence.crewchief_events.modules.race_time import RaceTimeEvent
from src.intelligence.crewchief_events.lap_edge import lap_completed


def test_time_remaining_on_lap_five_normal_verbosity():
    module = RaceTimeEvent()
    ctx = CrewChiefFrameContext(
        previous={"lap_number": 4, "session_time_left": 3600, "session_type_int": 10},
        current={"lap_number": 5, "session_time_left": 3500, "session_type_int": 10, "in_pits": False},
        strategy={},
        session={"phase": "race", "verbosity_level": "normal", "enable_race_time_messages": True},
        now_monotonic=1.0,
    )
    messages = module.evaluate(ctx)
    assert any(m.event_id == "race_time_remaining" for m in messages)
    assert "minuto" in messages[0].text.lower() or "segundo" in messages[0].text.lower()
```

- [ ] **Step 2: Implement** — usar `format_time_remaining()` de `time_format.py`; alternar `session_laps_left` si finish by laps

```python
# backend/src/intelligence/crewchief_events/modules/race_time.py
from src.intelligence.time_format import format_time_remaining

class RaceTimeEvent(CrewChiefEventModule):
    def _should_announce(self, ctx) -> bool:
        level = str(ctx.session.get("verbosity_level") or "normal").lower()
        lap = int(ctx.current.get("lap_number") or 0)
        if level == "detailed":
            return lap > 0 and lap % 2 == 0
        return lap > 0 and lap % 5 == 0
```

- [ ] **Step 3: Templates**

```json
  "race_time_remaining": {
    "default": "Quedan {remaining} de carrera."
  },
  "race_laps_remaining": {
    "default": "Quedan {laps} vueltas."
  }
```

- [ ] **Step 4: Wire suite** — insertar `RaceTimeEvent()` tras `LapCounterEvent`

- [ ] **Step 5: Run + commit**

---

## Task 41 (integration checkpoint — Wave 5 closure)

**Not driver_swaps — this is Wave 5 wiring only.**

- [ ] **Step 1: Update `cutover_registry.py`** con todos los event_ids 29–40

- [ ] **Step 2: Update `conftest.py` `mock_session_dict`** — añadir disable flags para triggers legacy de vehicle/battery/multiclass si tests lo requieren

- [ ] **Step 3: Create `backend/tests/test_crewchief_tasks29_40_cutover.py`**

```python
from src.intelligence.triggers import HybridDeployMapTrigger, MulticlassWarningTrigger
from src.intelligence.proactive_monitors import ProactiveMonitorSuite
from src.intelligence.immediate_alert import proactive_event_id


def test_hybrid_trigger_suppressed_when_cc_battery_on():
    t = HybridDeployMapTrigger()
    tele = {"battery_charge": 10.0, "battery_drain": 2.0, "battery_regen": 0.0}
    assert t.condition(tele, {}, {"enable_battery_messages": True}) is False


def test_proactive_no_tyre_monitor_after_cutover():
    suite = ProactiveMonitorSuite()
    events = suite.evaluate(
        {"lap_number": 5, "session_type": "race"},
        {"tyre_wear": {"fl": 90, "fr": 90, "rl": 90, "rr": 90}},
        {"phase": "RACE"},
    )
    assert not any(proactive_event_id(e) == "tyre_monitor" for e in events)
```

- [ ] **Step 4: Full pytest wave 5**

Run: `cd backend && python -m pytest tests/ -k "crewchief and (tyre or engine or battery or overtaking or multiclass or frozen or opponent or watched or strategy or pearl or race_time or tasks29)" -q`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(crewchief): complete wave 5 modules 29-40 with cutover tests"
```

---

## Self-review (spec coverage)

| Task | Spec requirement | Covered |
|------|------------------|---------|
| 29 | Tyre hot/cooking, wear, brake LMU-11/18 | Task 29 + vehicle_thresholds |
| 30 | Engine water/oil PARTIAL LMU-29 | Task 30 |
| 31 | Hypercar battery SOC | Task 31 + HybridDeploy cutover |
| 32 | DRS/PTP PARTIAL | Task 32 |
| 33 | Multiclass 8+ scenarios MVP 3 | Task 33 expand |
| 34 | Frozen order lane/column | Task 34 expand |
| 35 | Opponent pit/position LMU-26 | Task 35 expand |
| 36 | OpponentMessages fast lap | Task 36 |
| 37 | WatchedOpponents LMU-34 | Task 37 |
| 38 | Strategy deterministic no LLM | Task 38 |
| 39 | Pearls frequency/gates LMU-24 | Task 39 |
| 40 | Race time reports | Task 40 |
| D3 anti-fork | Legacy emitters removed per task | Each task proactive/trigger step |
| D4 20 Hz | All modules in suite | Task 41 wiring |

**Placeholder scan:** ningún TBD — thresholds y paths concretos arriba.

**Type consistency:** `CrewChiefFrameContext`, `session_enable_flag`, `render_template` usados en todos los módulos; `_class_rank` movido a `multiclass_utils.py` para evitar duplicar con triggers.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-07-crewchief-tasks29-40-vehicle-opponents.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Recommended order if time-constrained (decisions doc):**

1. **29 → 33 → 34** (vehicle + multiclase + frozen — highest LMU impact)
2. **35 → 37** (opponents + watched)
3. **30 → 31 → 32** (engine/battery/DRS — PARTIAL OK)
4. **38 → 39 → 40** (strategy/pearls/race time — deferrable post-show)
5. **Task 41 integration checkpoint**

Which approach?
