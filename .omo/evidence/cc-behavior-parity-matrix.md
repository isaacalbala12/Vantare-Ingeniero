# Matriz de Paridad Conductual Crew Chief V4 → Vantare Ingeniero

**Generado:** 2026-06-07 | **Fuente CC:** GitLab `mr_belowski/CrewChiefV4` (main) | **Fuente Vantare:** Código fuente + tests CI

**Leyenda:** ✅ MATCH — COMPORTAMIENTO EQUIVALENTE | ⚠️ PARTIAL — DIFIERE EN DETALLES | ❌ MISMATCH — GAP SIGNIFICATIVO | ❓ UNKNOWN — FALTA VERIFICAR

---

## Resumen Ejecutivo

| Categoría | Total | ✅ MATCH | ⚠️ PARTIAL | ❌ MISMATCH |
|-----------|-------|----------|------------|-------------|
| Spotter (LMU-01 a LMU-05) | 5 | 5 | 0 | 0 |
| Spotter Sesión (LMU-06 a LMU-10) | 5 | 1 | 2 | 2 |
| Ingeniero Alert (LMU-11 a LMU-13) | 3 | 0 | 2 | 1 |
| Ingeniero LLM (LMU-14 a LMU-28) | 15 | 0 | 8 | 7 |
| Commentary/Monitores (LMU-29-30) | 2 | 0 | 1 | 1 |
| Audio Pipeline (LMU-31, 33, 35) | 3 | 1 | 1 | 1 |
| Sector/Grid/Watched (LMU-32, 34, 36) | 3 | 0 | 0 | 3 |
| **Nuevos hallazgos exhaustivos** (LMU-37 a LMU-48) | 12 | 0 | 0 | 12 |
| **TOTAL** | **48** | **7** | **14** | **27** |

---

## Top 10 P0 (ordenados por impacto en pista)

| # | ID | Área | Impacto Piloto | Fix Propuesto |
|---|-----|------|----------------|--------------|
| 1 | LMU-09 | **Daño multicomponente + puncture + crash** | No sabe si tiene pinchazo, alerón roto o suspensión dañada. CC avisa cada nivel por separado. | damage_report.py → 5 componentes style CC. Puncture + crash G. |
| 2 | LMU-15 | **Flags FCY ciclo completo** | CC avisa fases pits-closed/open/green. Vantare solo avisa SC/FCY una vez. | FCY phase tracking con mensajes inmediatos. |
| 3 | LMU-13 | **Penalización con conteo regresivo** | CC dice "3 vueltas para servir", "1 vuelta", "box now". Vantare: "penalty detectada". | conteo 3/2/1 + pit_now + cut track warnings. |
| 4 | LMU-20 | **Adelantamientos y rebasamientos** | CC dice "adelantamiento completado" / "te han pasado". Vantare no detecta. | gap sampling + opponent key tracking + mensajes dedicados. |
| 5 | LMU-30 | **Lluvia en tiempo real** | CC dice "lluvia ligera aumentando". Vantare solo forecast LLM (caro, lento). | rain_density real-time alerts inmediatos. |
| 6 | LMU-10 | **Gaps spotter silenciados** | CC tiene gap messages voz por defecto. Vantare los silencia. | Mantener silencio (intencional) pero documentar. P1 añadir toggle. |
| 7 | LMU-18 | **Temperatura neumáticos por rueda** | CC "hot front left tyre". Vantare genérico ">105°C". | 3 niveles + mensaje por eje/rueda. |
| 8 | LMU-19 | **Push Now con cálculo best lap** | CC "push to win" calculando si alcanza. Vantare simple undercut/final lap. | comparación bestLap propio vs rival + laps restantes. |
| 9 | LMU-25 | **Driver swap stint countdown** | CC "15 minutos restantes en stint". Vantare solo detecta cambio de nombre. | countdown messages si LMU expone stint data. |
| 10 | LMU-28 | **Fin de sesión con evaluación** | CC "buen resultado" o rant si malo. Vantare solo P+best. | evaluar mejora vs start position + mensaje de calidad. |
| 11 | LMU-33 | **Latencia eventos críticos** | race_start, flags, damage en commentary batch (5-10s) vs CC inmediato | Pasar a alert IMMEDIATE. No batch. |

---

## Matriz Completa

