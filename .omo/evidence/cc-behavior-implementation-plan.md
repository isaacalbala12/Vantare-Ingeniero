# Plan de Implementación — Paridad Conductual CC → Vantare

**Basado en:** `.omo/evidence/cc-behavior-parity-matrix.yaml` + `.omo/evidence/cc-behavior-parity-matrix.md`

---

## Fase P0 — Bugs / Gaps Críticos (Orden de Implementación)

### 1. LMU-09: Daño Multicomponente + Puncture + Crash "Are You OK"

**Archivos a tocar:**
- `backend/src/intelligence/damage_report.py` — Refactor mayor
- `backend/src/intelligence/lmu_damage.py` — Verificar datos disponibles
- `backend/src/intelligence/spotter.py` — Extender `_eval_damage`
- `backend/src/intelligence/proactive_monitors.py` — Extender `_eval_car_monitors` + `_eval_impact_damage`
- `backend/src/intelligence/triggers.py` — Añadir damage trigger opcional
- `backend/tests/test_spotter.py` — Nuevos tests

**Cambio:**
```
1. damage_report.py → 5 componentes (engine, tranny, aero, suspension, brakes) 
   con 4 niveles (NONE, TRIVIAL, MINOR, MAJOR/DESTROYED) style DamageReporting.cs
2. Añadir puncture detection: tyre_pressure < threshold (30) → "pinchazo LF/RF/LR/RR"
3. Añadir crash detection: deceleración > 40G (400 m/s²) → "are you OK?" + follow-up
4. Edge-once por nivel de daño (no solo primer impacto)
5. Mensaje inmediato (alert IMMEDIATE) para daño severo/destroyed, batch para menor
```

**Dependencias:** `lmu_damage.py` debe exponer damage desglosado
**Riesgo:** Datos LMU pueden no tener presión ruedas o deceleración
**Tests:** `test_damage_multi_component`, `test_puncture_detection`, `test_crash_40g`

---

### 2. LMU-15: Flags FCY Ciclo Completo

**Archivos a tocar:**
- `backend/src/intelligence/flags_monitor.py` — Añadir FCY phase tracking
- `backend/src/intelligence/spotter.py` — Extender `_eval_safety_car`
- `backend/src/intelligence/triggers.py` — Ajustar FlagsMonitorTrigger
- `backend/tests/test_flags_fcy.py` — Nuevo test

**Cambio:**
```
1. flags_monitor.py → FlagSnapshot añadir fcy_phase (RACING/PITS_CLOSED/PITS_OPEN/GREEN)
2. detect_flag_transitions → emitir eventos por fase FCY
3. spotter._eval_safety_car → edge-once por activación + desactivación (green transition)
4. Mensaje inmediato para cada fase:
   - "SC ACTIVO → Pits cerrados"
   - "Pits abiertos" 
   - "Última vuelta SC"
   - "Bandera verde — a tope"
5. cooldown entre fase: configurable (default 25s)
```

**Dependencias:** flags_monitor.py ya tiene estructura base
**Riesgo:** Medio — requiere probar ciclo FCY real en LMU
**Tests:** `test_fcy_phase_sequence`, `test_sc_green_transition`

---

### 3. LMU-13: Penalización con Conteo Regresivo

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Extender PenaltyMonitorTrigger
- `backend/src/intelligence/penalty_tracker.py` — Nuevo archivo (o en triggers.py)
- `backend/src/models/messages.py` — Verificar campos penalty
- `backend/tests/test_penalty_countdown.py` — Nuevo test

**Cambio:**
```
1. PenaltyMonitorTrigger → hacer ALERT_ONLY con múltiples mensajes:
   - Nueva penalización: "Penalización asignada — {tipo}. Debes entrar en 3 vueltas."
   - 3 vueltas restantes → notificar
   - 2 vueltas restantes → "2 vueltas para servir penalización"
   - 1 vuelta restante → "1 vuelta, tienes que entrar"
   - Pit now en sector 3: "Entra a boxes ahora para servir penalización"
   - Servida: "Penalización cumplida"
   - No servida tras tiempo: "No has servido la penalización — posible descalificación"
2. Añadir tipos de penalización si LMU los expone:
   - Drive-through / Stop & Go / Slow down / Time penalty
3. Cut track warnings con frecuencia 30s (4 niveles: OK→minor→excessive→taking piss)
```

**Dependencias:** Datos LMU REST o shared memory para penalizaciones específicas
**Riesgo:** Puede que LMU solo exponga `num_penalties` genérico
**Tests:** `test_penalty_countdown_3_2_1`, `test_penalty_not_served`, `test_cut_track_warning`

