---
generated: 2026-06-07
sources: [CC GitLab main: DamageReporting.cs, Penalties.cs, FlagsMonitor.cs, Position.cs, PushNow.cs, SessionEndMessages.cs, ConditionsMonitor.cs, TyreMonitor.cs, Fuel.cs, CrewChief.cs; Vantare: triggers.py, proactive_monitors.py, damage_report.py]
scope: annex-only (no full matrix rewrite)
---

# Anexo 2: Plantillas de Mensajes CC → Español TTS para Urgencias P0

## Reglas Generales para las Plantillas

1. **Radio breve, 1-2 frases máximo** en urgencias (estilo CC)
2. **No LLM** para estos mensajes — son deterministas, deben ser inmediatos
3. **Canales:** alert IMMEDIATE para críticos, commentary batch para informativos
4. **Edge-once** salvo que se indique cooldown
5. **Números:** CC usa NumberReader nativo ("one point two"). Vantare puede usar numeral directo ("1.2") por brevedad
6. **Traducción:** No literal - conservar intención CC en español natural de ingeniero

---

## LMU-09: Damage (Impactos, Niveles, Puncture, Crash)

### Impacto Nuevo (por severidad)
- **CC WAV folder:** `damage_reporting/severe_aero_damage`, `minor_aero_damage`, `trivial_aero_damage_gen`
- **CC fuente:** `DamageReporting.cs:playDamageToReport()`
- **Dispara cuando:** `lastImpactET` nuevo y `magnitude >= 25`. Se espera 3s `timeToWaitForDamageToSettle`
- **Condición CC:** `aeroDamage = MAJOR/DESTROYED` → severe; `MINOR` → minor; `TRIVIAL` → trivial
- **Plantilla Vantare (español TTS):**
  - `severity=grave` (dent_max>=2 o aero>=60%): **"Golpe fuerte. Daño grave en el frontal."**
  - `severity=moderado` (dent_max>=1 o aero>=25%): **"Impacto notable. Daño moderado — revisa el balance del coche."**
  - `severity=leve`: **"Toque detectado. Daños leves."**
- **Variables:** ninguna (el mensaje varía por severity)
- **Canal CC:** IMPORTANT_MESSAGE priority 15
- **Canal Vantare:** alert IMMEDIATE priority 4 (CRITICAL) / 3 (WARNING)
- **LLM permitido:** NO para este mensaje
- **Edge-once:** Sí, por nivel de daño (no repetir si sube de leve a moderado)

### Puncture (Pinchazo)
- **CC WAV folder:** `damage_reporting/left_front_puncture`, `right_front_puncture`, `left_rear_puncture`, `right_rear_puncture`
- **CC fuente:** `DamageReporting.cs:triggerInternal()` (puncture check cada 3s)
- **Dispara cuando:** `mWheels[i].mFlat == true` (o presión < threshold 30 tras 4-7s delay)
- **Plantilla Vantare (español TTS):**
  - FL: **"Pinchazo delantero izquierdo."**
  - FR: **"Pinchazo delantero derecho."**
  - RL: **"Pinchazo trasero izquierdo."**
  - RR: **"Pinchazo trasero derecho."**
- **Variables:** {wheel} (delantero/trasero izquierdo/derecho)
- **Canal CC:** CRITICAL_MESSAGE priority 15
- **Canal Vantare:** alert IMMEDIATE priority 4
- **LLM permitido:** NO
- **Edge-once:** Sí, hasta que se repara o cambia rueda

### Crash >40G ("Are you OK?")
- **CC WAV folder:** `damage_reporting/are_you_ok_first_try`, `are_you_ok_second_try`, `are_you_ok_third_try`
- **CC fuente:** `DamageReporting.cs:triggerInternal()` (aceleración > 400 m/s² O > 270 para ACC)
- **Dispara cuando:** `mLocalAccel` > 392 m/s² (40G) Y speed después del impacto < 3 m/s. Espera 2s post-impacto
- **Repetición CC:** 3 intentos: 0s, 8s, 16s. Si no responde → "no response, he's dead jim"
- **Plantilla Vantare (español TTS):**
  - 1er intento: **"¿Estás bien? ¿Estás bien?"**
  - 2do intento (8s): **"¿Cómo estás? Responde."**
  - 3er intento (16s): **"No contestas. Entra en boxes si puedes."**