| ID | Nombre CC | Comportamiento CC | Comportamiento Vantare | Delta | Prioridad | Paridad |
|----|-----------|-------------------|----------------------|-------|-----------|---------|
| LMU-01 | Car Left/Right | WAV spotter, detección geométrica 3D, hold-repeat 3s | TTS dinámico, detección cartesiana+path+world, still-there 3s | Vantare tiene TTS en vez de WAV (aceptable alpha). Ambos with closing speed. | P2 | ✅ |
| LMU-02 | Clear Left/Right | clear_delay 150ms, clear_all_round | clear_delay 0.15s, consolidate clears | Paridad funcional casi perfecta. Message expiry (2000ms) CC no replicado. | P2 | ✅ |
| LMU-03 | Three-wide (in the middle) | 3-wide-on-left/right (off por defecto), line-astern detection | 3-wide ambos lados ocupados, bounce delay | CC detecta stacked vs line-astern. Vantare es más simple (OK para alpha). | P1 | ✅ |
| LMU-04 | Pit Limiter Engage | grace ~3s, edge-once, cooldown | grace 3s, cooldown 30s, entry_window 8s | Prácticamente idéntico. Vantare tiene entry_window adicional. | P2 | ✅ |
| LMU-05 | Pit Limiter Disengage | delay post-exit, edge-once | delay 2s, exit_check, reintentos 0.5s flicker | Vantare mejor contra flicker LMU. | P2 | ✅ |
| LMU-06 | Fuel Critical (<1 lap) | folderAboutToRunOut en sector 3, fuel<3L | finish-safe <1 lap, edge-once | CC aviso en sector 3 adicional. Vantare finish-safe superior. | P1 | ⚠️ |
| LMU-07 | SC/FCY | FCY phase sequence (6+ fases), edge por fase | edge-once activación, sin green transition | Gap grande en ciclo SC completo. | P1 | ⚠️ |
| LMU-08 | Last Lap | SessionEndMessages + LapCounter | edge-once "última vuelta" | CC integra con fin de sesión y posición final. | P1 | ⚠️ |
| LMU-09 | Damage Reporting | 5 componentes, puncture, crash>40G, 'are you OK' | impacto+resumen aero%, sin componentes separados | **MAYOR GAP.** CC mucho más completo. | **P0** | ❌ |
| LMU-10 | Gap Messages | Voz por defecto, configurable, sector-based | UI-only, category=gaps silenciado, timer 30s | **GAP INTENCIONAL.** Silencio correcto para alpha. P1 futuro. | P1 | ❌ |
| LMU-11 | Brake Wear >80% | DamageLevel componentes, mensajes por rueda | % directo >80, edge-once, genérico | CC más granular (% → level). | P1 | ⚠️ |
| LMU-12 | Multiclass Warning | 8+ mensajes, distancia pista, nombre clase | gap time simple ±2s/1s, 2 mensajes | CC más rico en escenarios. | P1 | ⚠️ |
| LMU-13 | Penalty Detection | 20+ tipos, conteo 3/2/1, pit_now, cut_warn | num_penalties change, genérico | **MAYOR GAP.** Falta casi todo el sistema CC. | **P0** | ❌ |
| LMU-14 | Fuel Critical (<3 laps) | X_laps_fuel determinista, half_distance, pit_now | LLM streaming con finish-safe | CC tiene persistencia histórica, Vantare finish-safe. | P1 | ⚠️ |
| LMU-15 | Flags Monitor | FCY 6+ fases, sector yellows, local yellows, incident | transiciones básicas, commentary batch | **MAYOR GAP.** Sin FCY cycling, sin local yellows. | **P0** | ❌ |
| LMU-16 | Pit Window Opened | determinista con lap numbers | LLM streaming | Vantare usa LLM, CC datos concretos. | P2 | ⚠️ |
| LMU-17 | Pit Window Closing | determinista con lap countdown | LLM streaming | Igual que LMU-16. | P2 | ⚠️ |
| LMU-18 | Tyre Temperature | 3 niveles por rueda, brake temp separado | >105°C genérico | CC mucho más granular. | **P0** | ❌ |
| LMU-19 | Push Now | bestLap comparación, mensajes objetivo | undercut/laps<=3, LLM | **MAYOR GAP.** CC cálculo realista. | **P0** | ❌ |
| LMU-20 | Position Change | overtake detection, start quality, reminder | commentary batch, sin overtakes | **MAYOR GAP.** Sin adelantamientos. | **P0** | ❌ |
| LMU-21 | Lap Completion | corner names mid-point (inmediato) | commentary batch (delay 3-8s) | Delay Vantare en corner names. | P1 | ⚠️ |
| LMU-22 | Gap Update | sector-based randomness, delayed re-validate | timer 45s fijo, batch | CC más sofisticado (sector-based). | P1 | ❌ |
| LMU-23 | Race Start | good/bad/terrible según cambio posición | "vamos vamos" fijo + batch delay | Falta calidad de salida. | P1 | ❌ |
| LMU-24 | Pearls of Wisdom | slider 0-10, pearl asociado a position msg | max 2-4 fijo, silenciado en A0 | CC configurable, Vantare limitado. | P1 | ⚠️ |
| LMU-25 | Driver Swap | countdown 15/10/5/2 min, pit_this_lap | solo cambio driver_name | **MAYOR GAP.** Sin countdown. | **P0** | ❌ |
| LMU-26 | Competitor Pitted | pit entry/exit, watched opponents, gap | ±1 transición pits, LLM | CC watched opponents + exit. | P1 | ⚠️ |
| LMU-27 | Gap Closed | gap history → CLOSE status, being_pressured | threshold 1.5s, edge-once | CC historial de gaps vs threshold. | P2 | ⚠️ |
| LMU-28 | Session End | good/bad finish, rant, podium, disqualified | P+best lap, LLM | **MAYOR GAP.** Sin evaluación resultado. | **P0** | ❌ |
| LMU-29 | Engine Monitor | water+oil temp+pressure | engine_temp > 105 | Básico similar. | P2 | ⚠️ |
| LMU-30 | Weather Change | rain real-time, temp reports, ACC forecast | forecast rain_chance>30%, LLM DEEP | **MAYOR GAP.** Sin rain real-time, temp reports. | **P0** | ❌ |
| LMU-31 | Audio Priority System | 0-15 priority, bypass, channel beeps | binario IMMEDIATE/NORMAL | CC más granular | P2 | ⚠️ |
| LMU-32 | Sector Delta Reports | 30+ WAV combinados, frecuencia configurable | fuel_raw analysis cada 60s | CC completo, Vantare básico | P1 | ❌ |
| LMU-33 | **Critical Event Latency** | race_start/flags/damage SIEMPRE inmediatos | commentary batch 5-10s delay | **eventos críticos en batch** | **P0** | ❌ |
| LMU-34 | WatchedOpponents | voice commands, teammate/rival, delta times | evaluate_monitored_events | CC voice-driven, Vantare limitado | P1 | ❌ |
| LMU-35 | keepQuiet Mode | binario + allowImportantDuringSilence | SILENT 3 niveles | funcionalmente equivalentes | P2 | ✅ |
| LMU-36 | Grid Side Detection | getGridSide parrilla | NO IMPLEMENTADO | No existe en Vantare | P2 | ❌ |
| LMU-37 | SoundCache WAV | Cache 500 WAV, lazy loading, TTS fallback | TTS puro (Edge/Piper) | CC WAV + TTS; Vantare TTS siempre | P2 | ❌ |
| LMU-38 | Priority Queue 0-15 | 16 niveles, delayed callbacks, re-validate | binario IMMEDIATE/NORMAL | CC sistema completo; Vantare basico | P1 | ❌ |
| LMU-39 | Background Ambiance | Audio ambiente fondo separado | NO IMPLEMENTADO | Vantare no tiene | P2 | ❌ |
| LMU-40 | **FCY Spotter Cooldown** | Pausa spotter 10-30s durante SC | NO IMPLEMENTADO | Vantare continua proximity en SC | **P0** | ❌ |
| LMU-41 | Per-Class Message Types | Flags por clase (TYRE_TEMPS, etc) | NO IMPLEMENTADO | No critico para LMU | P2 | ❌ |
| LMU-42 | Condition-Aware Lap Times | 9 condiciones pista, buckets | NO IMPLEMENTADO | Afecta PushNow/GapClosed | P1 | ❌ |
| LMU-43 | Radio Beeps | beeps apertura/cierre canal | NO IMPLEMENTADO | Efecto inmersivo, no critico | P2 | ❌ |
| LMU-44 | Rants System | Mensajes humoristicos mal resultado | NO IMPLEMENTADO | Opcional | P2 | ❌ |
| LMU-45 | **Persisted Fuel History** | Consumo por coche/pista a JSON | HistoryStore basico | CC persiste entre sesiones | **P0** | ❌ |
| LMU-46 | NumberReader ML | Multi-lenguaje, precision auto | LLM decide formato | CC deterministico, Vantare LLM | P2 | ❌ |
| LMU-47 | Min Session Startup (6s) | Ignora datos primeros 6s | NO IMPLEMENTADO | Riesgo falsos positivos | P1 | ❌ |
| LMU-48 | **LMU REST Pit Write** | SetFuelLevel, SetTyreType via API | lmu_api.py read-only | CC escribe, Vantare solo lee | P1 | ❌ |

