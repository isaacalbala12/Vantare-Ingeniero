---
generated: 2026-06-07
sources: [Vantare: strategy_service.py, strategy_runner.py, flags_monitor.py, damage_report.py, proactive_monitors.py, spotter_adapter.py, engine.py, triggers.py; LMU: shared-memory.md, lmu_data.py, rest-api.md; CC: DamageReporting.cs, Position.cs, Penalties.cs, FlagsMonitor.cs, ConditionsMonitor.cs]
scope: gap-closure for Wave 1 implementation
---

# Gap Closure: Wave 1 — Correcciones al Análisis Previo

## A. Resumen Ejecutivo

Se cerraron 7 de 9 gaps identificados. 2 quedan PARTIAL (mTrackLimitsSteps UNKNOWN, sidecar REST brakes). El riesgo global Wave 1 es BAJO: todos los P0 elegidos tienen datos LMU verificados y la mayoría no requiere datos nuevos en TelemetryFrame. LMU-09 se rescata de "5 componentes" a "daño LMU real (dent + puncture + crash + REST brakes)". LMU-33 se resuelve con un nuevo tipo `ImmediateAlert` que bifurca el routing en engine.py.

## B. Tabla GAP → Resolución

| GAP | Estado | Decisión | Evidencia | Impacto plan |
|-----|--------|----------|-----------|-------------|
| 1. LMU-09 multicomponente sobredimensionado | **CLOSED** | Rescope a: impacto (dent severity) + puncture (mFlat) + crash (mLocalAccel) + REST brakes/susp. NO engine/tranny damage | `lmu_data.py` NO tiene engine/transmission damage. `DamageReporting.cs` usa datos que LMU no expone | Reduce estimación LMU-09 de 3d a 1.5d |
| 2. Telemetría no cableada (mRaining, mYellowFlagState, mFlat, mLocalAccel) | **CLOSED** | Añadir 5 campos a TelemetryFrame + leer en strategy_service y strategy_runner | `strategy_service.py:240-285` verifica NO se leen hoy | F0 añade ~2h de trabajo |
| 3. LMU-33 subestima engine.py | **CLOSED** | Crear tipo `ImmediateAlert` + bifurcar routing en _run_proactive_monitors | `proactive_monitors.py:evaluate()` retorna TODO como CommentaryEvent → batch | F1 estimado 3h |
| 4. LMU-20 algoritmo ambiguo | **CLOSED** | Pseudocódigo CC Position.cs traducido a Vantare (gap+opponent key, no solo mPlace delta) | `Position.cs:checkForNewOvertakes()` verificado | F5 estimado 4h |
| 5. LMU-13 countdown sintético | **CLOSED** | PenaltyTracker state machine: al subir mNumPenalties → iniciar conteo 3/2/1/pit_now. "3 vueltas" es convención Vantare (CC usa 3 laps para DT/SG) | `Penalties.cs:triggerInternal()` confirma 3-lap countdown | F4 estimado 3h |
| 6. mYellowFlagState runtime validation | **CLOSED** | Plan de verificación + tabla mapping provisional. Si falla en pista, fallback a mGamePhase==6 sin subfases | `lmu_data.py:LMUScoringInfo.mYellowFlagState` línea 301 (c_char) | No bloquea implementación |
| 7. Sidecar vs backend paridad | **PARTIAL** | Brake wear REST solo en backend. Sidecar NO tiene REST brakes = brake_wear 0.0. Wave 1 features: LMU-15/13/20/30/33 NO requieren REST. LMU-09 brakes solo en backend path | `strategy_runner.py:170-174` brake_wear hardcodeado a 0.0 | No bloquea Wave 1; añadir TODO para sidecar REST |
| 8. Orden de implementación | **CLOSED** | F0 (telemetría) → F1 (routing) → F2 (LMU-09) → F3 (LMU-15) → F4 (LMU-13) → F5 (LMU-20) → F6 (LMU-30) → F7 (integración) | Dependencias explícitas en Sección I | Plan v1 mueve LMU-30 al final por requerir rain_monitor.py nuevo |
| 9. Typos en plantillas | **CLOSED** | "平衡" → "balance" en cc-message-templates-p0.md:29. LMU-09 renombrado a "Daño LMU-parcial + puncture + crash" | Ver línea exacta | Fix en F2 |

