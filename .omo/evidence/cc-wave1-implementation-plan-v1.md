---
generated: 2026-06-07
sources: [.omo/evidence/cc-wave1-gaps-closed.md, .omo/evidence/cc-message-templates-p0.md, Vantare repo paths as cited]
---

# Plan de Implementación Wave 1 v1 — Paridad Conductual CC → Vantare

## 1. Objetivo Wave 1

Cerrar los 6 gaps conductuales más críticos entre Crew Chief V4 y Vantare Ingeniero para Le Mans Ultimate: daño audible (impacto + puncture + crash), ciclo completo de Safety Car (fases pits-closed/open/green), penalización con conteo regresivo 3/2/1/pit-now, detección de adelantamientos, latencia de eventos críticos (routing inmediato vs batch), y lluvia en tiempo real (niveles drizzle→storm). Al finalizar, el piloto percibe que Vantare "suena a CC" en estas 6 urgencias.

**No incluye:** LMU-40 (FCY spotter cooldown), LMU-18 (tyre temp por rueda), LMU-19 (push now best lap), LMU-28 (session end evaluation), LMU-45 (fuel persistence), engine/tranny damage, PitManager, overlays, MQTT.

## 2. Pre-requisitos

- **Branch:** `main` o nueva branch `wave1-parity`
- **Tests baseline:** `python scripts/verify_audio_pipeline.py` debe pasar
- **No commitear sin petición del usuario**
- **Entregables de referencia:**
  - `.omo/evidence/cc-wave1-gaps-closed.md` (gap resolutions)
  - `.omo/evidence/cc-message-templates-p0.md` (TTS templates)
  - `.omo/evidence/cc-p0-wave1-locked.md` (Wave 1 architecture rules)

## 3. Fases de Implementación

### F0 — Telemetría Wave 1 Fields

**Objetivo:** Añadir los 5 campos LMU necesarios para Wave 1 a TelemetryFrame, strategy_service, strategy_runner y spotter_adapter.

**Archivos:**
- `shared-strategy/src/shared_strategy/models.py` — TelemetryFrame: añadir campos
- `backend/src/services/strategy_service.py` — _process_cycle(): leer mLocalAccel, mRaining, mYellowFlagState, mFlat, mTrackLimitsSteps
- `sidecar/src/sidecar/strategy_runner.py` — process_cycle(): mismos campos (duplicar lógica)
- `backend/src/intelligence/spotter_adapter.py` — frame_to_spotter_tick: pasar nuevos campos si aplica

**Campos a añadir en TelemetryFrame:**
```python
raining_intensity: float = 0.0           # mRaining 0.0-1.0
yellow_flag_state: int = 0               # mYellowFlagState -1..7
local_accel_x: float = 0.0              # mLocalAccel.x
local_accel_y: float = 0.0              # mLocalAccel.y
local_accel_z: float = 0.0              # mLocalAccel.z
tyre_flat_fl: bool = False              # mWheels[0].mFlat
tyre_flat_fr: bool = False
tyre_flat_rl: bool = False
tyre_flat_rr: bool = False
track_limits_steps: int = 0             # mTrackLimitsSteps (UNKNOWN, leer pero no usar)
```

**Bloque a insertar en strategy_service.py** (tras línea 246, dentro del `if not offline`):
Ver `cc-wave1-gaps-closed.md` Sección D para código exacto.

**Tests nuevos:** `test_telemetry_wave1_fields.py`
```python
def test_telemetry_frame_has_raining():
    frame = TelemetryFrame()
    assert hasattr(frame, "raining_intensity")
    assert frame.raining_intensity == 0.0

def test_telemetry_frame_has_yellow_flag_state():
    frame = TelemetryFrame()
    assert hasattr(frame, "yellow_flag_state")

def test_telemetry_frame_has_local_accel():
    frame = TelemetryFrame()
    assert hasattr(frame, "local_accel_x")

def test_telemetry_frame_has_tyre_flat():
    frame = TelemetryFrame()
    assert frame.tyre_flat_fl is False

def test_strategy_service_reads_raining():
    """Mock LMU data, verify raining_intensity set in frame."""
    # usar mock_race_state con mRaining simulado
```

**Definition of Done:**
- [ ] TelemetryFrame tiene los 10 campos nuevos con defaults correctos
- [ ] `pytest tests/test_telemetry_wave1_fields.py` pasa
- [ ] strategy_service._process_cycle() setea raining_intensity desde mRaining
- [ ] strategy_service._process_cycle() setea tyre_flat_* desde mWheels[i].mFlat
- [ ] strategy_service._process_cycle() setea local_accel_* desde mLocalAccel
- [ ] strategy_runner.process_cycle() tiene los mismos cambios duplicados

**Riesgo:** BAJO. Solo añadir campos, no cambiar lógica existente.
**Estimación:** 2h

---

### F1 — LMU-33: Routing Inmediato vs Commentary Batch

