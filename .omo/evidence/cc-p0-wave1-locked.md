---
generated: 2026-06-07
sources: [CC GitLab main (todos), Vantare código fuente, .omo/evidence/cc-behavior-parity-matrix.yaml, .omo/evidence/cc-behavior-implementation-plan.md, .omo/evidence/lmu-data-availability.md]
scope: annex-only (no full matrix rewrite)
reviewed_por: 3 modelos previos + lectura exhaustiva
---

# Anexo 3: Wave 1 Cerrada — Contradicciones Resueltas y Plan de Implementación

## Sección A — Contradicciones Resueltas

| # | Contradicción | Fuentes | Decisión Final | Justificación |
|---|---|---|---|---|
| 1 | **LMU-40 (FCY spotter pause): P0 en plan vs P1 en YAML** | YAML: P1. Plan: listado como P0. | **P1 — mover a Wave 2** | No cambiar. El spotter lateral tiene secondary impacto vs LMU-09/15/20. CC efectivamente pausa spotter 10-30s durante FCY (CrewChief.cs lines `fcySpotterCooldownWindow`), pero el fix es trivial (<0.5d) y no bloquea otros P0. El piloto nota más la ausencia de daño/penalizaciones que el spotter continuo durante SC. |
| 2 | **LMU-45 (fuel persistence): P0 en resumen vs P1 en YAML** | YAML: P1. Resumen markdown: P0. | **P1 — Wave 2** | Fuel persistence es mejora de calidad, no bug conductual. CC persiste consumo a JSON (Fuel.cs:savePersistedFuelUsage) para estimar mejor primera carrera en un combo. Vantare estima con consumo intra-sesión, que funciona. No hay diferencia audible para el piloto. |
| 3 | **Position messages: practice/quali habilitado en CC vs Vantare silencia fuera de race** | Position.cs: `applicableSessionTypes = [Practice, Qualify, Race]`. Vantare proactive_monitors: solo `_is_race_phase()`. | **Mantener Vantare: solo race para commentary** | CC Position.cs reproduce en practice/quali también (position reminders, pole message). Sin embargo, el feedback del piloto indicó que position en quali/practice es molesto cuando estás concentrado. Decisión alineada con configuración CC: CC tiene `enable_position_messages` toggle (default true) — Vantare puede deshabilitarlo en no-race por defecto. Añadir toggle si se desea. |
| 4 | **LMU-33: plan modifica proactive_monitors vs plan dice "no tocar commentary_orchestrator"** | Plan P0 item 10 modifica proactive_monitors.py. Plan también dice "no tocar" en regresión. | **Modificar proactive_monitors SOLO para race_start/flags/damage crítico** | No hay contradicción real. La regla "no tocar commentary_orchestrator.py" se refiere a no cambiar el debounce/batch pipeline existente. La modificación es: ciertos eventos (race_start, flags críticos) deben salir por alert IMMEDIATE, no por commentary batch. Esto se hace en proactive_monitors.py (donde se generan los eventos), no en commentary_orchestrator.py (que solo procesa los que llegan). |
| 5 | **LMU-10 gaps: CC voz default ON, Vantare UI-only intencional** | YAML: P1, silencio intencional. Plan previo: mantener silencio. | **Wave 1 NO incluye LMU-10** | El usuario reportó en pista que gaps constantes saturaban TTS. La decisión de UI-only es correcta para alpha. CC tiene `enable_gap_messages=true` por defecto pero también `frequency_of_gap_ahead_reports=5` (1-10 escala). Vantare podría añadir toggle + frecuencia en beta. No bloqueante ahora. |
| 6 | **11 ítems P0 en plan vs capacidad real Wave 1** | Plan lista 11 P0. Capacidad Wave 1: 6 ítems. | **Wave 1 = 6 ítems. Resto a Wave 2+** | Ver Sección B para la selección. Criterio: máximo impacto conductual audible + datos LMU verificados + quick wins. |

---

## Sección B — Wave 1 LOCKED (6 ítems)