- **Variables:** ninguna
- **Canal CC:** CRITICAL_MESSAGE priority 15 (playMessageImmediately)
- **Canal Vantare:** alert IMMEDIATE priority 4
- **LLM permitido:** NO
- **Edge-once:** No en el sentido clásico — hasta 3 intentos. Cancelar si entra en pits

---

## LMU-13: Penalty (Nueva, Conteo, Pit Now, Servida, No Servida)

### Nueva Penalización
- **CC WAV folder:** `penalties/new_penalty_drivethrough`, `new_penalty_stopgo`, `new_penalty_black_flag`
- **CC fuente:** `Penalties.cs:triggerInternal()` (HasDriveThrough/StopAndGo transition true)
- **Dispara cuando:** `numPenalties` incrementa. CC diferencia tipos. Vantare: mensaje genérico (LMU no expone tipo)
- **Plantilla Vantare (español TTS):**
  - **"Penalización asignada. Tienes 3 vueltas para entrar en boxes."**
- **Variables:** ninguna (genérico porque LMU no da tipo)
- **Canal CC:** priority 10
- **Canal Vantare:** alert IMMEDIATE priority 3 (HIGH)
- **LLM permitido:** NO
- **Edge-once:** Sí, por nueva penalización

### 3 vueltas restantes
- **CC WAV folder:** `penalties/penalty_three_laps_left`
- **CC fuente:** `Penalties.cs:triggerInternal()` (queued con pitstopDelay=20s)
- **Dispara cuando:** Misma vuelta que se asignó. Delay 20s para evitar saturación post-penalty
- **Plantilla Vantare (español TTS):**
  - **"3 vueltas para servir la penalización."**
- **Canal CC:** priority 10 (delayed message)
- **Canal Vantare:** alert NORMAL priority 2
- **LLM permitido:** NO
- **Edge-once:** Sí

### 2 vueltas restantes
- **CC WAV folder:** `penalties/penalty_two_laps_left`
- **Plantilla Vantare (español TTS):**
  - **"2 vueltas. Tienes que entrar."**
- **Canal Vantare:** alert IMMEDIATE priority 3

### 1 vuelta restante
- **CC WAV folder:** `penalties/penalty_one_lap_left_stopgo`, `one_lap_left_drivethrough`, `one_lap_left_to_pit`
- **Plantilla Vantare (español TTS):**
  - **"1 vuelta. Entra ahora o serás descalificado."**
- **Canal Vantare:** alert IMMEDIATE priority 4 (CRITICAL)

### Pit Now (Sector 3)
- **CC WAV folder:** `penalties/pit_now_stop_go`, `pit_now_drive_through`
- **CC fuente:** `Penalties.cs:triggerInternal()` — cuando sector=3 Y lapsCompleted-penaltyLap==2
- **Plantilla Vantare (español TTS):**
  - **"Entra a boxes ahora."**
- **Canal Vantare:** alert IMMEDIATE priority 4

### Penalización Servida
- **CC WAV folder:** `penalties/penalty_served`
- **Plantilla Vantare (español TTS):**
  - **"Penalización cumplida. Buen trabajo."**
- **Canal Vantare:** alert NORMAL priority 2

### Penalización No Servida / Descalificación
- **CC WAV folder:** `penalties/penalty_not_served`, `penalties/disqualified`
- **Plantilla Vantare (español TTS):**
  - **"No has servido la penalización. Vas a ser descalificado."**
- **Canal Vantare:** alert IMMEDIATE priority 4

### Cut Track Warning (opcional)
- **CC WAV folder:** `penalties/cut_track_race_{1-4}`, `cut_track_prac_or_qual_{1-4}`
- **CC fuente:** `Penalties.cs:triggerInternal()` — cutTrackWarningsCount incrementa. Cooldown 30s
- **Plantilla Vantare (español TTS):**
  - Nivel 1: **"Límites de pista — cuidado."**
  - Nivel 2: **"Reiteradas salidas de pista. Van a penalizarte."**
  - Nivel 3: **"No sigas cortando. Van a penalizar."**
  - Nivel 4: **"Ya vale de cortar. Te van a descalificar."**
- **Canal Vantare:** alert NORMAL priority 2
- **Edge-once:** Cooldown 30s entre mensajes (style CC)

---

## LMU-15 / LMU-07: FCY / SC Fases