## C. LMU-09 Rescoped (mensajes reales según datos LMU)

```yaml
lm09_messages:
  - id: impact_severity
    fuente_dato: mDentSeverity[8] (0-2) + mLastImpactMagnitude > 25
    canal: alert IMMEDIATE
    edge_once: true (por nivel)
    cooldown: 3s (timeToWaitForDamageToSettle)
    condicion_vantare: |
      if last_impact_et != _last_impact_et and magnitude >= 25:
        severity = classify_damage_severity({dent_max, dent_avg, detached})
        emit(severity)
    plantillas:
      - severity=grave (dent_max>=2 OR dent_avg>=1.2 OR detached):
          "Golpe fuerte. Daño grave en el frontal."
      - severity=moderado (dent_max>=1 OR dent_avg>=0.5):
          "Impacto notable. Daño moderado — revisa el balance del coche."
      - severity=leve:
          "Toque detectado. Daños leves."
    notas: |
      NO hay engine/transmission damage en LMU. 
      mDentSeverity[8] = 8 ubicaciones carrocería, no componentes.
      Ya implementado parcialmente en damage_report.py:classify_damage_severity.

  - id: puncture_FL/FR/RL/RR
    fuente_dato: mWheels[i].mFlat (c_bool) — LMU directo
    fallback: mWheels[i].mPressure < threshold_kPa (si mFlat no fiable)
    canal: alert IMMEDIATE priority 4
    edge_once: true (por rueda, resetea al cambiar rueda)
    delay: 4-7s (style CC DamageReporting.cs)
    plantillas:
      - i=0 (FL): "Pinchazo delantero izquierdo."
      - i=1 (FR): "Pinchazo delantero derecho."
      - i=2 (RL): "Pinchazo trasero izquierdo."
      - i=3 (RR): "Pinchazo trasero derecho."
    notas: |
      LMU expone mFlat como c_bool. CC usa umbral de presión 30 (aprox 5psi).
      Vantare: usar mFlat primero. Si no funciona en pista, caer a mPressure < threshold.

  - id: crash_are_you_ok
    fuente_dato: mLocalAccel magnitud > 392 m/s² (40G)
    canal: alert IMMEDIATE priority 4
    retries:
      - t=0s:  "¿Estás bien? ¿Estás bien?"
      - t=8s:  "¿Cómo estás? Responde."
      - t=16s: "No contestas. Entra en boxes si puedes."
    cancel_si: in_pits transitions a true (entra a boxes voluntariamente)
    notas: |
      CC DamageReporting.cs: acceleration > 400 m/s² O > 270 (ACC).
      LMU mLocalAccel es LMUVect3 (x,y,z) en m/s². Magnitud = sqrt(x²+y²+z²).
      Si speed tras impacto < 3 m/s → asumir detenido, iniciar retries.
      Si speed > 3 m/s → esperar 3s, si no acelera → asumir dañado, iniciar.

  - id: REST_brakes_wear  # SOLO backend path
    fuente_dato: lmu_api.get_additional_data("brakes") → [0.0-1.0] x4
    canal: alert NORMAL (no crítico inmediato)
    disponibles: backend SI, sidecar NO (brake_wear=0.0 en sidecar)
    notas: |
      Ya cableado en strategy_service.py:366-395.
      sidecar/strategy_runner.py:170-174 tiene brake_wear=0.0 hardcodeado.
      No crítico para Wave 1 (LMU-09 no depende de brake wear).

  - id: REST_suspension_wear  # SOLO backend path
    fuente_dato: lmu_api.get_additional_data("garage_wear") → wearables.suspension[4]
    canal: alert NORMAL
    disponibles: backend SI, sidecar NO
    notas: |
      No cableado actualmente. Requiere añadir parse en strategy_service.py.
      POSTPONER a Wave 2 (no crítico, LMU no expone suspension damage en shared mem).
```

## D. Telemetría — Diff Spec (campos nuevos en TelemetryFrame)