**Objetivo:** Bifurcar eventos críticos (race_start, SC, damage severo, penalty pit_now, overtake, rain cambio nivel) para que salgan como alert IMMEDIATE, no pasen por commentary batch.

**Archivos:**
- `backend/src/intelligence/proactive_monitors.py` — Añadir `ImmediateAlert` dataclass + `IMMEDIATE_EVENTS` set. Modificar `evaluate()` para devolver `ImmediateAlert | CommentaryEvent`
- `backend/src/intelligence/engine.py` — Refactor `_run_proactive_monitors()` para bifurcar: `ImmediateAlert → AlertMessage → broadcast_sync()`, `CommentaryEvent → enqueue_commentary()`

**Código a insertar en proactive_monitors.py:**
```python
from dataclasses import dataclass, field
from typing import Union

@dataclass
class ImmediateAlert:
    event_id: str
    message: str
    priority: str      # "CRITICAL"|"HIGH"|"MEDIUM"|"LOW"
    category: str      # canal semántico
    payload: dict = field(default_factory=dict)

IMMEDIATE_EVENTS: frozenset[str] = frozenset({
    "race_start", "flags_yellow", "flags_safety_car",
    "damage", "penalties", "overtake", "rain_drizzle",
    "rain_light", "rain_heavy",
})

CommentaryEvent = tuple[str, str, str]  # event_id, summary, priority
ProactiveOutput = Union[ImmediateAlert, CommentaryEvent]
```

**Refactor de evaluate()** — el método retorna `list[ProactiveOutput]` en vez de `list[CommentaryEvent]`:
- Los eventos en `IMMEDIATE_EVENTS` se devuelven como `ImmediateAlert`
- El resto se devuelven como `CommentaryEvent` tuple (sin cambios)

**Refactor de engine.py `_run_proactive_monitors()`** (código actual líneas 286-299):
```python
async def _run_proactive_monitors(self, telemetry_dict, strategy_dict, session_dict):
    events = self.proactive_monitors.evaluate(
        telemetry_dict, strategy_dict, session_dict,
        history_store=self._get_history_store(),
        strategy_service=self._get_strategy_service(),
    )
    for evt in events:
        if isinstance(evt, ImmediateAlert):
            alert = AlertMessage(
                event="alert",
                alert_id=str(uuid.uuid4()),
                category=evt.category,
                message=evt.message,
                audio_priority=str(int(Priority[evt.priority].value)),
                payload={"severity": evt.priority, **evt.payload},
            )
            self.broadcaster.send(alert)
        else:
            event_id, summary, priority = evt
            self.enqueue_commentary(event_id, summary, priority)
```

**Tests nuevos:** `test_immediate_routing.py`
```python
@pytest.mark.asyncio
async def test_race_start_goes_immediate_not_batch():
    """race_start debe emitirse como AlertMessage, no como commentary_end."""
    engine, messages = _engine_with_capture()
    await engine.evaluate_cycle(
        {"lap_number": 1, "standing_position": 5},
        {},
        {"phase": "RACE"},
    )
    alerts = [m for m in messages if isinstance(m, AlertMessage)]
    assert any("Salida" in a.message for a in alerts)
    commentary = [m for m in messages if m.event == "commentary_end"]
    assert not any("Salida" in c.full_text for c in commentary)

@pytest.mark.asyncio
async def test_position_change_still_in_batch():
    """position_change NO debe ir a AlertMessage."""
    engine, messages = _engine_with_capture()
    engine.proactive_monitors._last_standing = 8
    await engine.evaluate_cycle(
        {"lap_number": 2, "standing_position": 6, "session_type": "RACE"},
        {},
        {"phase": "RACE"},
    )
    commentary = [m for m in messages if m.event == "commentary_end"]
    assert any("P6" in c.full_text for c in commentary)
```

**Definition of Done:**
- [ ] race_start emite AlertMessage (no commentary batch)
- [ ] flags_yellow/SC emiten AlertMessage
- [ ] position_change/lap_complete siguen en commentary batch
- [ ] `pytest tests/test_immediate_routing.py` pasa

**Riesgo:** BAJO. Cambio de routing, no de lógica.
**Estimación:** 3h

---

### F2 — LMU-09: Damage + Puncture + Crash

**Objetivo:** Implementar detección de daño por impacto (severidad), pinchazo (mFlat), crash severo (mLocalAccel >40G) con mensajes deterministas inmediatos.

**Archivos:**
- `backend/src/intelligence/damage_report.py` — Añadir puncture detection, crash G detection, impact severity levels
- `backend/src/intelligence/spotter.py` — Extender `_eval_damage()` para usar nuevos detectores
- `backend/src/intelligence/proactive_monitors.py` — Extender `_eval_impact_damage()` para usar ImmediateAlert
- `backend/tests/test_damage_wave1.py` — Tests