---

## Anti-patrones Vantare Actuales

### 1. Commentary batch mezclando eventos
Vantare usa `CommentaryOrchestrator` con debounce 3-8s para eventos que CC emite inmediatamente:
- `race_start` → CC inmediato priority 5, Vantare batch (delay 3-8s)
- `corner_names` → CC inmediato en mid-point, Vantare batch al completar vuelta
- `flags_yellow` → CC inmediato IMPORTANT_MESSAGE, Vantare batch
- `damage` → CC inmediato priority 15, Vantare batch (aunque tiene también alert inmediato)

**Fix:** Race start, daño severo y flags críticas deben ir por canal inmediato (alert IMMEDIATE priority), no commentary batch.

### 2. Periodic timers vs edge events CC
CC usa eventos *edge-driven* (transiciones detectadas). Vantare usa timers periódicos para:
- `gap_update` → timer 45s vs CC sector-based randomness
- `fuel` → timer 90s commentary + trigger 15s
- `engine_monitor` → timer 90s vs CC edge

**Fix:** Mantener edge para primera detección (ya implementado en triggers), usar timer solo para re-recordatorios.

### 3. Gaps constantes (fuel/position multi-report)
Aunque mitigado con finish-safe y edge-once:
- Fuel puede triple-reportar: spotter `<1`, trigger `<3`, commentary `<3`
- Position_change: commentary batch + pearls + proactive

