---
generated: 2026-06-07
sources: [LMU/shared-memory.md, LMU/rest-api.md, shared-telemetry/pyLMUSharedMemory/lmu_data.py, backend/src/services/lmu_api.py, backend/src/services/strategy_service.py]
scope: annex-only (no full matrix rewrite)
---

# Anexo 1: Disponibilidad de Datos LMU para Implementación P0

## 1. Resumen Ejecutivo

| Campo / Dato | ¿Disponible LMU? | Fuente | Campo exacto | P0 IDs que lo necesitan | Fallback Vantare si NO |
|---|---|---|---|---|---|
| `mDentSeverity[8]` | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mDentSeverity` (c_ubyte[8], 0-2) | LMU-09 | Usar average como `damage_aero` (ya implementado) |
| `mLastImpactET` | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mLastImpactET` | LMU-09 | Ya implementado en spotter._eval_damage |
| `mLastImpactMagnitude` | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mLastImpactMagnitude` | LMU-09 | Ya implementado (threshold 25) |
| `mDetached` (piezas carrocería) | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mDetached` | LMU-09 | Ya implementado en damage_report.py |
| Desglose daño por componente (engine, tranny, aero, susp, brakes) | ❌ NO | No disponible | LMU no expone damage desglosado. Solo `mDentSeverity[8]` (8 ubicaciones carrocería, 0-2) y REST body.aero (0.0-1.0) | LMU-09 | Usar dent severity + REST aero. NO hay engine/tranny/suspension damage separado en LMU |
| Presión neumáticos (tyre_pressure) | ✅ SI | Shared memory | `lmu_data.py:LMUWheel.mPressure` (c_double, kPa) | LMU-09 | Puncture vía `mFlat` (c_bool) |
| `mFlat` (puncture detection) | ✅ SI | Shared memory | `lmu_data.py:LMUWheel.mFlat` (c_bool) | LMU-09 | Umbral presión alternativo si mFlat no es fiable |
| Deceleración / crash G | ✅ SI (derivable) | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mLocalAccel` (LMUVect3, m/s²). Magnitud = sqrt(x²+y²+z²). 40G = 392 m/s² | LMU-09 | Calcular desde cambio de velocidad entre ticks (fallback) |
| `num_penalties` (conteo) | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleScoring.mNumPenalties` (c_short) | LMU-13 | Ya implementado en PenaltyMonitorTrigger |
| Tipo penalización (drive-through, stop-go, time) | ❌ NO | No disponible | LMU no expone tipo. Solo conteo de pendientes | LMU-13 | Mensaje genérico "Penalización asignada" sin tipo. No se puede diferenciar DT vs SG |
| Vueltas restantes para servir penalización | ❌ NO | No disponible | No existe en shared memory ni REST | LMU-13 | Implementar conteo interno: cuando num_penalties sube, contar vueltas hasta que baja |
| Cut track warnings | ❓ UNKNOWN | Shared memory? | `mTrackLimitsSteps` (c_uint8) en telemetry. REST no parece exponer track limits | LMU-13 | Verificar si mTrackLimitsSteps cambia con cuts. Si no, omitir cut track warnings |
| `mRaining` (lluvia real-time) | ✅ SI | Shared memory | `lmu_data.py:LMUScoringInfo.mRaining` (c_double, 0.0-1.0) | LMU-30 | Ya disponible a 20Hz. No es forecast, es lluvia actual |
| `driver_stint_seconds_remaining` | ❌ NO | No disponible | No existe en shared memory. REST API no documenta stint data | LMU-25 | Mantener detección por cambio de driver_name (implementado). Sin countdown |
| `standing_position` inicial (session start) | ✅ SI (derivable) | Shared memory | `mPlace` en primer tick de sesión. No hay campo "start position" separado | LMU-28 | Capturar mPlace en el primer tick con gamePhase=5 como "start position" |
| `mGamePhase` / fases FCY | ✅ SI | Shared memory | `lmu_data.py:LMUScoringInfo.mGamePhase` (c_ubyte, 0-9). `mYellowFlagState` (c_char, -1 a 7) para subfases | LMU-15 | mGamePhase=6 + mYellowFlagState da PITS_CLOSED/PITS_OPEN/LAST_LAP/GREEN |
| Sector yellow / local yellow flags | ✅ SI | Shared memory | `lmu_data.py:LMUScoringInfo.mSectorFlag` (c_ubyte[3]) | LMU-15 | Ya parcialmente en flags_monitor.py |
| `mTimeGapCarAhead/Behind` | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mTimeGapCarAhead` (c_float), `mTimeGapCarBehind` (c_float) | Múltiples | Ya implementado en strategy_service.py |
| `mTimeGapPlaceAhead/Behind` | ✅ SI | Shared memory | `lmu_data.py:LMUVehicleTelemetry.mTimeGapPlaceAhead` (c_float), `mTimeGapPlaceBehind` (c_float) | Múltiples | Ya implementado |
| Opponent `best_lap_time` | ✅ SI | Shared memory (scoring) | `lmu_data.py:LMUVehicleScoring.mBestLapTime` (c_double) | Múltiples | Ya en CompetitorTelemetry |
| Opponent `last_lap_time` | ✅ SI | Shared memory (scoring) | `lmu_data.py:LMUVehicleScoring.mLastLapTime` (c_double) | LMU-20 | Ya en CompetitorTelemetry |
| Brake wear (pastillas) | ✅ SI (REST only) | REST API (`/rest/garage/UIScreen/RepairAndRefuel`) | `wearables.brakes[4]` float 0.0-1.0, cada 3s | LMU-11 | NO en shared memory. Sidecar NO accede a REST (brake_wear=0.0). Backend sí |
| Suspension wear | ✅ SI (REST only) | REST API | `wearables.suspension[4]` float 0.0-1.0 | LMU-09 | No disponible en shared memory ni sidecar |
| Aero damage | ✅ SI (REST only) | REST API | `wearables.body.aero` float 0.0-1.0 | LMU-09 | Dent severity como fallback (ya implementado) |
| Temperatura frenos | ✅ SI | Shared memory | `lmu_data.py:LMUWheel.mBrakeTemp` (c_double, Celsius) | LMU-18 | Ya disponible. No usado actualmente en triggers |
| Presión neumáticos (todas 4) | ✅ SI | Shared memory | `lmu_data.py:LMUWheel.mPressure` (c_double, kPa) | LMU-09 | No usado actualmente |
| Temperatura neumáticos | ✅ SI | Shared memory | `mTemperature[3]` (Kelvin, -273.15) y `mTireCarcassTemperature` (Kelvin) | LMU-18 | Ya en TelemetryFrame como tyre_temp_fl/fr/rl/rr |
| Desgaste neumáticos | ✅ SI | Shared memory | `mWear` (c_double, 0.0-1.0) | LMU-18 | Ya en TelemetryFrame como tyre_wear_* |
| Nivel de combustible oponentes | ✅ SI | Shared memory | `mFuelFraction` (c_ubyte, 0x00-0xFF) en scoring | LMU-26 | Ya en CompetitorTelemetry.fuel_capacity_fraction |
| Velocidad oponentes | ✅ SI | Shared memory | `mLocalVel` (LMUVect3) tanto en scoring como telemetry | LMU-26 | Ya en CompetitorTelemetry.speed |
| Posición mundial oponentes | ✅ SI | Shared memory | `mPos` (LMUVect3) en scoring | LMU-01 a LMU-03 | Ya usado por cartesian_spotter |

## 2. Detalle por P0 Bloqueado por Datos

```yaml
p0_id: LMU-09
dato_requerido: tyre_pressure FL para puncture
disponible: YES
evidencia_lmu: "lmu_data.py:LMUWheel.mPressure línea 58, mFlat línea 63"
evidencia_cc: "DamageReporting.cs:getPuncture() usa tyreData.FrontLeftPressure < punctureThreshold (30)"
fallback_vantare: "Usar mFlat flag directamente en vez de umbral presión"
implementable_sin_fallback: true
---
p0_id: LMU-09
dato_requerido: Desglose daño 5 componentes (engine, tranny, aero, suspension, brakes)
disponible: PARTIAL
evidencia_lmu: "Solo mDentSeverity[8] (carrocería, 8 ubicaciones 0-2) + REST body.aero + REST suspension[4] + REST brakes[4]"
evidencia_cc: "DamageReporting.cs usa GameStateData.CarDamageData con OverallEngineDamage, OverallTransmissionDamage, OverallAeroDamage, SuspensionDamageStatus, BrakeDamageStatus — LMU NO expone estos campos"
fallback_vantare: "Implementar con datos disponibles: DentSeverity→aero, REST suspension, REST brakes. Omitir engine y tranny damage. Mensaje: 'Daño en carrocería' + 'frenos al X%' + 'suspensión al X%'"
implementable_sin_fallback: true
---
p0_id: LMU-09
dato_requerido: Deceleración >40G para crash detection
disponible: YES
evidencia_lmu: "lmu_data.py:LMUVehicleTelemetry.mLocalAccel línea 93 (LMUVect3, m/s²). Magnitud sqrt(x²+y²+z²). 40G=392m/s²"
evidencia_cc: "DamageReporting.cs calcula acceleration = abs(currentSpeed - previousSpeed) / interval. Si >400 m/s² considera dangerous impact"
fallback_vantare: "Calcular desde cambio de mLocalVel entre ticks (como CC)"
implementable_sin_fallback: true
---
p0_id: LMU-13
dato_requerido: Tipo de penalización (drive-through, stop-go, time)
disponible: NO
evidencia_lmu: "Solo mNumPenalties (c_short) en scoring. No hay campo de tipo. REST API no documenta endpoint de penalties"
evidencia_cc: "Penalties.cs usa currentGameState.PenaltiesData.HasDriveThrough, HasStopAndGo, HasTimeDeduction — datos que LMU NO expone"
fallback_vantare: "Mensaje genérico sin tipo. Conteo regresivo de vueltas para servir funciona igual"
implementable_sin_fallback: true
---
p0_id: LMU-13
dato_requerido: Cut track warnings
disponible: UNKNOWN
evidencia_lmu: "mTrackLimitsSteps (c_uint8) en telemetry. No sabemos si incrementa con cuts. Habría que verificar en pista"
evidencia_cc: "Penalties.cs usa currentGameState.PenaltiesData.CutTrackWarnings"
fallback_vantare: "Si mTrackLimitsSteps no funciona, implementar detección propia: invalid lap consecutiva = posible cut"
implementable_sin_fallback: true
---
p0_id: LMU-15
dato_requerido: FCY phase tracking (pits closed, pits open, etc.)
disponible: YES
evidencia_lmu: "lmu_data.py:LMUScoringInfo.mYellowFlagState línea 301 (c_char). Valores: -1=invalid, 0=none, 1=pending, 2=pits_closed, 3=pit_lead_lap, 4=pits_open, 5=last_lap, 6=resume, 7=race_halt"
evidencia_cc: "FlagsMonitor.cs usa currentGameState.FlagData.fcyPhase (FullCourseYellowPhase enum: PITS_CLOSED, PITS_OPEN, etc.)"
fallback_vantare: "Ya hay mGamePhase==6 para detectar FCY. Añadir mYellowFlagState para subfases"
implementable_sin_fallback: true
---
p0_id: LMU-18
dato_requerido: Tyre temperature por rueda
disponible: YES
evidencia_lmu: "lmu_data.py:LMUWheel.mTemperature[3] línea 59 (Kelvin, 3 zonas). mTireCarcassTemperature línea 69 (Kelvin promedio). mBrakeTemp línea 46 (Celsius)"
evidencia_cc: "TyreMonitor.cs usa tyreData LF/RF/LR/RR con thresholds Hot/Cooking"
fallback_vantare: "Ya en TelemetryFrame como tyre_temp_fl/fr/rl/rr (carcass temp en °C)"
implementable_sin_fallback: true
---
p0_id: LMU-19
dato_requerido: Opponent best lap time para PushNow calculation
disponible: YES
evidencia_lmu: "lmu_data.py:LMUVehicleScoring.mBestLapTime línea 214 (c_double). Ya en CompetitorTelemetry.best_lap"
evidencia_cc: "PushNow.cs:getOpponentBestLap() usa opponent.CurrentBestLapTime"
fallback_vantare: "Ya disponible. Solo falta implementar comparación en PushNowTrigger"
implementable_sin_fallback: true
---
p0_id: LMU-20
dato_requerido: Opponent key delante/detrás para overtake detection
disponible: YES
evidencia_lmu: "mTimeGapPlaceAhead/Behind + mPlace + vehScoringInfo IDs. mLastLapTime para confirmar pass"
evidencia_cc: "Position.cs:checkForNewOvertakes() monitorea currentOpponentAheadKey vs opponentAheadKey + gapsAhead samples"
fallback_vantare: "Usar competitor list con standing_position para detectar cambios de orden"
implementable_sin_fallback: true
---
p0_id: LMU-25
dato_requerido: driver_stint_seconds_remaining
disponible: NO
evidencia_lmu: "No existe en shared memory (no hay campo de stint time en LMUVehicleScoring ni LMUVehicleTelemetry). REST API no documenta"
evidencia_cc: "DriverSwaps.cs usa currentGameState.PitData.DriverStintSecondsRemaining"
fallback_vantare: "Solo nombre cambia. Sin countdown. Mensaje: 'Cambio de piloto — {name}'"
implementable_sin_fallback: false
---
p0_id: LMU-30
dato_requerido: Rain intensity en tiempo real
disponible: YES
evidencia_lmu: "lmu_data.py:LMUScoringInfo.mRaining línea 309 (c_double, 0.0-1.0). Actualizado a 20Hz"
evidencia_cc: "ConditionsMonitor.cs usa currentConditions.RainDensity con niveles DRIZZLE(0.01-0.15), LIGHT(0.15-0.3), MID(0.3-0.6), HEAVY(0.6-0.75), STORM(>0.75)"
fallback_vantare: "Ya disponible. Solo falta trigger edge-once por nivel"
implementable_sin_fallback: true
---
p0_id: LMU-33 (race_start)
dato_requerido: Start position para evaluar calidad de salida
disponible: YES (derivable)
evidencia_lmu: "mPlace en primer tick con gamePhase==5. mPlace segundo tick para ver cambio"
evidencia_cc: "Position.cs usa currentGameState.SessionData.SessionStartClassPosition"
fallback_vantare: "Capturar mPlace al entrar en gamePhase 5 como start_position"
implementable_sin_fallback: true
---
p0_id: LMU-40 (FCY spotter cooldown)
dato_requerido: gamePhase para detectar FCY inicio/fin
disponible: YES
evidencia_lmu: "lmu_data.py:LMUScoringInfo.mGamePhase línea 290 (c_ubyte). 6=FCY/SC, 5=green, 8=session over"
evidencia_cc: "CrewChief.cs usa game_phase==6 para gestionar spotter pause"
fallback_vantare: "Ya disponible en tick. Solo falta lógica de cooldown en spotter"
implementable_sin_fallback: true
---
p0_id: LMU-45 (fuel persistence)
dato_requerido: Fuel used per lap para persistir
disponible: YES
evidencia_lmu: "mFuel (c_double, litros) en telemetry. Diferencia entre laps = consumo"
evidencia_cc: "Fuel.cs calcula lap_used = amount_start - currentFuel"
fallback_vantare: "Ya calculado en strategy_service._lap_fuel_start. Solo falta persistencia a JSON"
implementable_sin_fallback: true
---
p0_id: LMU-48 (REST API pit write)
dato_requerido: REST API write endpoints
disponible: YES (read)
evidencia_lmu: "rest-api.md documenta 3 endpoints read-only. CC escribe a /rest/garage/PitMenu/ (LMUPitMenuAPI.cs). Vantare no escribe"
evidencia_cc: "LMUPitMenuAPI.cs:SetFuelLevel(), SetTyreType(), SetVirtualEnergy() via POST"
fallback_vantare: "Solo lectura. Escritura fuera de scope alpha (PitManager voz)"
implementable_sin_fallback: true
```

## 3. Recomendación

### P0 implementables YA (datos LMU verificados)
| P0 | Datos necesarios | Estado LMU |
|----|-----------------|------------|
| LMU-09 | Puncture, crash G, damage parcial | ✅ Datos disponibles (mFlat, mLocalAccel, mDentSeverity) |
| LMU-15 | FCY fases | ✅ mYellowFlagState da 7 subfases |
| LMU-13 | Conteo regresivo penalizaciones | ⚠️ Sin tipo de penalty, pero conteo funciona con mNumPenalties |
| LMU-20 | Overtake detection | ✅ mPlace + competitor list |
| LMU-30 | Rain real-time | ✅ mRaining 20Hz |
| LMU-33 | race_start + latencia crítica | ✅ No requiere nuevos datos |
| LMU-40 | FCY spotter cooldown | ✅ gamePhase disponible |
| LMU-45 | Fuel persistence | ✅ mFuel disponible |

### P0 condicionados (requieren verificación en pista)
| P0 | Condición |
|----|-----------|
| LMU-13 (cut track) | Verificar si mTrackLimitsSteps funciona |
| LMU-18 (brake temp) | mBrakeTemp disponible pero falta probar en pista |
| LMU-19 (push now best lap) | mBestLapTime disponible, falta comparación |

### P0 pospuestos por datos
| P0 | Motivo |
|----|--------|
| LMU-25 (stint countdown) | ❌ LMU no expone driver_stint_seconds_remaining |
| LMU-48 (REST write) | ❌ Scope OUT de alpha (PitManager voz) |
| LMU-09 (engine/tranny damage) | ❌ LMU no tiene damage desglosado |