---

### 4. LMU-20: Adelantamientos y Rebasamientos

**Archivos a tocar:**
- `backend/src/intelligence/proactive_monitors.py` — Extender con overtake detection
- `backend/src/intelligence/overtake_detector.py` — Nuevo archivo (o en proactive_monitors)
- `backend/tests/test_overtake_detection.py` — Nuevo test

**Cambio:**
```
1. Implementar overtake detector style Position.cs:
   - Guardar opponentKey delante/detrás
   - Muestrear gap_ahead/gap_behind (pas check interval 1s)
   - Cuando opponentKey cambia y gap > minTimeDeltaForPass (0.15s):
     "Adelantamiento completado a {driver_name}" / "Te ha pasado {driver_name}"
   - Verificar: no penalización en curso, no pits, no yellow, lap válida
   - Cooldown 20s entre mensajes
2. Mensaje inmediato (alert IMMEDIATE), no commentary batch
```

**Dependencias:** `driver_names.py` para nombre rival
**Riesgo:** Bajo — gap_ahead/gap_behind ya disponibles
**Tests:** `test_overtake_detected`, `test_being_overtaken`, `test_overtake_cooldown`

---

### 5. LMU-30: Lluvia en Tiempo Real

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Dividir WeatherChangeTrigger
- `backend/src/intelligence/weather_monitor.py` — Nuevo archivo
- `backend/src/intelligence/flags_monitor.py` — Reutilizar patrón
- `backend/tests/test_weather_realtime.py` — Nuevo test

**Cambio:**
```
1. Crear RainMonitor (no LLM) para detectar cambios de rain_density en telemetría:
   - Niveles: DRIZZLE (<0.15), LIGHT (<0.3), MID (<0.6), HEAVY (<0.75), STORM
   - Edge-once por nivel ascendente/descendente
   - Mensaje inmediato: "Lluvia ligera aumentando" / "Dejó de llover"
   - Cooldown 120s (RF2) o 10s (otros)
2. WeatherChangeTrigger → mantener para forecast LLM (complementario, no sustituto)
```

**Dependencias:** LMU shared memory debe exponer rain_density
**Riesgo:** Puede que LMU solo tenga forecast, no rain real-time
**Tests:** `test_rain_level_transition`, `test_rain_stopped`

---

### 6. LMU-18: Temperatura Neumáticos por Rueda

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Extender TiresThermalOverheatingTrigger
- `backend/tests/test_tyre_temp_specific.py` — Nuevo test

**Cambio:**
```
1. TiresThermalOverheatingTrigger → 3 niveles por rueda:
   - Cold (<60°C): "Neumáticos fríos"
   - Hot (>100°C): "Temperatura alta neumático {rueda}"
   - Cooking (>120°C): "Neumático {rueda} sobrecalentado"
2. Mensaje específico si solo un eje o rueda específica
3. MINOR = 100-120°C, MAJOR = 120°C+ (equivalente damage level)
4. Mantener LLM_REQUIRED para consejo, ALERT_ONLY para urgencia
```

**Dependencias:** tyre_temp_FL/FR/RL/RR ya disponibles
**Riesgo:** Bajo
**Tests:** `test_tyre_temp_cold_front`, `test_tyre_temp_cooking_left_rear`

---

### 7. LMU-19: Push Now con Cálculo Best Lap

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Refactor PushNowTrigger
- `shared-strategy/src/shared_strategy/models.py` — Verificar opponent_best_lap
- `backend/tests/test_push_now_bestlap.py` — Nuevo test

**Cambio:**
```
1. PushNowTrigger → calcular si merece la pena empujar:
   - opponent_best_lap - player_best_lap = diferencia por vuelta
   - diferencia * laps_remaining > gap_ahead → alcanzable ("push to win/P2/P3/improve")
   - player_best_lap - opponent_behind_best_lap * laps > gap_behind → defender ("push to hold")
2. Mensajes específicos según objetivo:
   - "Empuja para ganar" (P2, gap alcanzable)
   - "Empuja para defender" (rival alcanzándote)
   - "Empuja para mejorar" (P5, gap alcanzable a P4)
3. Mantener LLM_REQUIRED para rich advice
```

**Dependencias:** opponent best lap data en shared-strategy
**Riesgo:** Medio — requiere opponent best lap en telemetría
**Tests:** `test_push_now_win_calculable`, `test_push_now_hold`, `test_push_now_not_possible`