| field | lmu_source | type | default | wired in strategy_service? | wired in strategy_runner? | wired in TelemetryFrame? |
|-------|-----------|------|---------|--------------------------|-------------------------|-------------------------|
| `raining_intensity` | `LMUScoringInfo.mRaining` | float (0.0-1.0) | 0.0 | ❌ NO (línea 240-246 no lo lee) | ❌ NO | ❌ NO (nuevo campo) |
| `yellow_flag_state` | `LMUScoringInfo.mYellowFlagState` | int (-1..7) | 0 | ❌ NO | ❌ NO | ❌ NO (nuevo campo) |
| `tyre_flat_FL` | `LMUWheel[0].mFlat` | bool | False | ❌ NO (no se leen wheels) | ❌ NO | ❌ NO |
| `tyre_flat_FR` | `LMUWheel[1].mFlat` | bool | False | ❌ NO | ❌ NO | ❌ NO |
| `tyre_flat_RL` | `LMUWheel[2].mFlat` | bool | False | ❌ NO | ❌ NO | ❌ NO |
| `tyre_flat_RR` | `LMUWheel[3].mFlat` | bool | False | ❌ NO | ❌ NO | ❌ NO |
| `local_accel_x` | `mLocalAccel.x` | float | 0.0 | ❌ NO | ❌ NO | ❌ NO |
| `local_accel_y` | `mLocalAccel.y` | float | 0.0 | ❌ NO | ❌ NO | ❌ NO |
| `local_accel_z` | `mLocalAccel.z` | float | 0.0 | ❌ NO | ❌ NO | ❌ NO |
| `track_limits_steps` | `mTrackLimitsSteps` | uint8 | 0 | ❌ NO | ❌ NO | ❌ NO (UNKNOWN utility) |

**Bloques de código a insertar:**

En `strategy_service.py:_process_cycle()`, dentro del bloque `if not self.reader.offline and self.reader.shmm and self.reader.shmm.data:` (línea 225), tras la línea 246 (has_sector_yellow):

```python
# --- NUEVOS CAMPOS WAVE 1 ---
# mRaining (LMU-30): intensidad lluvia en tiempo real
rainfall = safe_float(scoring_info.mRaining)

# mYellowFlagState (LMU-15): fase FCY
yellow_flag_state = int(scoring_info.mYellowFlagState)

# mLocalAccel (LMU-09 crash G): solo player_scor tiene accel
local_accel_x = safe_float(player_scor.mLocalAccel.x) if player_scor else 0.0
local_accel_y = safe_float(player_scor.mLocalAccel.y) if player_scor else 0.0
local_accel_z = safe_float(player_scor.mLocalAccel.z) if player_scor else 0.0

# mFlat (LMU-09 puncture): desde telemetría del jugador
tyre_flat = [False, False, False, False]
if player_tele is not None:
    for i in range(4):
        tyre_flat[i] = bool(player_tele.mWheels[i].mFlat)

# mTrackLimitsSteps (LMU-13 cut track, UNKNOWN)
track_limits_steps = int(player_tele.mTrackLimitsSteps) if player_tele else 0
```

Luego añadir al `TelemetryFrame(...)` (línea 474+):

```python
raining_intensity=rainfall,
yellow_flag_state=yellow_flag_state,
local_accel_x=local_accel_x,
local_accel_y=local_accel_y,
local_accel_z=local_accel_z,
tyre_flat_fl=tyre_flat[0],
tyre_flat_fr=tyre_flat[1],
tyre_flat_rl=tyre_flat[2],
tyre_flat_rr=tyre_flat[3],
track_limits_steps=track_limits_steps,
```

**Mismos cambios en `sidecar/src/sidecar/strategy_runner.py`** duplicar en `process_cycle()`.

## E. LMU-33 — Diseño de Routing (ImmediateAlert vs CommentaryEvent)

### Diagrama de flujo

```
proactive_monitors.evaluate()
│
├── event_id in IMMEDIATE_EVENTS set?
│   ├── SI → devolver ImmediateAlert (no CommentaryEvent)
│   └── NO → devolver CommentaryEvent (tupla, batch)
│
engine._run_proactive_monitors()
│
├── ImmediateAlert → AlertMessage → broadcast_sync() (canal IMMEDIATE)
│
└── CommentaryEvent → enqueue_commentary() → batch → commentary_end
```

### Tipo Python

```python
# En proactive_monitors.py o nuevo archivo
@dataclass
class ImmediateAlert:
    """Alerta que DEBE emitirse como IMMEDIATE, no pasar por commentary batch."""
    event_id: str
    message: str
    priority: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    category: str  # "safety_car" | "damage" | "penalty" | "overtake" | "rain" | "race"
    payload: dict = field(default_factory=dict)


IMMEDIATE_EVENTS: set[str] = {
    "race_start",
    "flags_yellow",     # SC/FCY start
    "flags_safety_car",
    "damage",           # impacto severo
    "penalties",        # pit_now
    "overtake",
    "rain_drizzle",
    "rain_light",
    "rain_heavy",
}
```