**Fix typo:** En `cc-message-templates-p0.md` línea 29: cambiar "平衡" por "balance"

**Cambios damage_report.py:**
```python
# AÑADIR:
IMPACT_CRASH_THRESHOLD_MS2 = 392.0  # 40G en m/s²

def detect_puncture(tick: dict) -> tuple[bool, int]:
    """Detecta pinchazo vía mFlat. Retorna (hay_pinchazo, índice_rueda)."""
    for i in range(4):
        if tick.get(f"tyre_flat_{['fl','fr','rl','rr'][i]}", False):
            return True, i
    return False, -1

def detect_crash_g(tick: dict, prev_tick: dict | None) -> bool:
    """Detecta impacto >40G via mLocalAccel."""
    ax = float(tick.get("local_accel_x", 0))
    ay = float(tick.get("local_accel_y", 0))
    az = float(tick.get("local_accel_z", 0))
    magnitude = math.sqrt(ax*ax + ay*ay + az*az)
    return magnitude >= IMPACT_CRASH_THRESHOLD_MS2

PUNCTURE_WHEEL_NAMES = ["delantero izquierdo", "delantero derecho", "trasero izquierdo", "trasero derecho"]

def format_puncture_message(wheel_index: int) -> str:
    return f"Pinchazo {PUNCTURE_WHEEL_NAMES[wheel_index]}."
```

**Tests nuevos:** `test_damage_wave1.py`
```python
def test_damage_severity_grave_from_dent():
    tick = {"dent_severity_max": 2, "damage_aero": 50}
    assert classify_damage_severity(tick) == "grave"

def test_puncture_detected_via_mflat():
    tick = {"tyre_flat_fr": True}
    punct, idx = detect_puncture(tick)
    assert punct
    assert idx == 1  # FR

def test_crash_40g_detected():
    tick = {"local_accel_x": 0, "local_accel_y": 0, "local_accel_z": -400}
    assert detect_crash_g(tick, None)

def test_crash_below_threshold():
    tick = {"local_accel_x": 0, "local_accel_y": 0, "local_accel_z": -50}
    assert not detect_crash_g(tick, None)

def test_damage_edge_once():
    """Mismo last_impact_et no debe repetir alerta."""
    spotter = SpotterService(broadcast_callback=lambda m: None)
    tick1 = {"last_impact_et": 100, "last_impact_magnitude": 50, "dent_severity_max": 1}
    tick2 = {"last_impact_et": 100, "last_impact_magnitude": 50, "dent_severity_max": 1}
    assert len(spotter.evaluate(tick1)) >= 1
    assert len(spotter.evaluate(tick2)) == 0  # mismo ET
```

**Definition of Done:**
- [ ] Impacto severo (dent_max>=2) → "Golpe fuerte. Daño grave en el frontal." (IMMEDIATE)
- [ ] Pinchazo (mFlat) → "Pinchazo delantero derecho." (IMMEDIATE, delay 4-7s)
- [ ] Crash >40G → "¿Estás bien?" con 3 retries (IMMEDIATE)
- [ ] Edge-once por impacto ET
- [ ] Typo "平衡" corregido a "balance" en plantillas
- [ ] `pytest tests/test_damage_wave1.py` pasa

**Riesgo:** MEDIO. mFlat puede no funcionar en LMU real. Fallback: umbral de presión.
**Estimación:** 4h

---

### F3 — LMU-15: FCY Phases (PITS_CLOSED → PITS_OPEN → LAST_LAP → GREEN)

**Objetivo:** Reemplazar el único mensaje "SC activo" por ciclo completo de fases FCY.

**Archivos:**
- `backend/src/intelligence/flags_monitor.py` — Añadir `fcy_phase` a `FlagSnapshot`. Añadir detección transiciones mYellowFlagState. Añadir mensajes por subfase
- `backend/src/intelligence/spotter.py` — `_eval_safety_car()` usar nueva flag_fcy_phase

**Cambios flags_monitor.py:**
```python
# Añadir a FlagSnapshot:
fcy_phase: int = 0  # -1=invalid, 0=none, 1=pending, 2=pits_closed, 3=pit_lead_lap, 4=pits_open, 5=last_lap, 6=resume

# Añadir a FlagEventType:
FCY_PITS_CLOSED = "fcy_pits_closed"
FCY_PITS_OPEN = "fcy_pits_open"  
FCY_LAST_LAP = "fcy_last_lap"
FCY_RESUME = "fcy_resume"
GREEN = "green"

# snapshot_from_telemetry: leer yellow_flag_state del dict
fcy_phase = int(telemetry.get("yellow_flag_state", 0))

# detect_flag_transitions: detectar cambios en fcy_phase
# Mapeo: 2→FCY_PITS_CLOSED, 4→FCY_PITS_OPEN, 5→FCY_LAST_LAP, 6→FCY_RESUME, gamePhase 6→5→GREEN
```