---

### 8. LMU-25: Driver Swap Stint Countdown

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Extender DriverSwapTrigger
- `backend/tests/test_driver_swap_countdown.py` — Nuevo test

**Cambio:**
```
1. DriverSwapTrigger → detectar driver_stint_seconds_remaining de telemetría:
   - Si datos disponibles: mensajes en 15/10/5/2 minutos restantes
   - "Pit this lap for driver change" cuando restante < best_lap + 30s
   - Recordatorio en sector 3: "Box now for driver change"
2. Mantener nombre change detection actual
```

**Dependencias:** LMU debe exponer driver_stint_seconds_remaining
**Riesgo:** Alto — puede que LMU no tenga stint data
**Tests:** `test_stint_15min`, `test_stint_pit_this_lap`

---

### 9. LMU-28: Fin de Sesión con Evaluación

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Extender SessionEndTrigger
- `backend/src/intelligence/session_evaluator.py` — Nuevo archivo
- `backend/tests/test_session_end_evaluation.py` — Nuevo test

**Cambio:**
```
1. SessionEndTrigger → evaluar calidad del resultado:
   - Start position vs finish position
   - Expected finish position (de compartir-strategy)
   - Good finish: ganó 3+ posiciones o finish dentro de expected
   - Bad finish: perdió 5+ posiciones o muy por debajo de expected
   - P1: "¡Victoria!" / P2-P3: "Podio" / Otros: según evaluación
2. Añadir ALERT_ONLY determinista para mensaje inmediato
3. Mantener LLM_REQUIRED para resumen plus
```

**Dependencias:** `start_position` disponible en telemetría
**Riesgo:** Bajo
**Tests:** `test_session_end_victory`, `test_session_end_good_finish`, `test_session_end_bad_finish`

### 10. LMU-40: FCY Spotter Cooldown (10-30s pause)

**Archivos a tocar:**
- `backend/src/intelligence/spotter.py` — `_eval_proximity` añadir SC check
- `backend/tests/test_fcy_spotter_silent.py` — Nuevo test

**Cambio:**
```
1. En spotter._eval_proximity, si safety_car_active o full_course_yellow_active:
   - Si speed < 50 m/s O tiempo desde SC inicio < 10s: no emitir proximity
   - Reanudar tras 10-30s (configurable) o cuando speed > 50 m/s
2. Mantener fuel, damage, limiter activos (solo silenciar proximity lateral)
```

**Dependencias:** Ninguna
**Riesgo:** Bajo
**Tests:** `test_fcy_spotter_silent`, `test_fcy_spotter_resume`

### 11. LMU-33: Critical Event Latency (race_start, flags, damage NO batch)

**Archivos a tocar:**
- `backend/src/intelligence/proactive_monitors.py` — race_start _eval_flags devolver alert IMMEDIATE
- `backend/src/intelligence/commentary_orchestrator.py` — Verificar bypass
- `backend/src/models/messages.py` — Sin cambios
- `backend/tests/test_critical_event_latency.py` — Nuevo test

**Cambio:**
```
1. proactive_monitors.evaluate → race_start, flags_yellow transitions, damage crítico:
   Devolver como AlertMessage directo (no commentary event).
   Usar broadcast_callback para enviar alert IMMEDIATE.
2. Verificar event_registry.py: preemptible=False ya existe en race_start.
   Implementar bypass real en proactive_monitors.
3. Mantener commentary batch para eventos NO críticos (lap_complete, gap_update, etc.)
```

**Dependencias:** Ninguna — solo cambio de canal de salida
**Riesgo:** Bajo — es cambio de ruta, no de lógica
**Tests:** `test_critical_events_immediate`, `test_non_critical_still_batch`

---

## Fase P1 — Paridad CC Útil (Post-P0)

**Archivos a tocar:**
- `backend/src/intelligence/triggers.py` — Extender SessionEndTrigger
- `backend/src/intelligence/session_evaluator.py` — Nuevo archivo
- `backend/tests/test_session_end_evaluation.py` — Nuevo test

**Cambio:**
```
1. SessionEndTrigger → evaluar calidad del resultado:
   - Start position vs finish position
   - Expected finish position (de compartir-strategy)
   - Good finish: ganó 3+ posiciones o finish dentro de expected
   - Bad finish: perdió 5+ posiciones o muy por debajo de expected
   - P1: "¡Victoria!" / P2-P3: "Podio" / Otros: según evaluación
2. Añadir ALERT_ONLY determinista para mensaje inmediato
3. Mantener LLM_REQUIRED para resumen plus
```