### Refactor de `_run_proactive_monitors`

```python
async def _run_proactive_monitors(self, telemetry_dict, strategy_dict, session_dict):
    events = self.proactive_monitors.evaluate(
        telemetry_dict, strategy_dict, session_dict,
        history_store=self._get_history_store(),
        strategy_service=self._get_strategy_service(),
    )
    for evt in events:
        if isinstance(evt, ImmediateAlert):
            # Canal IMMEDIATE — bypass batch
            alert = AlertMessage(
                event="alert",
                alert_id=str(uuid.uuid4()),
                category=evt.category,
                message=evt.message,
                audio_priority=str(Priority[evt.priority].value),
                payload={"severity": evt.priority, **evt.payload},
            )
            self.broadcaster.send(alert)
        else:
            # Canal NORMAL — commentary batch
            event_id, summary, priority = evt
            self.enqueue_commentary(event_id, summary, priority)
```

## F. LMU-20 — Pseudocódigo Overtake Detector

**Inputs necesarios:** `competitors` list (con standing_position, driver_index, driver_name, in_pits, lap_valid), `gap_ahead`, `gap_behind`, `session_phase`, `lap_number`, `yellow_flag_active`

**Estado persistente por sesión:**
```python
_last_opponent_ahead_key: str | None = None
_gap_samples_ahead: list[float] = []     # sliding window, ~100 samples a 0.5Hz
_last_overtake_at: float = 0.0            # cooldown 20s
_last_being_overtaken_at: float = 0.0
_complaints_count: int = 0                # max 60/sesión
```

**Pseudocódigo:**
```python
def _detect_overtakes(self, telemetry: dict, now: float) -> list[ImmediateAlert]:
    alerts: list[ImmediateAlert] = []
    
    # Gates: solo race, no pits, no yellow
    if not self._is_race_phase(telemetry.get("session_phase", "")):
        return alerts
    if telemetry.get("in_pits", False):
        return alerts
    if telemetry.get("yellow_flag_active", False) or telemetry.get("full_course_yellow_active", False):
        return alerts
    
    competitors = telemetry.get("competitors", [])
    if not competitors:
        return alerts
    
    my_position = int(telemetry.get("standing_position", 1))
    
    # Encontrar oponente delante (siguiente posición)
    comp_ahead = min(
        (c for c in competitors if int(c.get("standing_position", 99)) < my_position and not c.get("in_pits", False)),
        key=lambda c: abs(int(c.get("standing_position", 99)) - my_position),
        default=None
    )
    current_key_ahead = str(comp_ahead.get("driver_index", -1)) if comp_ahead else None
    
    # Encontrar oponente detrás
    comp_behind = min(
        (c for c in competitors if int(c.get("standing_position", 99)) > my_position and not c.get("in_pits", False)),
        key=lambda c: abs(int(c.get("standing_position", 99)) - my_position),
        default=None
    )
    current_key_behind = str(comp_behind.get("driver_index", -1)) if comp_behind else None
    
    # Muestrear gap
    gap_ahead = float(telemetry.get("gap_ahead", 99.0))
    gap_behind = float(telemetry.get("gap_behind", 99.0))
    self._gap_samples_ahead.append(gap_ahead)
    if len(self._gap_samples_ahead) > 100:
        self._gap_samples_ahead.pop(0)
    
    # DETECTAR ADELANTAMIENTO: cambia el coche delante
    if (current_key_ahead != self._last_opponent_ahead_key 
        and self._last_opponent_ahead_key is not None
        and current_key_ahead is not None
        and (now - self._last_overtake_at) >= 20.0):
        
        # Verificar: el anterior rival ahora está detrás
        if comp_behind and str(comp_behind.get("driver_index", -1)) == self._last_opponent_ahead_key:
            # Confirmar que no es por DNF/boxes
            if comp_ahead and not comp_ahead.get("in_pits", False):
                gap_mean = sum(self._gap_samples_ahead[-20:]) / max(1, len(self._gap_samples_ahead[-20:]))
                if gap_mean > 0.15:  # minTimeDeltaForPass style CC
                    name = comp_ahead.get("driver_name", "")
                    alerts.append(ImmediateAlert(
                        event_id="overtake",
                        message=f"Adelantamiento completado.",
                        priority="MEDIUM",
                        category="overtake",
                        payload={"driver_name": name, "position": my_position},
                    ))
                    self._last_overtake_at = now
    
    # DETECTAR REBASAMIENTO: cambia el coche detrás y el anterior está delante
    if (current_key_behind != self._last_key_behind
        and self._last_key_behind is not None
        and current_key_behind is not None
        and (now - self._last_being_overtaken_at) >= 20.0):
        
        if comp_ahead and str(comp_ahead.get("driver_index", -1)) == self._last_key_behind:
            if self._complaints_count < 60:  # maxComplaintsPerSession
                name = comp_behind.get("driver_name", "")
                alerts.append(ImmediateAlert(
                    event_id="being_overtaken",
                    message=f"Te ha pasado un rival.",
                    priority="HIGH" if my_position <= 5 else "MEDIUM",
                    category="overtake",
                    payload={"driver_name": name, "position": my_position},
                ))
                self._last_being_overtaken_at = now
                self._complaints_count += 1
    
    self._last_opponent_ahead_key = current_key_ahead
    self._last_key_behind = current_key_behind
    return alerts
```