**Mensajes** (desde cc-message-templates-p0.md):
- `fcy_phase=2`: "Safety Car desplegado. Pits cerrados." (IMMEDIATE priority 4)
- `fcy_phase=4`: "Pits abiertos." (IMMEDIATE priority 3)
- `fcy_phase=5`: "Última vuelta de Safety Car." (IMMEDIATE priority 3)
- `fcy_phase=6`: "Prepárate para relanzamiento." (IMMEDIATE priority 3)
- gamePhase 5→6: solo si no pasa por 2 (emergencia sin SC): "Bandera amarilla en todo el circuito." (IMMEDIATE)
- gamePhase 6→5: "Bandera verde. A tope." (IMMEDIATE priority 3)

**Tests nuevos:** `test_fcy_wave1.py`
```python
def test_fcy_phase_transition_pits_closed():
    prev = FlagSnapshot(fcy_phase=0)
    curr = FlagSnapshot(fcy_phase=2, safety_car=True)
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.FCY_PITS_CLOSED for e in events)

def test_fcy_phase_transition_green():
    prev = FlagSnapshot(fcy_phase=6, safety_car=True)
    curr = FlagSnapshot(fcy_phase=0, safety_car=False)
    events = detect_flag_transitions(prev, curr)
    assert any(e.event_type == FlagEventType.GREEN for e in events)
```

**Definition of Done:**
- [ ] PITS_CLOSED → alert IMMEDIATE "Safety Car desplegado. Pits cerrados."
- [ ] PITS_OPEN → alert IMMEDIATE "Pits abiertos."
- [ ] LAST_LAP → alert IMMEDIATE "Última vuelta de Safety Car."
- [ ] GREEN → alert IMMEDIATE "Bandera verde. A tope."
- [ ] Fallback: si mYellowFlagState no cambia, solo gamePhase 6→5 mensajes
- [ ] `pytest tests/test_fcy_wave1.py` pasa

**Riesgo:** MEDIO. mYellowFlagState puede no funcionar en LMU (ver plan validación Sección H en gaps-closed).
**Estimación:** 3h

---

### F4 — LMU-13: Penalty Countdown 3/2/1/Pit Now

**Objetivo:** Reemplazar el mensaje genérico "Penalización detectada" por conteo regresivo completo estilo CC.

**Archivos:**
- `backend/src/intelligence/triggers.py` — Refactor `PenaltyMonitorTrigger` para usar PenaltyTracker
- `backend/src/intelligence/penalty_tracker.py` — NUEVO: state machine
- `backend/tests/test_penalty_wave1.py` — Tests

**PenaltyTracker** (state machine de cc-wave1-gaps-closed.md Sección G):

```python
class PenaltyTracker:
    """State machine for penalty countdown (LMU-13)."""
    
    def __init__(self):
        self._state = "CLEAR"
        self._penalty_lap: int = -1
        self._pit_now_played: bool = False
        self._disqualified_played: bool = False
        self._not_served_played: bool = False
    
    def evaluate(self, num_penalties: int, lap: int, sector: int, in_pits: bool) -> ImmediateAlert | None:
        if self._state == "CLEAR" and num_penalties > 0:
            self._state = "COUNTDOWN"
            self._penalty_lap = lap
            self._pit_now_played = False
            return ImmediateAlert("penalty_new", "Penalización asignada. Tienes 3 vueltas para entrar en boxes.", "HIGH", "penalty")
        
        if self._state == "COUNTDOWN":
            if num_penalties == 0:
                self._state = "CLEAR"
                return ImmediateAlert("penalty_served", "Penalización cumplida. Buen trabajo.", "MEDIUM", "penalty")
            
            laps_since = lap - self._penalty_lap
            if laps_since >= 2 and not self._pit_now_played and sector == 3:
                self._pit_now_played = True
                return ImmediateAlert("penalty_pit_now", "Entra a boxes ahora.", "CRITICAL", "penalty")
            if laps_since == 2 and not in_pits:
                return ImmediateAlert("penalty_2_laps", "2 vueltas. Tienes que entrar.", "HIGH", "penalty")
            if laps_since == 1 and not in_pits:
                return ImmediateAlert("penalty_1_lap", "1 vuelta. Entra ahora o serás descalificado.", "CRITICAL", "penalty")
            if laps_since >= 3 and num_penalties > 0 and not self._disqualified_played:
                self._disqualified_played = True
                return ImmediateAlert("penalty_disqualified", "No has servido la penalización. Vas a ser descalificado.", "CRITICAL", "penalty")
        
        if in_pits and self._state == "COUNTDOWN" and num_penalties > 0 and not self._not_served_played:
            # Salió de pits sin servir
            if not in_pits:
                self._not_served_played = True
                return ImmediateAlert("penalty_not_served", "No has servido la penalización.", "HIGH", "penalty")
        
        return None
```