### FCY Start
- **CC WAV folder:** `flags/fc_yellow_start_eu` / `fc_yellow_start_usa`
- **CC fuente:** `FlagsMonitor.cs:gameDataYellowFlagImplementation()` — cuando fcyPhase cambia a PITS_CLOSED
- **Dispara cuando:** `mGamePhase` pasa a 6 (FCY/SC). CC distingue con/sin safety car según `folderFCYellowStartNoSafetyCarEU`
- **Plantilla Vantare (español TTS):**
  - Con safety car: **"Safety Car desplegado. Pits cerrados."**
  - Sin safety car: **"Bandera amarilla en todo el circuito. Pits cerrados."**
- **Canal CC:** IMPORTANT_MESSAGE priority 10
- **Canal Vantare:** alert IMMEDIATE priority 4
- **LLM permitido:** NO
- **Edge-once:** Sí, por transición de fase

### Pits Open
- **CC WAV folder:** `flags/fc_yellow_pits_open_eu` / `fc_yellow_pits_open_usa`
- **Dispara cuando:** `mYellowFlagState` cambia a 4 (pits open)
- **Plantilla Vantare (español TTS):**
  - Líderes: **"Pits abiertos — coches de delante pueden entrar."**
  - No líderes: **"Pits abiertos."**
- **Canal Vantare:** alert IMMEDIATE priority 3

### Last Lap FCY
- **CC WAV folder:** `flags/fc_yellow_last_lap_current_eu`, `fc_yellow_last_lap_next_eu`
- **Dispara cuando:** `mYellowFlagState` cambia a 5 (last lap)
- **Plantilla Vantare (español TTS):**
  - **"Última vuelta de Safety Car."**
- **Canal Vantare:** alert IMMEDIATE priority 3

### Prepare for Green
- **CC WAV folder:** `flags/fc_yellow_prepare_for_green_eu` / `fc_yellow_prepare_for_green_usa`
- **Dispara cuando:** `mYellowFlagState` cambia a 6 (resume)
- **Plantilla Vantare (español TTS):**
  - **"Prepárate para relanzamiento."**
- **Canal Vantare:** alert IMMEDIATE priority 3

### Green Flag
- **CC WAV folder:** `flags/fc_yellow_green_flag`
- **Dispara cuando:** `mGamePhase` vuelve a 5 (green)
- **Plantilla Vantare (español TTS):**
  - **"Bandera verde. A tope."**
- **Canal Vantare:** alert IMMEDIATE priority 3

---

## LMU-20: Overtake / Being Overtaken

### Overtake completado
- **CC WAV folder:** `position/overtaking`
- **CC fuente:** `Position.cs:checkCompletedOvertake()` — requiere gap sampling + minTimeToWaitBeforeReportingPass (4s) + gap > minTimeDeltaForPass (0.15s)
- **Dispara cuando:** gap_ahead samples muestran crossover, opponent key cambia, gap>0.15s, lap válida, sin penalties/yellow/offtrack
- **Plantilla Vantare (español TTS):**
  - **"Adelantamiento completado."**
- **Variables:** {driver_name} (nombre rival si disponible)
- **Canal CC:** priority 10 (con pearl GOOD opcional)
- **Canal Vantare:** alert IMMEDIATE priority 2
- **LLM permitido:** NO para el mensaje. SÍ para comentario post (estrategia)
- **Edge-once:** minTimeBetweenOvertakeMessages = 20s

### Being Overtaken (te han pasado)
- **CC WAV folder:** `position/being_overtaken`
- **CC fuente:** `Position.cs:checkCompletedOvertake()` (folderBeingOvertaken)
- **Dispara cuando:** gap_behind samples + opponent key cambia. maxComplaintsPerSession (60)
- **Plantilla Vantare (español TTS):**
  - **"Te ha pasado un rival."**
- **Variables:** {driver_name}
- **Canal Vantare:** alert NORMAL priority 2
- **Edge-once:** cooldown 20s, max 60/sesión

---

## LMU-30: Rain Realtime (Cambios de Nivel)

### Drizzle increasing
- **CC WAV folder:** `conditions/drizzle_increasing`
- **CC fuente:** `ConditionsMonitor.cs:triggerInternal()` — cuando RainLevel cambia y rainDensity > lastReported
- **Dispara cuando:** `mRaining` cruza umbral 0.01 (drizzle start)
- **Umbrales CC:** NONE(0), DRIZZLE(0.01-0.15), LIGHT(0.15-0.3), MID(0.3-0.6), HEAVY(0.6-0.75), STORM(>0.75)
- **Plantilla Vantare (español TTS):**
  - Drizzle: **"Llovizna — vigila la pista."**
  - Light: **"Lluvia ligera. Prepara intermedias."**
  - Mid: **"Está lloviendo. Considera entrar a por lluvia."**
  - Heavy: **"Lluvia intensa. Entra a por mojado."**
  - Storm: **"Diluvio. Máximo cuidado."**