## G. LMU-13 — PenaltyTracker State Machine

### Diagrama de estados

```
         ┌──────────────────────────────────────────────────┐
         │                                                  │
         v                                                  │
   ┌─────────┐   mNumPenalties++    ┌────────────┐         │
   │  CLEAR  │ ──────────────────► │ COUNTDOWN  │         │
   │ (sin    │                     │ (3 vueltas │         │
   │  pen)   │ ◄───────────────── │  restantes)│         │
   └─────────┘   mNumPenalties==0    └─────┬──────┘         │
         ^                                 │                │
         │           ┌──────────────┐      │                │
         │           │  PIT_NOW     │ ◄────┤ sector 3       │
         │           │  (sector 3)  │      │ lap-penLap==2  │
         │           └──────┬───────┘      │                │
         │                  │              │                │
         │         mNumPenalties baja      │                │
         │           (penalizó servida)    │                │
         └─────────────────────────────────┘                │
                                                            │
         Si numPenalties > 0 por > 3 vueltas               │
         → DISQUALIFIED                                     │
                                                            └──
```

### Tabla de transiciones

| Estado actual | Evento | Sgte estado | Mensaje TTS | Condición extra |
|---|---|---|---|---|
| CLEAR | `numPenalties` sube | COUNTDOWN | "Penalización asignada. Tienes 3 vueltas para entrar en boxes." | Iniciar `_penalty_lap = current_lap` |
| COUNTDOWN | Nueva vuelta y `lap - penLap == 3` | COUNTDOWN | — | No repetir, ya avisado al inicio |
| COUNTDOWN | Nueva vuelta y `lap - penLap == 2` | COUNTDOWN | "2 vueltas. Tienes que entrar." | Si no `in_pits` |
| COUNTDOWN | Nueva vuelta y `lap - penLap == 1` | COUNTDOWN | "1 vuelta. Entra ahora o serás descalificado." | Si no `in_pits` |
| COUNTDOWN | `sector == 3` y `lap - penLap == 2` | PIT_NOW | "Entra a boxes ahora." | Una vez |
| COUNTDOWN | `numPenalties` baja (servida en pits) | CLEAR | "Penalización cumplida. Buen trabajo." | — |
| PIT_NOW | `numPenalties` baja | CLEAR | "Penalización cumplida." | — |
| CUALQUIERA | `numPenalties` sube otra vez | COUNTDOWN | "Nueva penalización asignada." | Reiniciar `_penalty_lap` |
| COUNTDOWN | `lap - penLap > 3` y `numPenalties > 0` | DISQUALIFIED | "No has servido la penalización. Vas a ser descalificado." | Una vez |
| CUALQUIERA | `in_pits` y sale con `numPenalties > 0` | COUNTDOWN | "No has servido la penalización." | Cooldown 1 vez por stint |