```yaml
wave1:
  - rank: 1
    id: LMU-09
    nombre: "Daño multicomponente + Puncture + Crash AreYouOK"
    por_que_wave1: "El piloto NO SABE si tiene pinchazo, alerón roto o 
      suspensión dañada. CC avisa cada nivel por separado. Es el gap 
      conductual más grande en pista."
    archivos_vantare:
      - backend/src/intelligence/damage_report.py (refactor)
      - backend/src/intelligence/spotter.py (_eval_damage extender)
      - backend/src/intelligence/triggers.py (nuevo DamageTrigger ALERT_ONLY)
      - backend/src/models/messages.py (sin cambios)
    depende_datos_lmu: YES
    bloqueado_si: null
    criterio_listo_lmu: |
      Conducir LMU, golpear pared a 200km/h. Verificar:
      - ¿Suena "Golpe fuerte. Daño grave en el frontal"?
      - ¿Pinchazo detectado en mWheels.mFlat?
      - ¿Crash >40G detectado?
    tests_ci_minimos:
      - test_damage_multi_component (5 niveles + puncture)
      - test_crash_40g_detection
      - test_damage_edge_once

  - rank: 2
    id: LMU-15
    nombre: "Flags FCY Ciclo Completo (PITS_CLOSED/OPEN/GREEN)"
    por_que_wave1: "CC anuncia cada fase del SC (pits cerrados, pits abiertos, 
      última vuelta, verde). Vantare solo dice 'SC activo' una vez. El piloto 
      no sabe cuándo puede entrar en boxes ni cuándo se relanza."
    archivos_vantare:
      - backend/src/intelligence/flags_monitor.py (FCY phase tracking)
      - backend/src/intelligence/spotter.py (_eval_safety_car extender)
    depende_datos_lmu: YES
    bloqueado_si: null  # mYellowFlagState disponible
    criterio_listo_lmu: |
      Esperar SC en LMU. Verificar:
      - ¿"Safety Car desplegado. Pits cerrados" suena al activarse?
      - ¿"Pits abiertos" cuando cambia fase?
      - ¿"Última vuelta de Safety Car"?
      - ¿"Bandera verde. A tope" al relanzar?
    tests_ci_minimos:
      - test_fcy_phase_sequence
      - test_sc_green_transition

  - rank: 3
    id: LMU-13
    nombre: "Penalización con Conteo Regresivo 3/2/1 + Pit Now"
    por_que_wave1: "CC dice '3 vueltas para servir, 1 vuelta, entra ahora'. 
      Vantare solo dice 'penalización detectada'. El piloto se entera 
      demasiado tarde y es descalificado."
    archivos_vantare:
      - backend/src/intelligence/triggers.py (PenaltyMonitorTrigger refactor)
      - backend/src/intelligence/penalty_tracker.py (nuevo)
    depende_datos_lmu: PARTIAL
    bloqueado_si: null  # mNumPenalties funciona, sin tipo pero conteo sirve
    criterio_listo_lmu: |
      Cometer infracción (cortar curva). Verificar:
      - ¿"Penalización asignada. 3 vueltas para entrar" suena?
      - ¿"2 vueltas" suena 1 vuelta después?
      - ¿"Entra a boxes ahora" suena en sector 3?
      - ¿"Penalización cumplida" tras servir?
    tests_ci_minimos:
      - test_penalty_countdown_3_2_1
      - test_penalty_not_served
      - test_penalty_pit_now_sector3

  - rank: 4
    id: LMU-20
    nombre: "Adelantamientos y Rebasamientos Detectados"
    por_que_wave1: "CC dice 'adelantamiento completado' o 'te ha pasado 
      un rival'. Vantare no dice nada. Es uno de los eventos más 
      notorios que faltan en pista."
    archivos_vantare:
      - backend/src/intelligence/proactive_monitors.py (overtake detection)
      - backend/src/intelligence/overtake_detector.py (nuevo)
    depende_datos_lmu: YES
    bloqueado_si: null  # competitor list + mPlace + gaps disponible
    criterio_listo_lmu: |
      Adelantar a un rival en LMU. Verificar:
      - ¿"Adelantamiento completado" suena tras pasar?
      - ¿No suena si adelantas en bandera amarilla?
      - ¿No suena si adelantas y entras en boxes?
    tests_ci_minimos:
      - test_overtake_detected
      - test_being_overtaken
      - test_overtake_cooldown_20s

  - rank: 5
    id: LMU-33
    nombre: "Latencia Crítica — Eventos NO Commentary Batch"
    por_que_wave1: "race_start, flags críticos y daño severo tardan 
      5-10s en CommentaryOrchestrator vs CC inmediato. El piloto 
      recibe la información cuando ya no es útil."
    archivos_vantare:
      - backend/src/intelligence/proactive_monitors.py (race_start, flags → alert)
    depende_datos_lmu: NO  # solo cambio de canal de salida
    bloqueado_si: null
    criterio_listo_lmu: |
      Iniciar carrera. Verificar:
      - ¿"Buena salida" suena en <1s desde que se completa la salida?
      - ¿SC "Safety Car" suena inmediato (no 5s después)?
    tests_ci_minimos:
      - test_critical_events_immediate
      - test_non_critical_still_batch

  - rank: 6
    id: LMU-30
    nombre: "Lluvia en Tiempo Real (no solo Forecast)"
    por_que_wave1: "CC dice 'lluvia ligera aumentando' cuando empieza 
      a llover. Vantare solo usa forecast LLM (cada 120s, caro). 
      El piloto no sabe que está lloviendo hasta que ya derrapa."
    archivos_vantare:
      - backend/src/intelligence/triggers.py (nuevo RainRealtimeTrigger o modificar WeatherChangeTrigger)
      - backend/src/intelligence/rain_monitor.py (nuevo)
    depende_datos_lmu: YES
    bloqueado_si: null  # mRaining disponible a 20Hz
    criterio_listo_lmu: |
      Conducir con lluvia variable. Verificar:
      - ¿"Llovizna — vigila la pista" suena cuando mRaining>0.01?
      - ¿"Dejó de llover" suena al secarse?
      - ¿No hay falsos positivos con mRaining=0?
    tests_ci_minimos:
      - test_rain_drizzle_transition
      - test_rain_heavy_transition
      - test_rain_stopped
```