**Tests nuevos:** `test_penalty_wave1.py`
```python
def test_penalty_new_starts_countdown():
    tracker = PenaltyTracker()
    result = tracker.evaluate(1, 5, 1, False)
    assert result is not None
    assert "3 vueltas" in result.message

def test_penalty_countdown_2_laps():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    result = tracker.evaluate(1, 7, 1, False)  # 7-5=2
    assert result is not None
    assert "2 vueltas" in result.message

def test_penalty_served_clears():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    result = tracker.evaluate(0, 7, 1, False)
    assert result is not None
    assert "cumplida" in result.message
    assert tracker._state == "CLEAR"

def test_penalty_pit_now_sector_3():
    tracker = PenaltyTracker()
    tracker._penalty_lap = 5
    tracker._state = "COUNTDOWN"
    result = tracker.evaluate(1, 7, 3, False)  # lap-penLap=2, sector=3
    assert result is not None
    assert "Entra a boxes ahora" in result.message
```

**Definition of Done:**
- [ ] Penalización nueva → "Penalización asignada. Tienes 3 vueltas..."
- [ ] 2 vueltas después → "2 vueltas. Tienes que entrar."
- [ ] 1 vuelta después → "1 vuelta. Entra ahora o serás descalificado."
- [ ] Sector 3 con lap-penLap=2 → "Entra a boxes ahora."
- [ ] Servida → "Penalización cumplida. Buen trabajo."
- [ ] No servida → mensaje descalificación
- [ ] `pytest tests/test_penalty_wave1.py` pasa

**Riesgo:** BAJO. LMU da mNumPenalties. CC countdown es 3-lap convención, no depende de datos LMU.
**Estimación:** 3h

---

### F5 — LMU-20: Overtake Detection

**Objetivo:** Implementar detección de adelantamientos y rebasamientos.

**Archivos:**
- `backend/src/intelligence/proactive_monitors.py` — Añadir `_detect_overtakes()` + estado persistente
- `backend/tests/test_overtake_wave1.py` — Tests

**Pseudocódigo:** Ver `cc-wave1-gaps-closed.md` Sección F para implementación completa (40 líneas).

**Tests nuevos:** `test_overtake_wave1.py`
```python
def test_overtake_detected():
    monitor = ProactiveMonitorSuite()
    monitor._last_standing = 5
    monitor._last_opponent_ahead_key = "rival1"
    telemetry = {
        "standing_position": 4,  # mejoró
        "competitors": [
            {"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False},
        ],
        "gap_ahead": 2.0, "gap_behind": 0.5,
        "in_pits": False, "session_type": "RACE",
        "yellow_flag_active": False, "full_course_yellow_active": False,
    }
    events = monitor._detect_overtakes(telemetry, time.monotonic())
    overtakes = [e for e in events if e.event_id == "overtake"]
    assert len(overtakes) >= 1

def test_no_overtake_under_yellow():
    monitor = ProactiveMonitorSuite()
    telemetry = {
        "standing_position": 4,
        "competitors": [{"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False}],
        "gap_ahead": 2.0, "gap_behind": 0.5,
        "in_pits": False, "session_type": "RACE",
        "yellow_flag_active": True,
    }
    assert len(monitor._detect_overtakes(telemetry, time.monotonic())) == 0

def test_no_overtake_if_rival_in_pits():
    monitor = ProactiveMonitorSuite()
    telemetry = {
        "standing_position": 4,
        "competitors": [{"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": True}],
        "gap_ahead": 2.0, "gap_behind": 0.5,
        "in_pits": False, "session_type": "RACE",
        "yellow_flag_active": False, "full_course_yellow_active": False,
    }
    assert len(monitor._detect_overtakes(telemetry, time.monotonic())) == 0

def test_overtake_cooldown_20s():
    monitor = ProactiveMonitorSuite()
    monitor._last_overtake_at = time.monotonic()  # just now
    telemetry = {
        "standing_position": 4,
        "competitors": [{"driver_index": 1, "driver_name": "Rival", "standing_position": 5, "in_pits": False}],
        "gap_ahead": 2.0, "gap_behind": 0.5,
        "in_pits": False, "session_type": "RACE",
        "yellow_flag_active": False, "full_course_yellow_active": False,
    }
    assert len(monitor._detect_overtakes(telemetry, time.monotonic())) == 0
```

**Definition of Done:**
- [ ] Adelantamiento completado → "Adelantamiento completado." (IMMEDIATE)
- [ ] Rebasado → "Te ha pasado un rival." (IMMEDIATE)
- [ ] No detecta bajo bandera amarilla/FCY
- [ ] No detecta si rival entra en boxes (no cuenta como adelantamiento)
- [ ] Cooldown 20s entre mensajes
- [ ] `pytest tests/test_overtake_wave1.py` pasa

**Riesgo:** BAJO. Datos disponibles. Algoritmo validado contra CC Position.cs.
**Estimación:** 4h

---