- **Canal CC:** IMPORTANT_MESSAGE inmediato
- **Canal Vantare:** alert IMMEDIATE priority 3
- **LLM permitido:** NO para el alert. SÍ para consejo de estrategia post-alert
- **Edge-once:** por nivel. Cooldown 120s (RF2) / 10s (otros). Para LMU usar 120s.

### Rain decreasing (vuelta a seco)
- **CC WAV folder:** `conditions/drizzle_decreasing`, `light_rain_decreasing`, etc., `stopped_raining`
- **Plantilla Vantare (español TTS):**
  - **"Dejó de llover. Pista secándose."**
- **Canal Vantare:** alert NORMAL priority 2

---

## LMU-18: Tyre Temperature (Hot/Cooking por Rueda)

### Hot tyres
- **CC WAV folder:** `tyre_monitor/hot_front_tyres`, `hot_rear_tyres`, `hot_tyres_all_round`, `hot_left_front_tyre`, etc.
- **CC fuente:** `TyreMonitor.cs:triggerInternal()` — temperature thresholds por rueda/eje
- **Dispara cuando:** tyre carcass temp > 100°C (hot) o > 120°C (cooking). Individual o por eje
- **Plantilla Vantare (español TTS):**
  - Una rueda específica (>105°C): **"Neumático {wheel} caliente."**
    - FL: delantero izquierdo, FR: delantero derecho, RL: trasero izquierdo, RR: trasero derecho
  - Eje delantero ambos >105°C: **"Neumáticos delanteros calientes."**
  - Eje trasero ambos >105°C: **"Neumáticos traseros calientes."**
  - Las 4 >105°C: **"Neumáticos calientes — cuidado con el desgaste."**
  - Cualquiera >120°C: **"Neumático {wheel} sobrecalentado."**
- **Canal Vantare:** alert NORMAL priority 2 (no es crítica inmediata)
- **LLM permitido:** NO. Determinista.
- **Edge-once:** por nivel. Cooldown entre vueltas.

### Cold tyres
- **CC WAV folder:** `tyre_monitor/cold_front_tyres`, `cold_tyres_all_round`
- **Dispara cuando:** temp < 60°C después de 2 vueltas
- **Plantilla Vantare (español TTS):**
  - **"Neumáticos fríos — cuidado las primeras curvas."**
- **Canal Vantare:** alert NORMAL priority 2

---

## LMU-19: Push Now (Win / Hold / Improve)

### Push to win
- **CC WAV folder:** `push_now/push_to_get_win`
- **CC fuente:** `PushNow.cs:checkGaps()` — calcula si (opponentBestLap - playerBestLap) * lapsLeft > gapAhead
- **Dispara cuando:** P2, rival delante alcanzable según diferencia de ritmo y vueltas restantes
- **Plantilla Vantare (español TTS):**
  - P2: **"Empuja — puedes ganar esta carrera."**
  - P3: **"Empuja — puedes ser segundo."**
  - P4: **"Empuja — puedes subir al podio."**
  - Otras: **"Empuja — estás mejorando."**
- **Canal CC:** priority 5
- **Canal Vantare:** alert IMMEDIATE priority 3
- **LLM permitido:** NO para el alert. SÍ para consejo adicional.

### Push to hold (defender)
- **CC WAV folder:** `push_now/push_to_hold_position`
- **Dispara cuando:** rival detrás más rápido Y (playerBestLap - opponentBestLap) * lapsLeft > gapBehind
- **Plantilla Vantare (español TTS):**
  - **"Defiende la posición — viene un rival más rápido."**
- **Canal Vantare:** alert IMMEDIATE priority 3

### Pit Exit Clear
- **CC WAV folder:** `push_now/pits_exit_clear`, `push_now/pits_exit_traffic_behind`
- **Plantilla Vantare (español TTS):**
  - Sin tráfico: **"Salida limpia."**
  - Con tráfico detrás: **"Cuidado — coche cerca saliendo de boxes."**
- **Canal Vantare:** alert NORMAL priority 2

---

## LMU-28: Session End (Resultado)