---

## Sección C — Wave 2 Preview (pospuestos)

| ID | Título | Por qué no Wave 1 |
|---|---|---|
| LMU-19 | Push Now con cálculo best lap | Requiere integración con opponent best lap data ya disponible pero más complejo que los 6 elegidos |
| LMU-40 | FCY spotter cooldown | Fix trivial pero menos impacto que LMU-09/15/13/20/33/30 |
| LMU-18 | Tyre temp hot/cold por rueda | Útil pero no crítico — el trigger >105°C ya existe |
| LMU-28 | Session end con evaluación | Afecta al final de carrera, no durante. Menos impacto que overtakes |
| LMU-45 | Fuel persistence car/track | Mejora de calidad, no bug |
| LMU-38 | Priority queue 3 niveles | Mejora pipeline audio, no conductual |
| LMU-42 | Condition-aware best lap | Afecta PushNow y GapClosed, pero esos no están en Wave 1 |
| LMU-47 | Session startup delay 6s | Preventivo, no hay bug reportado |

---

## Sección D — Reglas de Arquitectura Wave 1 (Binding)

### D1. Qué eventos nunca van a CommentaryOrchestrator batch

Los siguientes eventos deben emitirse como `alert IMMEDIATE` directamente (NUNCA pasar por `enqueue_commentary`):

| Evento | Motivo |
|--------|--------|
| race_start (good/bad/terrible) | Timing crítico, CC inmediato priority 5 |
| damage severo / puncture / crash | Seguridad, CC CRITICAL_MESSAGE priority 15 |
| penalty pit_now (sector 3) | Timing crítico, CC priority 10 inmediato |
| FCY/SC start | CC IMPORTANT_MESSAGE inmediato |
| green flag | CC IMPORTANT_MESSAGE inmediato |
| overtake / being overtaken | CC priority 10 inmediato |
| fuel crítico <1 vuelta | CC spotter inmediato |
| brake_wear crítico | CC ALERT_ONLY inmediato |
| rain cambio de nivel | CC IMPORTANT_MESSAGE inmediato |

