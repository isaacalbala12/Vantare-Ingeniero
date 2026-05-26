# LMU Shared Memory — Especificación Completa

> Fuente: `shared-telemetry/shared_telemetry/pyLMUSharedMemory/lmu_data.py`
> Basado en: `SharedMemoryInterface.hpp` de S397 (LMU), `pyRfactor2SharedMemory` de Tony Whitley

## Estructura General

```
LMUObjectOut
├── generic        → LMUGeneric (eventos, versión, FFB, appInfo)
├── paths          → LMUPathData (rutas de archivos)
├── scoring        → LMUScoringData
│   ├── scoringInfo      → LMUScoringInfo (sesión, clima, estado global)
│   ├── vehScoringInfo   → LMUVehicleScoring[104] (datos de todos los vehículos)
│   └── scoringStream    → char[65536] (stream de resultados)
└── telemetry      → LMUTelemetryData
    ├── activeVehicles   → uint8
    ├── playerVehicleIdx → uint8
    ├── playerHasVehicle → bool
    └── telemInfo        → LMUVehicleTelemetry[104] (telemetría detallada)
```

---

## 1. LMUVect3 (vector 3D)

| Campo | Tipo | Descripción |
|-------|------|-------------|
| x | c_double | Coordenada X |
| y | c_double | Coordenada Y |
| z | c_double | Coordenada Z |

---

## 2. LMUWheel (información por rueda) — 4 por vehículo

| Campo | Tipo | Rango | Descripción |
|-------|------|-------|-------------|
| mSuspensionDeflection | c_double | — | Deflexión suspensión (metros) |
| mRideHeight | c_double | — | Altura de conducción (metros) |
| mSuspForce | c_double | — | Carga en la suspensión (Newtons) |
| **mBrakeTemp** | **c_double** | **°C** | **Temperatura de disco de freno** |
| **mBrakePressure** | **c_double** | **0.0-1.0** | **Presión de freno (eventualmente kPa)** |
| mRotation | c_double | rad/s | Velocidad de rotación |
| mLateralPatchVel | c_double | — | Velocidad lateral del parche de contacto |
| mLongitudinalPatchVel | c_double | — | Velocidad longitudinal del parche de contacto |
| mLateralGroundVel | c_double | — | Velocidad lateral respecto al suelo |
| mLongitudinalGroundVel | c_double | — | Velocidad longitudinal respecto al suelo |
| mCamber | c_double | rad | Ángulo de caída |
| mLateralForce | c_double | N | Fuerza lateral |
| mLongitudinalForce | c_double | N | Fuerza longitudinal |
| mTireLoad | c_double | N | Carga vertical sobre el neumático |
| mGripFract | c_double | 0.0-1.0 | Fracción de la zona de contacto deslizando |
| **mPressure** | **c_double** | **kPa** | **Presión de neumático** |
| **mTemperature** | **c_double[3]** | **Kelvin** | **Temp. izquierda/centro/derecha** (restar 273.15 → °C) |
| **mWear** | **c_double** | **0.0-1.0** | **Desgaste (fracción del máximo, NO necesariamente proporcional a pérdida de agarre)** |
| mTerrainName | c_char[16] | — | Prefijo de material TDF |
| mSurfaceType | c_ubyte | 0-6 | 0=seco, 1=mojado, 2=hierba, 3=tierra, 4=grava, 5=vibrador, 6=especial |
| mFlat | c_bool | — | Neumático pinchado |
| mDetached | c_bool | — | Rueda desprendida |
| mStaticUndeflectedRadius | c_ubyte | cm | Radio estático del neumático |
| mVerticalTireDeflection | c_double | — | Deflexión vertical del neumático |
| mWheelYLocation | c_double | — | Posición Y de la rueda respecto al vehículo |
| mToe | c_double | rad | Ángulo de convergencia actual |
| mTireCarcassTemperature | c_double | Kelvin | Temperatura promedio de la carcasa |
| mTireInnerLayerTemperature | c_double[3] | Kelvin | Temperatura capa interna (3 zonas) |
| mOptimalTemp | c_float | °C | Temperatura óptima del neumático |
| mCompoundIndex | c_ubyte | — | Índice del compuesto actual |
| **mCompoundType** | **c_ubyte** | **0-3** | **0=Soft, 1=Medium, 2=Hard, 3=Wet** |

---

## 3. LMUVehicleScoring (scoring por vehículo) — 104 vehículos máximo