### F6 — LMU-30: Rain Realtime (Drizzle → Storm)

**Objetivo:** Detectar cambios en mRaining y emitir alertas por nivel de lluvia.

**Archivos:**
- `backend/src/intelligence/rain_monitor.py` — NUEVO: RainLevelMonitor
- `backend/src/intelligence/proactive_monitors.py` — Conectar rain_monitor
- `backend/tests/test_rain_wave1.py` — Tests

```python
# rain_monitor.py
from enum import IntEnum

class RainLevel(IntEnum):
    NONE = 0
    DRIZZLE = 1
    LIGHT = 2
    MID = 3
    HEAVY = 4
    STORM = 5

RAIN_THRESHOLDS = [
    (0.0, RainLevel.NONE),
    (0.01, RainLevel.DRIZZLE),
    (0.15, RainLevel.LIGHT),
    (0.3, RainLevel.MID),
    (0.6, RainLevel.HEAVY),
    (0.75, RainLevel.STORM),
]

RAIN_MESSAGES = {
    RainLevel.DRIZZLE: "Llovizna — vigila la pista.",
    RainLevel.LIGHT: "Lluvia ligera. Prepara intermedias.",
    RainLevel.MID: "Está lloviendo. Considera entrar a por lluvia.",
    RainLevel.HEAVY: "Lluvia intensa. Entra a por mojado.",
    RainLevel.STORM: "Diluvio. Máximo cuidado.",
}

class RainLevelMonitor:
    def __init__(self):
        self._last_level = RainLevel.NONE
        self._last_alert_at: float = 0.0
    
    def evaluate(self, raining: float, now: float) -> ImmediateAlert | None:
        level = self._classify(raining)
        if level == self._last_level:
            return None
        self._last_level = level
        if (now - self._last_alert_at) < 120.0:  # cooldown 120s
            return None
        self._last_alert_at = now
        if level == RainLevel.NONE and self._last_level != RainLevel.NONE:
            return ImmediateAlert("rain_stopped", "Dejó de llover. Pista secándose.", "MEDIUM", "rain")
        msg = RAIN_MESSAGES.get(level)
        if msg:
            priority = "HIGH" if level >= RainLevel.HEAVY else "MEDIUM"
            return ImmediateAlert(f"rain_{level.name.lower()}", msg, priority, "rain")
        return None
```

**Tests nuevos:** `test_rain_wave1.py`
```python
def test_rain_drizzle_detected():
    monitor = RainLevelMonitor()
    result = monitor.evaluate(0.05, time.monotonic())
    assert result is not None
    assert "Llovizna" in result.message

def test_rain_heavy_detected():
    monitor = RainLevelMonitor()
    monitor._last_level = RainLevel.LIGHT
    result = monitor.evaluate(0.65, time.monotonic())
    assert result is not None
    assert "Lluvia intensa" in result.message

def test_rain_no_change_no_alert():
    monitor = RainLevelMonitor()
    monitor._last_level = RainLevel.DRIZZLE
    result = monitor.evaluate(0.05, time.monotonic())  # mismo nivel
    assert result is None

def test_rain_cooldown_suppresses():
    monitor = RainLevelMonitor()
    monitor._last_alert_at = time.monotonic()  # just now
    result = monitor.evaluate(0.05, time.monotonic() + 1.0)
    assert result is None  # cooldown 120s no ha pasado
```

**Definition of Done:**
- [ ] Drizzle (0.01-0.15) → "Llovizna — vigila la pista." (IMMEDIATE)
- [ ] Heavy (0.6-0.75) → "Lluvia intensa. Entra a por mojado." (IMMEDIATE)
- [ ] Storm (>0.75) → "Diluvio. Máximo cuidado." (IMMEDIATE)
- [ ] Secándose → "Dejó de llover. Pista secándose." (IMMEDIATE)
- [ ] Cooldown 120s entre cambios
- [ ] `pytest tests/test_rain_wave1.py` pasa

**Riesgo:** BAJO. mRaining disponible a 20Hz.
**Estimación:** 2h

---

### F7 — Integración + Checklist + Regresión

**Objetivo:** Verificar que todas las fases F0-F6 funcionan juntas y pasan CI.

**Archivos:**
- `scripts/verify_audio_pipeline.py` — Añadir tests nuevos si aplica
- `scripts/verify_alpha_parity.py` — Añadir checks Wave 1

**Tests de regresión:**
```bash
# Tests existentes que deben seguir pasando:
python scripts/verify_audio_pipeline.py
python scripts/verify_alpha_parity.py
python scripts/verify_spotter_pipeline.py

# Tests nuevos Wave 1:
cd backend && python -m pytest tests/test_telemetry_wave1_fields.py -v
cd backend && python -m pytest tests/test_immediate_routing.py -v
cd backend && python -m pytest tests/test_damage_wave1.py -v
cd backend && python -m pytest tests/test_fcy_wave1.py -v
cd backend && python -m pytest tests/test_penalty_wave1.py -v
cd backend && python -m pytest tests/test_overtake_wave1.py -v
cd backend && python -m pytest tests/test_rain_wave1.py -v
```