**Implementación:** En `proactive_monitors.py`, los eventos marcados como `critical` deben usar `broadcast_callback(AlertMessage(...))` directamente en lugar de devolver `CommentaryEvent` tuple para `enqueue_commentary`.

### D2. Spotter @ 20Hz vs Ingeniero @ 0.5Hz — Canales

| Capa | Frecuencia | Qué va aquí | Cómo se emite |
|------|-----------|-------------|---------------|
| **Spotter** | 20Hz (cada tick) | Proximidad lateral, limiter, fuel<1, damage impacto, SC/FCY flag, last lap | AlertMessage → priorityAudioQueue IMMEDIATE |
| **Ingeniero Alert** | 0.5Hz (engine cycle) | Brake wear, multiclass, driver swap, penalty (nueva/servida), penalty countdown, pit window, tyre temp, rain | AlertMessage → priorityAudioQueue IMMEDIATE (críticos) o NORMAL |
| **Ingeniero Commentary** | 0.5Hz (engine cycle) | position_change, lap_complete, gap_update, fuel commentary, tyre/brake commentary | commentary batch → commentary_end → priorityAudioQueue NORMAL |
| **Ingeniero LLM** | 0.5Hz (on trigger) | FuelCritical(<3), FlagsMonitor(LLM advice), PitWindow, GapClosed, PushNow, SessionEnd, WeatherChange, PilotQuestion | llm_pending → advice_* streaming → advice_end → priorityAudioQueue NORMAL |

**NUNCA** mezclar canales — los mensajes IMMEDIATE deben poder interrumpir NORMAL sin bloqueo.

### D3. Practice / Qualifying / Race — Tabla de Silenciamiento Acordada

Basada en CC `applicableSessionTypes` + feedback piloto Vantare:

| Evento | Practice | Qualifying | Race |
|--------|----------|------------|------|
| Spotter lateral | ✅ (si habilitado) | ❌ (default off) | ✅ |
| Pit limiter | ✅ | ✅ | ✅ |
| Gaps spotter | ❌ | ❌ | ❌ (UI-only) |
| Fuel <1 lap | ✅ | ✅ | ✅ |
| SC/FCY | ✅ | ❌ | ✅ |
| Last lap | ❌ | ❌ | ✅ |
| Damage impacto | ✅ | ✅ | ✅ |
| Brake wear | ❌ | ❌ | ✅ (solo race) |
| Multiclass | ❌ | ❌ | ✅ |
| Penalty | ✅ | ✅ | ✅ |
| Race start | ❌ | ❌ | ✅ |
| Overtake | ❌ | ❌ | ✅ |
| Push Now | ❌ | ❌ | ✅ |
| Rain real-time | ✅ | ✅ | ✅ |
| Fuel <3 vueltas (LLM) | ❌ | ❌ | ✅ |
| Pearls | ❌ | ❌ | ✅ |
| Session end | ✅ | ✅ | ✅ |
| Tyre temp >105°C | ✅ | ✅ | ✅ |

**Nota:** CC sí emite algunos mensajes en practice (damage, fuel, flags). La tabla refleja acuerdo con feedback piloto: en practice/quali se minimizan mensajes no críticos.

### D4. LLM: Qué triggers Wave 1 pasan a determinista vs mantienen LLM