| Campo | Tipo | Rango | Descripción | Uso en ticker |
|-------|------|-------|-------------|:---:|
| **mID** | c_int | — | Slot ID (se reusa en MP si alguien se va) | — |
| **mDriverName** | **c_char[32]** | — | **Nombre del piloto** | **RIV** |
| mVehicleName | c_char[64] | — | Nombre del coche | — |
| **mTotalLaps** | **c_short** | — | **Vueltas completadas** | **RIV** |
| mSector | c_byte | 0-2 | 0=sector3, 1=sector1, 2=sector2 | — |
| mFinishStatus | c_byte | 0-3 | 0=none, 1=finished, 2=dnf, 3=dq | — |
| mLapDist | c_double | — | Distancia actual en vuelta (metros) | — |
| mPathLateral | c_double | — | Posición lateral respecto a trazada "centro" | — |
| mTrackEdge | c_double | — | Borde de pista | — |
| mBestSector1 | c_double | s | Mejor sector 1 | — |
| mBestSector2 | c_double | s | Mejor sector 2 (incluye S1) | — |
| **mBestLapTime** | **c_double** | **s** | **Mejor tiempo de vuelta** | **GAP** |
| mLastSector1 | c_double | s | Último sector 1 | — |
| mLastSector2 | c_double | s | Último sector 2 | — |
| **mLastLapTime** | **c_double** | **s** | **Último tiempo de vuelta** | **GAP** |
| mCurSector1 | c_double | s | Sector 1 actual | — |
| mCurSector2 | c_double | s | Sector 2 actual | — |
| **mNumPitstops** | **c_short** | — | **Número de paradas en boxes** | — |
| mNumPenalties | c_short | — | Penalizaciones pendientes | — |
| **mIsPlayer** | **c_bool** | — | **¿Es el jugador local?** | — |
| mControl | c_byte | -1 a 3 | -1=nadie, 0=local, 1=AI, 2=remoto, 3=replay | — |
| **mInPits** | **c_bool** | — | **¿Entre entrada y salida de pits?** | — |
| **mPlace** | **c_ubyte** | **1-based** | **Posición en pista** | **DRV** |
| **mVehicleClass** | **c_char[32]** | — | **Clase del vehículo (Hypercar, GT3, etc.)** | **RIV** |
| mTimeBehindNext | c_double | s | Tiempo detrás del siguiente | — |
| mLapsBehindNext | c_int | — | Vueltas perdidas respecto al siguiente | — |
| **mTimeBehindLeader** | **c_double** | **s** | **Tiempo detrás del líder** | — |
| mLapsBehindLeader | c_int | — | Vueltas perdidas respecto al líder | — |
| mLapStartET | c_double | s | Tiempo de inicio de vuelta | — |
| mPos | LMUVect3 | — | Posición mundial (metros) | — |
| mLocalVel | LMUVect3 | — | Velocidad local (m/s) | — |
| mLocalAccel | LMUVect3 | — | Aceleración local (m/s²) | — |
| mHeadlights | c_ubyte | — | Estado faros | — |
| **mPitState** | **c_ubyte** | **0-4** | **0=none, 1=request, 2=entering, 3=stopped, 4=exiting** | **PIT** |
| mServerScored | c_ubyte | — | ¿Scoring por servidor? | — |
| mIndividualPhase | c_ubyte | — | Fase individual | — |
| mQualification | c_int | — | Posición clasificación (1-based) | — |
| mTimeIntoLap | c_double | s | Tiempo estimado en vuelta actual | — |
| mEstimatedLapTime | c_double | s | Tiempo estimado de vuelta | — |
| **mPitGroup** | **c_char[24]** | — | **Equipo/grupo de pits** | **RIV** (extra) |
| mFlag | c_ubyte | 0,6 | Bandera mostrada al vehículo (0=verde, 6=azul) | — |
| mUnderYellow | c_bool | — | ¿Ha pasado bajo bandera amarilla? | — |
| mInGarageStall | c_bool | — | ¿En plaza de garaje correcta? | — |
| **mSteamID** | **c_ulonglong** | — | **SteamID del piloto actual** | — |
| **mFuelFraction** | **c_ubyte** | **0x00-0xFF** | **Combustible restante (%)** | **DRV** (fallback) |
| **mDRSState** | **c_bool** | — | **¿DRS activo?** | **DRS** |

### PitState (mPitState)

| Valor | Estado |
|:-----:|--------|
| 0 | Ninguno |
| 1 | Solicitado |
| 2 | Entrando |
| 3 | Detenido |
| 4 | Saliendo |

---

## 4. LMUVehicleTelemetry (telemetría por vehículo) — 104 vehículos máximo