**Checklist LMU manual** (W1-01 a W1-07 de cc-p0-wave1-locked.md Sección E):
| ID | Escenario | Pre | Post |
|----|-----------|-----|------|
| W1-01 | Golpear pared >40G → ¿"Estás bien"? | ☐ | ☐ |
| W1-02 | Pinchazo → ¿"Pinchazo {wheel}"? | ☐ | ☐ |
| W1-03 | Esperar SC → ¿fases pits_closed/open/green? | ☐ | ☐ |
| W1-04 | Cortar curva → ¿penalty countdown 3/2/1? | ☐ | ☐ |
| W1-05 | Adelantar rival → ¿"Adelantamiento"? | ☐ | ☐ |
| W1-06 | Inicio carrera → ¿race_start inmediato? | ☐ | ☐ |
| W1-07 | Lluvia variable → ¿niveles drizzle/storm? | ☐ | ☐ |

**Definition of Done:**
- [ ] Todos los tests de regresión pasan
- [ ] Todos los tests nuevos Wave 1 pasan
- [ ] Checklist LMU manual W1-01 a W1-07 marcados (al menos 5/7 PASS)

## 4. Orden de Merge Recomendado

| PR | Contenido | Depende de |
|----|-----------|-----------|
| PR-0 | F0: TelemetryFrame nuevos campos | Ninguno |
| PR-1 | F1: LMU-33 routing ImmediateAlert | PR-0 (usa engine.py) |
| PR-2 | F2: LMU-09 damage + puncture + crash | PR-0 (necesita campos telemetría) |
| PR-3 | F3: LMU-15 FCY phases | PR-0 (necesita yellow_flag_state) |
| PR-4 | F4: LMU-13 penalty countdown | PR-1 (usa ImmediateAlert) |
| PR-5 | F5: LMU-20 overtake detection | PR-1 (usa ImmediateAlert) |
| PR-6 | F6: LMU-30 rain monitor | PR-0 + PR-1 |
| PR-7 | F7: Integración + checklist final | PR-2 a PR-6 |

PR-2 y PR-3 pueden ir en paralelo (no comparten archivos). PR-4, PR-5, PR-6 también en paralelo.

## 5. Tests CI Obligatorios por Fase

```bash
# F0:
pytest tests/test_telemetry_wave1_fields.py -v --tb=short

# F1:
pytest tests/test_immediate_routing.py -v --tb=short
pytest tests/test_commentary_debounce.py -v --tb=short  # regresión

# F2:
pytest tests/test_damage_wave1.py -v --tb=short
pytest tests/test_spotter.py -v --tb=short -k "damage"  # regresión
pytest tests/test_fuel_safety.py -v --tb=short  # regresión

# F3:
pytest tests/test_fcy_wave1.py -v --tb=short
pytest tests/test_flags_monitor.py -v --tb=short  # regresión

# F4:
pytest tests/test_penalty_wave1.py -v --tb=short
pytest tests/test_triggers.py -v --tb=short -k "penalty"  # regresión

# F5:
pytest tests/test_overtake_wave1.py -v --tb=short
pytest tests/test_proactive_monitors.py -v --tb=short  # regresión

# F6:
pytest tests/test_rain_wave1.py -v --tb=short
pytest tests/test_triggers.py -v --tb=short -k "weather"  # regresión
```

## 6. Checklist LMU Manual (Wave 1)

Marcar en una sesión LMU real tras cada PR mergeado:

| ID | Escenario | Comportamiento esperado | PR | Pre | Post |
|----|-----------|------------------------|----|-----|------|
| W1-01 | Golpear pared >40G → detenido | "¿Estás bien?" tras 2s, 2do intento 8s, 3ero 16s | PR-2 | ☐ | ☐ |
| W1-02 | Pinchazo (mFlat) | "Pinchazo delantero izquierdo." delay 4-7s | PR-2 | ☐ | ☐ |
| W1-03 | Safety Car en carrera | "Pits cerrados" → "Pits abiertos" → "Última vuelta SC" → "Verde" | PR-3 | ☐ | ☐ |
| W1-04 | Cortar curva + penalización | Countdown 3/2/1 + "Entra a boxes ahora" en sector 3 | PR-4 | ☐ | ☐ |
| W1-05 | Adelantar rival | "Adelantamiento completado." (IMMEDIATE, cooldown 20s) | PR-5 | ☐ | ☐ |
| W1-06 | Inicio carrera inmediato | "Buena salida" como alert, no commentary batch | PR-1 | ☐ | ☐ |
| W1-07 | Lluvia variable (0→0.4→0) | "Llovizna" → "Está lloviendo" → "Dejó de llover" | PR-6 | ☐ | ☐ |