**Dependencias:** start_position disponible en telemetría
**Riesgo:** Bajo
**Tests:** `test_session_end_victory`, `test_session_end_good_finish`, `test_session_end_bad_finish`

---

## Fase P1 — Paridad CC Útil (Post-P0)

| ID | Cambio | Archivos | Días est. |
|----|--------|----------|-----------|
| LMU-06 | fuel_about_to_run_out sector 3 | spotter.py | 0.5 |
| LMU-07 | SC green transition | spotter.py, flags_monitor.py | 0.5 |
| LMU-08 | Session end + position final | triggers.py, proactive_monitors.py | 0.5 |
| LMU-10 | UI toggle enable_gap_messages + voz opcional | config.ts, alertVoice.ts, spotter.py | 1 |
| LMU-11 | Brake wear por rueda | triggers.py | 0.5 |
| LMU-12 | Multiclass escenarios específicos | triggers.py | 1 |
| LMU-14 | Fuel persistencia coche/pista | history_store.py | 1 |
| LMU-21 | Corner names inmediato en mid-point | proactive_monitors.py | 0.5 |
| LMU-22 | Gap update trend detection + frecuencia UI | proactive_monitors.py, config | 1 |
| LMU-23 | Race start quality (good/bad) | proactive_monitors.py | 1 |
| LMU-24 | Pearls slider + audible A2 | pearls_of_wisdom.py, alertVoice.ts | 0.5 |
| LMU-26 | Competitor pit exit + gap | triggers.py, proactive_monitors.py | 0.5 |
| LMU-32 | Sector delta tracking (sector1/2/3 vs best) | proactive_monitors.py, sector_analysis.py | 1.5 |
| LMU-34 | Watched opponents voice command + store | engine.py, shared-strategy | 1 |
| LMU-38 | Priority queue 3 niveles + delayed validation | priorityAudioQueue.ts, useWebSocket.ts | 2 |
| LMU-40 | FCY spotter cooldown | spotter.py | 0.5 |
| LMU-42 | Condition-aware best lap | shared-strategy/models.py | 1 |
| LMU-45 | Fuel persistence car/track | history_store.py | 1 |
| LMU-47 | Session startup delay | engine.py | 0.5 |
| LMU-48 | Sidecar brake_wear fix | sidecar/strategy_runner.py | 0.5 |

## Fase P2 — Beta/Mejoras

| ID | Cambio | Archivos |
|----|--------|----------|
| LMU-01 | Hysteretic exit threshold con car_length+gap | spotter_state.py |
| LMU-02 | Message expiry para alerts | spotter.py |
| LMU-03 | Line-astern detection | spotter_state.py |
| LMU-04/05 | Ajustes menores pit limiter | spotter.py |
| LMU-16/17 | Pit window lap numbers en mensaje | triggers.py |
| LMU-27 | Gap closed con historial y trend | triggers.py |
| LMU-29 | Oil pressure monitor | proactive_monitors.py |

---

## Regresión: Archivos que NO deben tocarse en P0

| Archivo | Razón |
|---------|-------|
| `frontend/src/services/priorityAudioQueue.ts` | Pipeline audio intacto |
| `frontend/src/hooks/useWebSocket.ts` | Sin cambios WS |
| `backend/src/intelligence/engine.py` | Mínimos cambios (solo añadir overtake detection) |
| `backend/src/intelligence/pearls_of_wisdom.py` | No tocar hasta A2 |
| `backend/src/intelligence/commentary_orchestrator.py` | No tocar — pipeline batch intacto |
| `shared-strategy/` | Mínimos cambios — solo validar datos disponibles |

---

## Resumen de Riesgos por Dependencia de Datos LMU

| Dato LMU Necesario | P0 ID | Disponible? | Riesgo |
|-------------------|-------|-------------|--------|
| tyre_pressure (4 ruedas) | LMU-09 | ❓ Desconocido | ALTO |
| car_damage desglosado | LMU-09 | ❓ lmu_damage.py nuevo | MEDIO |
| driver_stint_seconds_remaining | LMU-25 | ❓ Desconocido | ALTO |
| rain_density | LMU-30 | ❓ Probablemente sí (REST API) | BAJO |
| penalty_type (drive_through/stop_go) | LMU-13 | ❓ Probablemente no | ALTO |
| start_position | LMU-28 | ✅ Sí (standing_position inicial) | NINGUNO |

---

*Plan generado por Sisyphus — Jun 2026*