| Campo | Tipo | Rango | Descripción | Uso en ticker |
|-------|------|-------|-------------|:---:|
| mID | c_int | — | Slot ID (se reusa en MP) | — |
| mDeltaTime | c_double | s | Tiempo desde último update | — |
| mElapsedTime | c_double | s | Tiempo de sesión transcurrido | — |
| **mLapNumber** | **c_int** | — | **Vuelta actual** | **DRV** |
| **mVehicleName** | **c_char[64]** | — | **Nombre del vehículo** | — |
| mTrackName | c_char[64] | — | Nombre del circuito | — |
| mPos | LMUVect3 | — | Posición mundial (metros) | — |
| **mLocalVel** | **LMUVect3** | — | **Velocidad local (m/s)** | **S** (magnitud) |
| mGear | c_int | -1 a N | -1=R, 0=N, 1+=marchas | — |
| mEngineRPM | c_double | — | RPM del motor | — |
| mEngineWaterTemp | c_double | °C | Temperatura agua | — |
| mEngineOilTemp | c_double | °C | Temperatura aceite | — |
| mFilteredThrottle | c_double | 0.0-1.0 | Acelerador filtrado | — |
| mFilteredBrake | c_double | 0.0-1.0 | Freno filtrado | — |
| **mFuel** | **c_double** | **L** | **Combustible en tanque** | **DRV** |
| mEngineMaxRPM | c_double | — | Límite de revoluciones | — |
| mScheduledStops | c_ubyte | — | Paradas programadas | — |
| mDentSeverity | c_ubyte[8] | 0-2 | Severidad abolladura (8 ubicaciones) | **D** (promedio) |
| mLastImpactMagnitude | c_double | N | Magnitud último impacto | — |
| mEngineTorque | c_double | Nm | Torque motor actual | — |
| **mRearFlapActivated** | **c_ubyte** | **0-1** | **¿Alerón trasero activado? (DRS)** | **DRS** |
| **mFuelCapacity** | **c_double** | **L** | **Capacidad del tanque** | — |
| **mBatteryChargeFraction** | **c_double** | **0.0-1.0** | **Carga de batería** | **BAT** |
| mElectricBoostMotorState | c_ubyte | 0-3 | 0=no disp, 1=inactivo, 2=propulsión, 3=regeneración | — |
| mStateOfCharge | c_float | % | Estado de carga batería | **BAT** |
| mRegen | c_float | kW | Potencia de regeneración | — |
| **mTimeGapPlaceAhead** | **c_float** | **s** | **Gap con el de adelante (por posición)** | **GAP** |
| **mTimeGapPlaceBehind** | **c_float** | **s** | **Gap con el de atrás (por posición)** | **GAP** |
| mVehicleModel | c_char[30] | — | Marca y modelo | — |
| mVehicleClass | c_uint8 | — | Clase (índice numérico) | — |
| **mWheels** | **LMUWheel[4]** | — | **Info de las 4 ruedas** | **TYR, BRK** |

**Nota importante sobre brake wear:** La shared memory NO expone desgaste de pastillas de freno. `mBrakeTemp` y `mBrakePressure` sí están disponibles, pero el desgaste de frenos se obtiene exclusivamente vía REST API (`/rest/garage/UIScreen/RepairAndRefuel`). Ver `rest-api.md`.

---

## 5. LMUScoringInfo (información global de sesión)

| Campo | Tipo | Rango | Descripción | Uso en ticker |
|-------|------|-------|-------------|:---:|
| mTrackName | c_char[64] | — | Nombre del circuito | — |
| **mSession** | **c_int** | **0-13** | **Tipo de sesión (ver enum abajo)** | **SES** |
| mCurrentET | c_double | s | Tiempo actual de sesión | — |
| mEndET | c_double | s | Tiempo final de sesión | — |
| **mMaxLaps** | **c_int** | — | **Vueltas máximas (0=por tiempo)** | **SES** |
| mLapDist | c_double | m | Longitud del circuito | — |
| **mNumVehicles** | **c_int** | **0-104** | **Número de vehículos en pista** | **RIV** |
| **mGamePhase** | **c_ubyte** | **0-9** | **Fase de juego (ver enum abajo)** | **SES** |
| mYellowFlagState | c_char | -1 a 7 | Estado FCY (ver enum en lmu_enum.py) | — |
| mSectorFlag | c_ubyte[3] | — | Bandera amarilla por sector | **YF** |
| mDarkCloud | c_double | 0.0-1.0 | Nubosidad | — |
| **mRaining** | **c_double** | **0.0-1.0** | **Intensidad de lluvia** | **WTH** |
| **mAmbientTemp** | **c_double** | **°C** | **Temperatura ambiente** | **WTH** |
| **mTrackTemp** | **c_double** | **°C** | **Temperatura pista** | **WTH** |
| mWind | LMUVect3 | — | Velocidad del viento | — |
| **mMinPathWetness** | **c_double** | **0.0-1.0** | **Mojado mínimo trazada** | **WET** |
| **mMaxPathWetness** | **c_double** | **0.0-1.0** | **Mojado máximo trazada** | **WET** |
| **mAvgPathWetness** | **c_double** | **0.0-1.0** | **Mojado promedio trazada** | **WET** |
| **mSessionTimeRemaining** | **c_float** | **s** | **Tiempo restante de sesión** | **SES** |
| mTimeOfDay | c_float | h | Hora del día en simulación | — |
| **mTrackGripLevel** | **c_uint8** | **0-4** | **Nivel de agarre pista** | **WTH** |
| **mCloudCoverage** | **c_uint8** | **0-10** | **Cobertura nubes (0=clear, 10=storm)** | **WTH** |