## 7. Fuera de Scope Wave 1 v1

- LMU-40 (FCY spotter cooldown) — Wave 2
- LMU-18 (tyre temp hot/cold por rueda) — Wave 2
- LMU-19 (push now best lap) — Wave 2
- LMU-28 (session end evaluation) — Wave 2
- LMU-45 (fuel persistence car/track) — Wave 2
- Engine/transmission damage — LMU NO tiene estos datos
- PitManager voz — Scope OUT alpha
- Brake wear REST en sidecar — POSTPONER
- mTrackLimitsSteps cut track — UNKNOWN, no implementar hasta verificar
- MQTT, overlays, grammar commands — Scope OUT

## 8. Riesgos y Mitigaciones (Top 5)

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|------------|---------|-----------|
| 1 | mYellowFlagState no cambia en LMU real | MEDIA | ALTO (F3 pierde subfases) | Fallback a solo gamePhase 6→5. Aún mejor que estado actual. Script de log para debug. |
| 2 | mFlat nunca es True en LMU (punctures no simuladas) | ALTA | ALTO (F2 pierde puncture) | Fallback a umbral mPressure < threshold. O aceptar que LMU no simula pinchazos. |
| 3 | mLocalAccel no fiable (ruido, valores extremos) | BAJA | MEDIO (F2 crash falsos +) | Threshold 40G es muy alto para falsos positivos. Si da falsos, subir a 50G. |
| 4 | mRaining no actualizado a 20Hz (solo cambios grandes) | BAJA | BAJO (F6 delay) | Aceptable. CC también tiene cooldown 120s entre cambios. |
| 5 | Sidecar brake_wear=0 rompe LMU-09 brakes en Tauri mode | MEDIA | BAJO | Wave 1 no depende de brake wear. TODO para Wave 2. |

## 9.1 Notas de implementación (binding — aplicadas en código)

### Dual-path daño (evitar doble voz)

| Evento | Canal | Frecuencia | Módulo |
|--------|-------|------------|--------|
| Impacto (dent/ET) | IMMEDIATE alert | 20 Hz | `spotter._eval_damage` |
| Pinchazo (`mFlat`) | IMMEDIATE alert | 20 Hz | `spotter._eval_puncture` |
| Crash >40G + retries | IMMEDIATE alert | 20 Hz | `spotter._eval_crash` |
| Daño acumulado (aero) | Commentary batch | 0.5 Hz | `proactive._eval_car_monitors` |
| Impacto edge | **NO** proactive | — | `_eval_impact_damage` eliminado de proactive |

### Penalties: una sola fuente

- `PenaltyTracker` vive en `penalty_tracker.py`, instanciado en `ProactiveMonitorSuite`.
- `PenaltyMonitorTrigger` desactivado (`condition` → `False`) para evitar duplicados con proactive @ 0.5 Hz.
- Sector para "pit now": leer `current_sector` desde `mSector` (LMU: 0=sector3 → `lmu_sector_number()==3`).

### FCY: determinista + fallback

- Transiciones por `yellow_flag_state` (2/4/5/6) en `flags_monitor.py` → `ImmediateAlert` vía proactive.
- Spotter @ 20 Hz repite fases FCY para latencia mínima (`_eval_fcy_phases`).
- Si `mYellowFlagState` no cambia: fallback `gamePhase` 5↔6 en `detect_flag_transitions`.

### `audio_priority` en AlertMessage

Usar `str(Priority[evt.priority].value)` — valores `"4"`/`"3"`/`"2"`/`"1"`, alineado con spotter.

### `mYellowFlagState` (`c_char`)

```python
def parse_yellow_flag_state(raw) -> int:
    if isinstance(raw, (bytes, bytearray)):
        return int(raw[0]) if raw else 0
    if isinstance(raw, str):
        return ord(raw[0]) if raw else 0
    return int(raw or 0)
```

### `mLocalAccel` fuente

Leer desde `player_tele.mLocalAccel` (telemetría jugador), no scoring.

### Campos F0 adicionales

- `current_sector: int = 0` — `mSector` en scoring jugador (necesario F4 pit-now).

## 9. Criterio "Wave 1 v1 DONE"

- [ ] Las 7 fases (F0 a F7) implementadas y mergeadas
- [ ] Todos los tests CI listados en Sección 5 pasan
- [ ] Checklist LMU manual (W1-01 a W1-07): mínimo 5/7 marcados como PASS
- [ ] Ningún test de regresión existente se ha roto
- [ ] No hay funcionalidad fuera de scope implementada
- [ ] El piloto puede completar una carrera en LMU y escuchar:
  - Daño al golpear (impacto, pinchazo, crash)
  - Fases del SC (pits cerrados/abiertos/verde)
  - Countdown de penalización (3/2/1/pit now)
  - Adelantamientos
  - Eventos inmediatos (no batch delay)
  - Cambios de lluvia en tiempo real