**Fix:** Ya mitigado. Verificar en CI que no haya solapamiento.

### 4. position_change fuera de race
Ya parcialmente fixeado (solo race phase en proactive_monitors). CC también lo restringe a race.

**Fix:** Confirmar que todos los eventos de commentary verifican session type.

---

## Defaults CC a portar

| Propiedad CC | Default | Descripción | Archivo Vantare destino |
|-------------|---------|-------------|------------------------|
| `enable_gap_messages` | true | Gap messages con voz | `config.py` (nueva) + UI toggle |
| `frequency_of_gap_ahead_reports` | 5 (1-10) | Frecuencia reportes gap adelante | `spotter.py` `SPOTTER_GAP_FREQUENCY_S` |
| `enable_multiclass_messages` | true | Warnings multiclase | ya ALERT_ONLY |
| `enable_position_messages` | true | Mensajes de posición | ya en commentary |
| `enable_race_start_messages` | true | Mensajes de salida | no implementado |
| `enable_damage_messages` | true | Mensajes de daño | ya en spotter |
| `enable_brake_damage_messages` | true | Daño frenos separado | no (unificado) |
| `enable_suspension_damage_messages` | true | Daño suspensión separado | no (unificado) |
| `enable_crash_messages` | true | "are you OK" tras crash | no implementado |
| `enable_tyre_temp_warnings` | true | Temperatura neumaticos | ya trigger |
| `enable_tyre_wear_warnings` | true | Desgaste neumáticos | no implementado |
| `enable_brake_temp_warnings` | true | Temperatura frenos | no implementado |
| `enable_blue_flag_messages` | true | Bandera azul | no (FlagsMonitor tiene blue pero silenciado?) |
| `frequency_of_pearls_of_wisdom` | 5 (0-10) | Frecuencia perlas | `verbosity_controller.py` (max_pearls) |
| `maxComplaintsPerSession` | 60 | Máx quejas negativas/sesión | no implementado |
| `enable_session_end_messages` | true | Mensajes fin de sesión | ya trigger |
| `enable_fuel_messages` | true | Mensajes de combustible | ya triggers + commentary |
| `report_fuel_laps_left_in_timed_races` | false | Reportar vueltas en carreras crono | no implementado |
| `enable_engine_warnings` | true | Temperatura motor | ya commentary engine_monitor |
| `enable_opponent_crash_messages` | true | Crash de oponentes | no implementado |
| `spotter_gap_for_clear` | variable | Gap extra para mensaje clear | no (hysteresis en Vantare existe pero diferente) |
| `time_after_race_start_for_spotter` | 20 | Delay spotter tras salida | `SPOTTER_RACE_START_DELAY_S=20` ✅ |

---

## Reglas de Arquitectura Recomendadas

### Eventos Discretos vs Level-Held