### GamePhase (mGamePhase)

| Valor | Estado |
|:-----:|--------|
| 0 | Antes de comenzar la sesión |
| 1 | Vueltas de reconocimiento (race only) |
| 2 | Grid walk-through (race only) |
| 3 | Vuelta de formación (race only) |
| 4 | Countdown de salida (race only) |
| 5 | **Bandera verde** |
| 6 | **FCY / Safety Car** |
| 7 | Sesión detenida |
| 8 | **Sesión terminada** |
| 9 | Pausa / Heartbeat |

### SessionType (mSession)

| Valor | Tipo |
|:-----:|------|
| 0 | Test Day |
| 1-4 | Practice 1-4 |
| 5-8 | Qualifying 1-4 |
| 9 | Warmup |
| 10-13 | Race 1-4 |

### TrackGripLevel (mTrackGripLevel)

| Valor | Abreviatura | Descripción |
|:-----:|:-----------:|-------------|
| 0 | GRN | Green (nuevo) |
| 1 | LOW | Low (poco agarre) |
| 2 | MED | Medium |
| 3 | HIG | High (heavy) |
| 4 | SAT | Saturated (saturado) |

### CloudCoverage (mCloudCoverage)

| Valor | Descripción |
|:-----:|-------------|
| 0 | Clear (despejado) |
| 1 | Light clouds |
| 2 | Partially cloudy |
| 3 | Mostly cloudy |
| 4 | Overcast |
| 5 | Cloudy & drizzle |
| 6 | Cloudy & light rain |
| 7 | Overcast & light rain |
| 8 | Overcast & rain |
| 9 | Overcast & heavy rain |
| 10 | Overcast & storm |

---

## 6. Mapeo a Pydantic Models (reader.py)

El `TelemetryReader` en `shared-telemetry/reader.py` transforma los structs C en estos modelos Pydantic:

### RaceState → ticker mapping

```
RaceState
├── session: SessionData → SES, WTH
├── player: VehicleData  → DRV (posición, vueltas)
├── tyres: TyreData      → TYR
├── brakes: BrakeData    → BRK (wear_thickness SIEMPRE 0 desde shared memory)
├── engine: EngineData   → — (no se usa en ticker)
├── inputs: DriverInputs → — (no se usa en ticker)
├── opponents: dict[int, VehicleData] → RIV
└── timestamp: float
```

### TelemetryFrame (shared-strategy) → ticker mapping

El `TelemetryFrame` de `shared-strategy/models.py` es la fuente principal para el ticker, ya que incluye datos procesados:

| TelemetryFrame field | Ticker section | Notas |
|---------------------|:--------------:|-------|
| standing_position | DRV.P | — |
| lap_number | DRV.L | — |
| fuel_in_tank | DRV.F | litros |
| fuel_capacity | DRV | capacidad total |
| tyre_wear_fl/fr/rl/rr | DRV.TYR | % desgaste |
| tyre_temp_fl/fr/rl/rr | DRV.TYR | °C temperatura |
| brake_wear_fl/fr/rl/rr | BRK | vía REST API, NO shared memory |
| time_gap_place_ahead | GAP | +gap |
| time_gap_place_behind | GAP | -gap |
| session_type | SES | practice/qualifying/race |
| session_time_left | SES | tiempo restante |
| safety_car_active | WTH.SC | — |
| full_course_yellow_active | WTH.SC | — |
| battery_charge | DRV | % batería |
| speed | DRV | m/s (de mLocalVel) |
| cloud_coverage | WTH | 0-10 |
| raining | WTH | 0.0-1.0 |
| avg_path_wetness | WET | 0.0-1.0 |
| ambient_temp | WTH | °C |
| track_temp | WTH | °C |
| track_grip_level | WTH | 0-4 |
| drs_state | DRV | DRS activo |
| pit_state | PIT | 0-4 |
| competitors | RIV | lista de CompetitorTelemetry |

**IMPORTANTE:** `brake_wear_*` en TelemetryFrame SIEMPRE es 0.0 si se origina de shared memory. Los valores reales vienen de la REST API. Ver `rest-api.md`.