**Nota sobre "3 vueltas":** CC usa 3 laps como estándar para drive-through y stop-go en la mayoría de simuladores. LMU puede tener reglas distintas, pero CC no conoce las reglas de cada título — usa 3 laps como convención. Vantare hace lo mismo. Si LMU da menos o más vueltas, el piloto escuchará "3 vueltas" pero la descalificación real llegará cuando LMU lo decida (no cuando Vantare lo diga).

## H. mYellowFlagState — Plan de Verificación

### Cómo validar en LMU

```python
# Script temporal para loguear mYellowFlagState durante sesión LMU
# Insertar en strategy_service.py:_process_cycle(), tras línea 240:
logger.info(
    "FCY DEBUG: gamePhase=%d yellowFlagState=%d sectorFlags=[%d,%d,%d]",
    scoring_info.mGamePhase,
    scoring_info.mYellowFlagState,
    scoring_info.mSectorFlag[0],
    scoring_info.mSectorFlag[1],
    scoring_info.mSectorFlag[2],
)
```

1. Iniciar sesión LMU sin SC → verificar `yellowFlagState=0`
2. Provocar SC (choque múltiple) o esperar SC automático
3. Observar log: `yellowFlagState` debe cambiar a 2 (pits closed), luego 4 (pits open), luego 5 (last lap), luego 6 (resume), luego 0 (racing)
4. Si no hay cambios → `mYellowFlagState` no funciona en LMU → fallback a solo `mGamePhase == 6`

### Mapping provisional (basado en lmu_data.py docs)

| mYellowFlagState | Fase CC | Mensaje TTS Vantare |
|---|---|---|
| -1 | Invalid | — (ignorar) |
| 0 | None (racing) | — |
| 1 | Pending | (esperar, no anunciar) |
| 2 | Pits closed | "Safety Car desplegado. Pits cerrados." |
| 3 | Pit lead lap | (solo coches líder, no anunciar) |
| 4 | Pits open | "Pits abiertos." |
| 5 | Last lap | "Última vuelta de Safety Car." |
| 6 | Resume | "Prepárate para relanzamiento." |
| 7 | Race halt | — (raro, no anunciar) |

### Fallback si mYellowFlagState no funciona

Si en LMU real `mYellowFlagState` no cambia (siempre 0), implementar solo con `mGamePhase`:
- `gamePhase == 6` → "Safety Car desplegado. Pits cerrados."
- `gamePhase 6 → 5` → "Bandera verde. A tope."

Las subfases (pits open, last lap, resume) se omiten. Aún así mejor que el estado actual (solo 1 mensaje "SC activo").

## I. Sidecar vs Backend Matrix

| Feature | Backend | Sidecar | Acción |
|---------|---------|---------|--------|
| LMU-09: impact severity | ✅ mDentSeverity via damage_fields | ✅ idem (duplicado en strategy_runner) | Ninguna |
| LMU-09: puncture mFlat | ❌ No leído hoy | ❌ No leído hoy | Añadir en F0 (ambos) |
| LMU-09: crash mLocalAccel | ❌ No leído hoy | ❌ No leído hoy | Añadir en F0 (ambos) |
| LMU-09: brake wear REST | ✅ strategy_service lee REST cada 3s | ❌ brake_wear=0 hardcodeado | POSTPONER Wave 2 |
| LMU-09: suspension REST | ⚠️ No parseado hoy | ❌ No disponible | POSTPONER Wave 2 |
| LMU-15: mYellowFlagState | ❌ No leído hoy | ❌ No leído hoy | Añadir en F0 (ambos) |
| LMU-15: mGamePhase==6 | ✅ Ya leído | ✅ Ya leído | Ninguna |
| LMU-13: mNumPenalties | ✅ Ya leído | ✅ Ya leído | Ninguna |
| LMU-20: competitors list | ✅ Ya leído | ✅ Ya leído | Ninguna |
| LMU-30: mRaining | ❌ No leído hoy | ❌ No leído hoy | Añadir en F0 (ambos) |
| LMU-33: routing | ⚠️ Todo va a batch | N/A (no genera commentary) | F1 solo backend |
| cut track: mTrackLimitsSteps | ❌ No leído hoy | ❌ No leído hoy | UNKNOWN, posponer |

**Conclusión:** Los 6 features Wave 1 funcionan en el path backend. El sidecar necesita los mismos campos nuevos de telemetría. Brake wear REST es el único gap backend vs sidecar y no afecta Wave 1.