| Tipo | Qué es | Canal CC | Canal Vantare Actual | Canal Recomendado |
|------|--------|----------|---------------------|-------------------|
| Discreto (edge, 1 vez) | Damage, Penalty, Overtake, FlagChange | IMPORTANT_MESSAGE inmediato | ALERT inmediato ✅ | ALERT inmediato |
| Level-held | Proximidad spotter | spotter TTS hold-repeat | IMMEDIATE hold-repeat ✅ | IMMEDIATE |
| Batch (varios eventos) | Position change, gap update, fuel | TTS position (immediate) + gap (sector) | commentary batch (debounce) | **Inmediato** para race_start, daño, overtake. Batch para info general. |

### Spotter @ 20Hz vs Ingeniero @ 0.5Hz

- **Spotter (20Hz):** Proximidad, limiter, fuel <1, última vuelta, damage impacto, SC/FCY.
- **Ingeniero (0.5Hz):** Triggers (<3 fuel, penalties, multiclass, etc.), commentary batch, pearls.
- **Qué NUNCA debe ir en commentary batch:** race_start, damage crítico, SC/FCY green transition, overtake completado, penalty pit_now. Estos deben ser alert inmediato.

### Practice / Qualifying / Race — Tabla de Silenciamiento CC

| Módulo | Practice | Qualifying | Race | Notas |
|--------|----------|------------|------|-------|
| Spotter lateral | ✅ (si spotter on) | ❌ (default off) | ✅ | `spotterOffQualifying` / `enable_spotter_in_timetrial` |
| Gaps | ✅ | ❌ | ✅ | solo race |
| Fuel | ❌ (onLowFuelRun) | ❌ (onLowFuelRun) | ✅ | CC asume low fuel en prac/qual |
| Position | ✅ | ✅ | ✅ | siempre |
| Damage | ✅ | ✅ | ✅ | siempre |
| Flags | ✅ | ❌ | ✅ | CC no flags en qual |
| Pearls | ❌ | ❌ | ✅ | solo race |
| Push Now | ❌ | ❌ | ✅ | solo race |
| Engine Monitor | ❌ | ❌ | ✅ | solo race |

### Cuándo CC usa LLM/texto variable vs frase determinista

**CC nunca usa LLM.** Todo el contenido de CC es:
1. WAV pre-grabados (spotter, position, fuel, damage, flags)
2. Números leídos vía NumberReader (gap times, laps, posiciones, temperaturas)
3. Texto compuesto por MessageFragment concatenado

**Vantare usa LLM para:** FuelCritical, FlagsMonitor, PitWindow, GapClosed, PushNow, SessionEnd, WeatherChange, PilotQuestion.
**Vantare usa determinista para:** Spotter proximity, damage alerts, brake wear, multiclass, penalty, tyre temp, commentary batch (LLM format) + pearls (pool).

**Decisión:** Mantener LLM para consejo estratégico (es el valor diferencial de Vantare), pero usar determinista para urgencias (fuel crítico spotter, damage impacto, penalty pit_now, flag changes críticas).

---

## Verificaciones CI Existentes por Fila

| ID | Test CI | Estado |
|----|---------|--------|
| LMU-01 | `test_spotter_cc_parity` | ✅ |
| LMU-02 | `test_spotter_state` | ✅ |
| LMU-03 | `test_spotter_state (3-wide)` | ✅ |
| LMU-04 | `test_spotter (limiter)` | ✅ |
| LMU-05 | `test_spotter (limiter exit)` | ✅ |
| LMU-06 | `test_fuel_safety` | ✅ |
| LMU-07 | `test_spotter (sc)` | ✅ |
| LMU-08 | `test_spotter (last lap)` | ✅ |
| LMU-09 | `test_spotter (damage)` | ✅ |
| LMU-10 | `alertVoice.test (gaps no voice)` | ✅ |
| LMU-11 | `test_audio_trigger_matrix (brakes)` | ✅ |
| LMU-12 | `test_audio_trigger_matrix (multiclass)` | ✅ |
| LMU-13 | `test_audio_trigger_matrix (penalty)` | ✅ |
| LMU-14 | `test_audio_trigger_matrix (fuel)` | ✅ |
| LMU-15 | `test_spotter (sc)` | ✅ |
| LMU-16 | `test_audio_trigger_matrix (pit window)` | ✅ |
| LMU-17-30 | Tests parciales | ⚠️ |

---

*Generado por Sisyphus — Jun 2026. Fuentes: CC GitLab main, Vantare código fuente + tests.*