| Trigger | Wave 1 cambio | Razón |
|---------|--------------|-------|
| FuelCritical | ✅ Sigue LLM (es estratégico) | CC usa voz determinista pero Vantare LLM da más contexto. Aceptable. |
| FlagsMonitor | ⚠️ **Bifurcar**: transiciones FCY → DETERMINISTA (alert). LLM solo para consejo estratégico post-evento | CC no usa LLM. La inmediatez es crítica. |
| PenaltyMonitor | ✅ Pasa a ALERT_ONLY determinista con countdown | CC no usa LLM para penalizaciones. |
| WeatherChange | ⚠️ **Bifurcar**: cambio nivel lluvia → DETERMINISTA (alert). Forecast LLM → complemento | CC ConditionsMonitor es determinista. |
| GapClosed | ✅ Sigue LLM (es consejo táctico) | No es crítico inmediato. |
| PushNow | ✅ Sigue LLM (es estratégico) | CC usa WAV determinista. Vantare LLM da contexto de estrategia. |
| SessionEnd | ⚠️ **Bifurcar**: resultado → DETERMINISTA (alert). Resumen → LLM | CC es determinista para resultado. LLM para análisis post. |
| PilotQuestion | ✅ Sigue LLM (es interactivo) | No hay equivalente CC (CC usa grammar commands). |

---

## Sección E — Checklist Aceptación Wave 1 (para marcar en LMU)

```yaml
checklist_wave1:
  - id: "W1-01"
    ref: "LMU-09"
    escenario: "Golpear pared a alta velocidad en recta de Spa"
    condicion: "mLocalAccel > 392 m/s² (40G)"
    comportamiento_esperado: |
      - Si velocidad final < 3 m/s: ¿"Estás bien?" suena tras 2s?
      - Si no responde: ¿8s después 2do intento?
      - Si hay daño: ¿"Daño grave en el frontal" suena?
    resultado: [PASS/FAIL]

  - id: "W1-02"
    ref: "LMU-09"
    escenario: "Pinchazo (simular mWheels[i].mFlat = true)"
    condicion: "mFlat == true en cualquier rueda"
    comportamiento_esperado: |
      - ¿Suena "Pinchazo {wheel}" con delay 4-7s?
      - ¿No se repite cada tick?
    resultado: [PASS/FAIL]

  - id: "W1-03"
    ref: "LMU-15"
    escenario: "Esperar Safety Car en carrera larga"
    condicion: "mGamePhase cambia a 6"
    comportamiento_esperado: |
      - ¿"Safety Car desplegado. Pits cerrados" inmediato?
      - ¿"Pits abiertos" cuando mYellowFlagState=4?
      - ¿"Bandera verde. A tope" al relanzar?
    resultado: [PASS/FAIL]

  - id: "W1-04"
    ref: "LMU-13"
    escenario: "Cortar curva recibir penalización"
    condicion: "mNumPenalties incrementa"
    comportamiento_esperado: |
      - ¿"Penalización asignada. 3 vueltas para entrar"?
      - 1 vuelta después: ¿"2 vueltas"?
      - 2 vueltas después: ¿"1 vuelta. Entra ahora"?
      - En sector 3: ¿"Entra a boxes ahora"?
    resultado: [PASS/FAIL]

  - id: "W1-05"
    ref: "LMU-20"
    escenario: "Adelantar a un rival"
    condicion: "mPlace mejora"
    comportamiento_esperado: |
      - ¿"Adelantamiento completado" suena tras 4s?
      - ¿No suena bajo bandera amarilla?
    resultado: [PASS/FAIL]

  - id: "W1-06"
    ref: "LMU-33"
    escenario: "Inicio de carrera + SC inmediato"
    condicion: "race_start + gamePhase=6"
    comportamiento_esperado: |
      - ¿race_start suena como alert (no batch)?
      - ¿SC suena INMEDIATO (no 5s después)?
      - ¿spotter proximity NO interrumpe SC?
    resultado: [PASS/FAIL]

  - id: "W1-07"
    ref: "LMU-30"
    escenario: "Lluvia variable en LMU"
    condicion: "mRaining cambia entre niveles"
    comportamiento_esperado: |
      - ¿"Llovizna" suena cuando mRaining>0.01?
      - ¿"Lluvia intensa" cuando mRaining>0.6?
      - ¿"Dejó de llover" cuando mRaining≈0?
    resultado: [PASS/FAIL]
```