### Victory / Podium / Good Finish
- **CC WAV folder:** `lap_counter/won_race`, `podium_finish`, `finished_race_good_finish`
- **CC fuente:** `SessionEndMessages.cs:playFinishMessage()`
- **Dispara cuando:** sessionPhase cambia a Finished
- **Plantilla Vantare (español TTS):**
  - P1: **"¡Victoria! Carrera perfecta."**
  - P2: **"Segundo puesto. Gran resultado."**
  - P3: **"Tercer puesto. Podio."**
  - Good finish (mejoró 3+ posiciones): **"P{pos}. Buen resultado — has ganado {gain} posiciones."**
  - Finish normal: **"Carrera completada en P{pos}."**
  - Last: **"P{pos} — último. Hay que trabajar el ritmo."**
- **Canal CC:** priority 10
- **Canal Vantare:** alert IMMEDIATE priority 2 (NORMAL para no crítico)
- **LLM permitido:** NO para el resultado. SÍ para análisis post-carrera.

### Disqualified
- **CC WAV folder:** `penalties/disqualified`
- **Plantilla Vantare (español TTS):**
  - **"Descalificado."**
- **Canal Vantare:** alert IMMEDIATE priority 4

---

## LMU-33: Race Start (Good/Bad/Terrible)

### Good Start
- **CC WAV folder:** `position/good_start`
- **CC fuente:** `Position.cs:triggerInternal()` — si currentClassPosition < SessionStartClassPosition - 1 o es P1
- **Dispara cuando:** CompletedLaps==0, JustGoneGreen+30-50s random delay, ganó 2+ posiciones
- **Plantilla Vantare (español TTS):**
  - **"Buena salida — has ganado {gain} posiciones."**
- **Canal CC:** priority 5
- **Canal Vantare:** alert IMMEDIATE priority 2
- **LLM permitido:** NO

### Bad Start
- **CC WAV folder:** `position/bad_start`, `position/terrible_start`
- **Dispara cuando:** perdió 3+ (bad) o 5+ (terrible) posiciones
- **Plantilla Vantare (español TTS):**
  - 3-4 perdidas: **"Salida complicada — has perdido {lost} posiciones."**
  - 5+ perdidas: **"Mala salida — has perdido {lost} posiciones. Céntrate y recupera."**
- **Canal Vantare:** alert IMMEDIATE priority 2

---

## LMU-40: FCY Spotter Cooldown (sin mensaje — solo comportamiento)

- **Comportamiento CC:** `CrewChief.cs` pausa spotter lateral 10-30s al entrar en FCY (gamePhase==6)
- **Comportamiento Vantare actual:** El spotter sigue emitiendo proximity durante SC
- **Comportamiento deseado:** Cuando `mGamePhase == 6` Y `speed < 50 m/s`:
  1. Suprimir mensajes de proximidad lateral
  2. Reanudar tras 15s o cuando speed > 50 m/s
  3. Mantener funcionando: fuel, damage, safety_car alerts (no silenciar todo, solo proximity)
- **No requiere mensaje TTS** — solo silencio conductual

---

## Mensajes a NO Mezclar en Commentary Batch

Basado en CC `playMessageImmediately()` (bypass total de cola):

| Evento | CC canal | Vantare debe usar |
|--------|----------|-------------------|
| race_start good/bad | priority 5 inmediato | alert IMMEDIATE |
| damage severo | CRITICAL_MESSAGE priority 15 | alert IMMEDIATE priority 4 |
| penalty pit_now | priority 10 inmediato (sector 3) | alert IMMEDIATE priority 4 |
| FCY/SC start | IMPORTANT_MESSAGE inmediato | alert IMMEDIATE priority 4 |
| green flag | IMPORTANT_MESSAGE inmediato | alert IMMEDIATE priority 3 |
| overtake completado | priority 10 | alert IMMEDIATE priority 2 |
| crash/are you OK | CRITICAL_MESSAGE priority 15 | alert IMMEDIATE priority 4 |
| puncture | CRITICAL_MESSAGE priority 15 | alert IMMEDIATE priority 4 |
| fuel crítico <1 vuelta | spotter priority 10 | alert IMMEDIATE priority 4 |
| brake wear crítico | ALERT_ONLY priority 4 | alert IMMEDIATE priority 4 |

**Regla:** Cualquier mensaje cuya omisión o retraso afecte la seguridad o el resultado de la carrera debe ir a alert IMMEDIATE, NO a commentary batch.
