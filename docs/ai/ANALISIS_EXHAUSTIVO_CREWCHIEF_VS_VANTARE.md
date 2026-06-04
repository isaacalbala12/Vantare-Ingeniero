# 📋 ANÁLISIS EXHAUSTIVO COMPLETO — Vantare Ingeniero vs CrewChiefV4
## Todas las implementaciones, detalles finos y brechas identificadas
### Fecha: 31 mayo 2026
### Revisión: Para DeepSeek V4 Pro

---

## ÍNDICE DE PASADAS

1. Arquitectura de eventos: Comparación estructural
2. El Spotter Cartesiano (el sistema más crítico)
3. Sistema de oponentes y seguimiento
4. Sistema de vueltas y sectores
5. Sistema de combustible
6. Sistema de neumáticos
7. Sistema de banderas e incidentes
8. Detección de posición y overtakes
9. Estado del modelo de datos: GameStateData
10. Sistema de cola de audio y mensajes
11. Detalles arquitectónicos finos de AbstractEvent
12. Sistema de audio: AudioPlayer y cola avanzada
13. Detalles finos de datos de LMU que NO leemos
14. Detalles de lógica de negocio que nos faltan
15. Detalles del pipeline de datos
16. El Spotter Cartesiano: algoritmo completo
17. Sistema de pits completo
18. Sistema de safety car / FCY completo
19. Detalles del sistema de audio
20. Detalles del modelo de datos: GameStateData completo
21. Sistema de control de voz
22. Sistema de condiciones climáticas
23. Sistema de datos congelados (FrozenOrder)
24. Sistema de reglas de stock cars
25. Motor de juego multi-soporte
26. Detalles del loop principal (CrewChief.cs)
27. Sistema de mensajes de sesión (SessionEndMessages)
28. Sistema de motor (EngineMonitor)
29. Sistema de vueltas y contador (LapCounter)
30. Sistema multiclase (MulticlassWarnings)
31. Sistema de oponentes vigilados (WatchedOpponents)
32. Detalles de eventos auxiliares

---

## PASADA 1 — Arquitectura de eventos: Comparación estructural

### CrewChief
CrewChief tiene **~30 clases de evento** independientes, cada una especializada en un dominio:
- `Spotter` (abstracto) + `NoisyCartesianCoordinateSpotter`
- `Opponents` — rivales, laptimes, cambios de posición, retirements
- `Position` — cambios de posición, overtakes, salida de carrera
- `PitStops` — ventanas, countdown, pit limiter, mandatory stops, benchmark
- `Fuel` — consumo, ventanas, estimaciones, FCY awareness
- `TyreMonitor` — temps, wear, presión, flat spots, locking, spinning, camber
- `FlagsMonitor` — banderas, FCY 7 fases, incidentes, blue flag, pileup
- `LapTimes` — deltas por sector, pace comparisons, consistencia, outliers
- `LapCounter` — laps restantes, pre-lights, green flag, formation lap, fin de sesión
- `DamageReporting` — daños por componente, puncture, rollover, crash detection
- `EngineMonitor` — temps aceite/agua, presión, stall warning
- `PushNow` — push/pull estratégico, pit exit warnings
- `Strategy` — estimación post-parada, pit stall occupied, R3E pit menu
- `MulticlassWarnings` — advertencias de clases más rápidas/lentas
- `WatchedOpponents` — seguimiento de rivales específicos
- `SessionEndMessages` — mensajes de fin de sesión (podio, ganador, último)
- `SafetyCarEvents` — eventos específicos de safety car
- `ConditionsMonitor` — clima con historial
- `FrozenOrderMonitor` — formación, safety car, rolling start
- `OvertakingAidsMonitor` — DRS, push-to-pass
- `Penalties` — penalizaciones, drive-through, stop-and-go
- `Battery` — gestión de batería híbrida
- `DriverSwaps` — cambios de piloto
- `CoDriver` — pace notes para rally
- `PitManagerVoiceCmds` — comandos de voz para pits
- `RaceTime` — gestión de tiempo de sesión
- `Timings` — timing general
- `CommonActions` — acciones comunes
- `IRacingBroadcastMessageEvent` — mensajes broadcast iRacing
- `PearlsOfWisdom` — mensajes aleatorios de ánimo/desánimo

Cada evento se suscribe a un `GameStateData` compartido y evalúa condiciones específicas con:
- **Cooldown propio** por evento + por tipo de mensaje
- **Validación de mensajes** (`isMessageStillValid()`) — cancela mensajes obsoletos
- **Sistema de prioridades** integrado en AudioPlayer
- **Filtrado por SessionType + SessionPhase + RacingType**

### Vantare (actual)
Tenemos **12 triggers** en `backend/src/intelligence/triggers.py`, agrupados en una sola clase `BaseTrigger`:
1. FuelCriticalTrigger — LLM_REQUIRED
2. SafetyCarTrigger — LLM_REQUIRED
3. TyreDegAccelTrigger — LLM_REQUIRED
4. WeatherChangeTrigger — LLM_REQUIRED
5. PilotQuestionTrigger — LLM_REQUIRED
6. TiresThermalOverheatingTrigger — LLM_REQUIRED
7. BrakeWearCriticalTrigger — ALERT_ONLY (el único sin LLM)
8. GapClosedTrigger — LLM_REQUIRED
9. HybridDeployMapTrigger — LLM_REQUIRED
10. PitWindowOpenedTrigger — LLM_REQUIRED
11. PitWindowClosingTrigger — LLM_REQUIRED
12. CompetitorPittedTrigger — LLM_REQUIRED

La evaluación es secuencial con `break` para `LLM_REQUIRED`.

### Brecha crítica
| Aspecto | CrewChief | Vantare |
|---------|-----------|---------|
| Eventos especializados | 30+ clases | 1 clase monolítica |
| Evaluación paralela | Sí, cada evento evalúa independientemente | No, secuencial con break |
| Validación de mensajes | `isMessageStillValid()` 2 llamadas | No existe |
| Cooldown granular | Por evento + por tipo de mensaje | Solo por trigger |
| Sin LLM | Todos funcionan | Solo 1/12 funciona (BrakeWearCritical) |
| Filtrado SessionType/Phase | Automático | No implementado |

**Impacto**: Cuando el LLM está caído, el 92% de los triggers no se evalúan porque son `LLM_REQUIRED` y el `break` bloquea el ciclo. CrewChief tiene **0 dependencias de LLM** — todo es determinista.

---

## PASADA 2 — El Spotter Cartesiano: algoritmo completo

### CrewChief: `NoisyCartesianCoordinateSpotter.cs` (1000+ líneas)

**Algoritmo paso a paso**:

1. **Filtrado por rango**: Solo procesa oponentes dentro de `trackZoneToConsider = 20m` en X y Z del jugador
2. **Filtrado por velocidad**: `playerVelocityData[0] > minSpeedForSpotterToOperate` (configurable, default 10m/s)
3. **Cálculo de velocidad de oponente**: Derivada de posición cada 0.2s — no necesita datos externos
4. **Rotación de coordenadas**: `getAlignedXZCoordinates(playerRotation, playerX, playerZ, rivalX, rivalZ)`:
   - Aplica matriz de rotación 2D usando el yaw del jugador
   - Devuelve coordenadas "alineadas" donde X=0 es adelante del jugador
5. **Clasificación lateral**:
   - `alignedX < -2m` → izquierda
   - `alignedX > 2m` → derecha
   - `|alignedX| < 2m` → adelante/atrás (no reportar como lado)
6. **Validación de overlap**: Solo cuenta como overlap si:
   - `|alignedX| > carWidth` (separación lateral suficiente)
   - Velocidad de cierre < `maxClosingSpeed` (configurable)
   - Oponente dentro de `trackZoneToConsider`
7. **Detección 3-wide**: Si `carsOnLeft > 1` Y `separationDelta < carWidth` → son line-astern, no 3-wide
8. **Máximo de overlaps**: `maxOverlapsPerSide = 3` (configurable) — no reporta más de 3 coches por lado
9. **Delays configurables**:
   - `clearMessageDelay`: delay antes de decir "clear" (evita falsos positivos)
   - `overlapMessageDelay`: delay antes de decir "car left"
   - `bouncingWait`: delay reducido cuando bouncing entre clear y overlap
   - `onSingleOverlapTo3WideDelay`: 0.5s entre "car left" y "3 wide"
10. **"Still there"**: Repite "still there" cada `repeatHoldFrequency` (3s default, 5s óvalos)
11. **Canal abierto**: `keepChannelOpenAfterSpotter()` mantiene el canal abierto para spotter continuo en circuitos
12. **Purgado de mensajes**: `removeImmediateMessages()` elimina mensajes de spotter conflictivos de la cola inmediata
13. **Expiración**: Mensajes de clear expiran en 2000ms, hold en 1000ms, inTheMiddle en 1000ms
14. **Modo óvalo**: Sonidos específicos "inside/outside" en vez de "left/right"
15. **Grid side detection**: `getGridSide()` determina lado de parrilla en formación

**Mensajes del spotter**:
- `car_left` / `car_right` — primer overlap
- `still_there` — repetición mientras hay overlap
- `clear_left` / `clear_right` — fin de overlap
- `clear_all_round` — fin de overlap en ambos lados
- `in_the_middle` — 3-wide, estás en medio
- `three_wide_on_left` / `three_wide_on_right` — 3-wide, estás en el lado
- `three_wide_on_inside` / `three_wide_on_outside` — 3-wide en óvalo

### Nuestra implementación actual
- No tenemos coordenadas cartesianas → no podemos implementar esto
- No tenemos `rotation_yaw` → no podemos rotar coordenadas
- No tenemos detección de velocidad de cierre
- No tenemos detección 3-wide
- No tenemos delays configurables
- No tenemos sistema de canal abierto para spotter

### Brecha crítica
| Característica | CrewChief | Vantare |
|---------------|-----------|---------|
| Algoritmo | Cartesiano (X,Z + yaw) | Time gap |
| Detección izquierda/derecha | ✅ | ❌ |
| Detección 3-wide | ✅ | ❌ |
| Detección oval (inside/outside) | ✅ | ❌ |
| Delays configurables | ✅ | ❌ |
| "Still there" repeat | ✅ | ❌ |
| Canal abierto spotter | ✅ | ❌ |
| Purgado de cola spotter | ✅ | ❌ |
| Expiración de mensajes | ✅ | ❌ |
| Cálculo velocidad oponente | ✅ (derivada 0.2s) | ❌ |
| Grid side detection | ✅ | ❌ |
| Spotter enable/disable | ✅ | ❌ |
| Min speed threshold | ✅ | ❌ |
| Max closing speed | ✅ | ❌ |
| Track zone consideration | ✅ (20m) | ❌ |

---

## PASADA 3 — Sistema de oponentes y seguimiento

### CrewChief: `Opponents.cs` (1200+ líneas)

**Sistemas implementados**:

1. **Tracking de laptimes de rivales**: Compara laptimes de oponentes con el mejor de la sesión
   - `frequencyOfOpponentRaceLapTimes` — frecuencia configurable
   - `frequencyOfOpponentPracticeAndQualLapTimes` — frecuencia en prac/qual
   - Detecta vueltas rápidas de rivals con mejora mínima `minImprovementBeforeReadingOpponentRaceTime`
   - Filtra por `maxOffPaceBeforeReadingOpponentRaceTime`

2. **Cambios de posición**:
   - `HasLeadChanged` — detecta nuevo líder
   - `IsRacingSameCarInFront` — detecta nuevo coche delante
   - Con **validación de mensajes**: si el mensaje se retrasa en la cola, valida que la posición siga siendo la misma
   - `onlyAnnounceOpponentAfter` — evita bouncing entre mensajes
   - `waitBeforeAnnouncingSameOpponentAhead` — 3 minutos de espera

3. **Retirements y DQ**:
   - `retiredDriverNames` — lista de pilotos retirados
   - `disqualifiedDriverNames` — lista de pilotos descalificados
   - Filtra DNF pre-sesión en ISI games
   - `announcedRetirementsAndDQs` — evita anunciar duplicados

4. **Cambios de neumáticos de rivales**:
   - `hasJustChangedToDifferentTyreType` — detecta cambio de compound
   - `suppressOpponentTyreChangeUntil` — cooldown 10-20s aleatorio
   - Anuncia: "VST is now on mediums"

5. **Validación de mensajes**:
   - `validationDriverAheadKey` — valida que el coche delante siga siendo el mismo
   - `validationNewLeaderKey` — valida que el líder siga siendo el mismo
   - Se llama JUSTO ANTES de reproducir el mensaje

6. **Voice commands**:
   - `WHATS_BEHIND_ME` / `WHATS_IN_FRONT_OF_ME` — "who's behind/in front on track?"
   - `WHOS_BEHIND_IN_THE_RACE` / `WHOS_IN_FRONT_IN_THE_RACE` — posición en carrera
   - `WHOS_LEADING` — quién va primero
   - `WHERE_IS [nombre]` — dónde está un piloto
   - `WHATS [nombre] LAST_LAP/BEST_LAP` — laptimes de rival
   - `HOW_GOOD_IS [nombre]` — rating/reputación (R3E)
   - `WHAT_TYRE_IS [nombre] ON` — compound del rival

### Nuestra implementación actual
- Tenemos `rivals` en el flat dict (3 delante, 3 detrás) pero solo 4 campos por rival
- No detectamos **cambios de posición** (leader change, new car ahead)
- No anunciamos **retirements/DQ**
- No reportamos **cambios de neumáticos** de rivals
- No tenemos sistema de **validación de mensajes**
- No tenemos **seguimiento de rivales específicos** (watch/rival)

### Brecha crítica
| Funcionalidad | CrewChief | Vantare |
|--------------|-----------|---------|
| Leader change | ✅ | ❌ |
| New car ahead/behind | ✅ | ❌ |
| Retirement/DQ | ✅ | ❌ |
| Rival tyre changes | ✅ | ❌ |
| Message validation | ✅ (2 llamadas) | ❌ |
| Watched opponents | ✅ | ❌ |
| Rival laptime reports | ✅ | ❌ |
| Voice commands oponentes | ✅ (10+) | ❌ |

---

## PASADA 4 — Sistema de vueltas y sectores

### CrewChief: `LapTimes.cs` (900+ líneas)

**Sistemas implementados**:

1. **Deltas por sector**: Compara cada sector contra el mejor de la sesión/clase
   - `frequencyOfRaceSectorDeltaReports` — frecuencia en carrera
   - `frequencyOfPracticeAndQualSectorDeltaReports` — frecuencia en prac/qual
   - `raceSectorReportsAtEachSector` — reportar en cada sector
   - `raceSectorReportsAtLapEnd` — reportar al final de vuelta

2. **Categorización de deltas**:
   - `FAST` (< 0.05s)
   - `A_TENTH` (0.05-0.15s)
   - `TWO_TENTHS` (0.15-0.25s)
   - `A_SECOND` (0.95-1.05s)
   - `AUTO_GAPS` (< 10s, con randomización)

3. **Consistencia**: Analiza ventana de 5 vueltas
   - `lapTimesWindowSize = 5`
   - Clasifica: `CONSISTENT`, `IMPROVING`, `WORSENING`
   - `consistencyLimit = 0.5%` — si varía < 0.5% es consistente

4. **Self-pace vs rival pace**: 
   - Compara contra mejor personal o mejor de la clase
   - `selfPace` flag para modo self-pace
   - `PaceOK` / `PaceBad` / `NeedToFindOneMoreTenth`

5. **Outlier detection**:
   - `outlierPaceLimits` por `TrackLengthClass`:
     - VERY_LONG: ±15s
     - LONG: ±8s
     - MEDIUM: ±3s
     - SHORT: ±2s
     - VERY_SHORT: ±2s
   - Detecta out laps, in laps, tráfico

6. **Laps before announcing gaps**:
   - Por `TrackLengthClass`:
     - VERY_SHORT: 4 laps
     - SHORT: 3 laps
     - MEDIUM: 2 laps
     - LONG: 1 lap
     - VERY_LONG: 0 laps

7. **Qualifying specific**:
   - "that was a 1:34.2, you're now 0.4 seconds off the pace"
   - Compara contra mejor de la sesión

8. **Race specific**:
   - "best lap in race" / "best lap in race for class"
   - "setting current race pace" / "matching race pace"
   - "personal best"

### Nuestra implementación actual
- Tenemos `lap_number` y `total_laps` en el flat dict
- El `FuelComputer` calcula consumo por vuelta
- **NO tenemos**: detección de última vuelta, deltas por sector, análisis de consistencia, outlier detection, qualifying deltas

### Brecha crítica
| Funcionalidad | CrewChief | Vantare |
|--------------|-----------|---------|
| Última vuelta anunciada | ✅ | ❌ |
| Deltas por sector | ✅ (60+ mensajes) | ❌ |
| Análisis de consistencia | ✅ | ❌ |
| Outlier detection | ✅ | ❌ |
| Self-pace vs rival pace | ✅ | ❌ |
| Laps before gaps | ✅ | ❌ |
| Qualifying deltas | ✅ | ❌ |
| Race pace tracking | ✅ | ❌ |

---

## PASADA 5 — Sistema de combustible

### CrewChief: `Fuel.cs` (900+ líneas)

**Sistemas implementados**:

1. **Inicialización**: Detecta cuándo empezar a trackear
   - 15s después de empezar
   - Fuera de pits
   - En movimiento
   - No en out lap

2. **Cálculo de consumo**: Ventana deslizante de últimas 3-6 vueltas
   - Depende de longitud de pista (`trackLengthClass`)
   - `fuelUseByLapsWindowLengthToUse`:
     - VERY_SHORT: 1 vuelta
     - SHORT: 2 vueltas
     - MEDIUM: 3 vueltas
     - LONG: 4 vueltas
     - VERY_LONG: 5 vueltas

3. **Máximo consumo**: Registra consumo máximo por vuelta y por minuto

4. **Ventana de pits**: Calcula ventana óptima
   - Laps restantes + consumo medio
   - Capacidad del tanque
   - Reserve configurable (`add_additional_fuel_laps`)

5. **Estimaciones contextuales**: Ajusta según tipo de sesión

6. **FCY awareness**: Usa máximo consumo si hubo Safety Car

7. **Mensajes específicos**:
   - "2 minutos de combustible"
   - "fuel will be tight"
   - "pit now"
   - "fuel to end"

### Nuestra implementación actual
- `FuelComputer` con media de 5 vueltas
- Estimación de vueltas restantes
- **NO tenemos**: ventana de pits, máximo consumo, FCY adjustment, refuel detection, mensajes contextuales

---

## PASADA 6 — Sistema de neumáticos

### CrewChief: `TyreMonitor.cs` (2500+ líneas)

**Sistemas implementados**:

1. **Temperatura de neumáticos**: Clasifica cada neumático
   - `COLD` / `WARM` / `HOT` / `COOKING`
   - Rangos específicos por compound
   - Muestra: carcass + inner/middle/outer

2. **Wear de neumáticos**: Clasifica
   - `NEW` / `SCRUBBED` / `MINOR_WEAR` / `MAJOR_WEAR` / `WORN_OUT`

3. **Presión de neumáticos**: Monitorea con tendencias
   - Samplea cada 1000ms
   - Detecta flat spots por diferencia de presión
   - `punctureThreshold = 30f` (kPa, ~5psi)

4. **Locking/Spinning**: Acumula tiempo por vuelta
   - Por rueda individual (LF, RF, LR, RR)
   - Por grupo (fronts, rears, lefts, rights)
   - Detecta el neumático más bloqueado

5. **Camber analysis**: Compara temps interno vs externo

6. **Compound detection**: Identifica tipo de compound

7. **Mensajes específicos**: ~80+ mensajes diferentes

### Nuestra implementación actual
- Leemos `tyre_wear`, `tyre_temp`, `tyre_pressure`, `tyre_flat`
- Tenemos `TiresThermalOverheatingTrigger` (>105°C)
- **NO tenemos**: clasificación temps, locking/spinning, camber, pressures trend, compound detection

---

## PASADA 7 — Sistema de banderas e incidentes

### CrewChief: `FlagsMonitor.cs` (1600+ líneas)

**Sistema de fases FCY**:
```csharp
public enum FullCourseYellowPhase {
    PENDING,           // FCY declarado
    IN_PROGRESS,       // FCY activo
    PITS_CLOSED,       // Pit lane cerrado
    PITS_OPEN_LEAD_LAP_VEHICLES,  // Solo líderes
    PITS_OPEN,         // Todos pueden entrar
    LAST_LAP_NEXT,     // Última vuelta bajo FCY
    LAST_LAP_CURRENT,  // Última vuelta actual
    RACING             // FCY terminado
}
```

**Detección de incidentes**:
1. Compara `distanceRoundTrack` entre ticks
2. Si `delta_distance < threshold` → coche detenido
3. Agrupa por corner (landmark detection)
4. Detecta pileup: `>= 4 coches`
5. Reporta nombres de pilotos
6. Detecta si jugador está involucrado

**Blue flag**: Detecta coche más rápido detrás, max 3 repeticiones

**Overtake bajo yellow**: Detecta adelantamientos ilegales

### Brecha crítica
| Funcionalidad | CrewChief | Vantare |
|--------------|-----------|---------|
| FCY 7 fases | ✅ | ❌ (3 booleanos) |
| Incident detection | ✅ | ❌ |
| Pileup detection | ✅ | ❌ |
| Blue flag | ✅ | ❌ |
| Overtake bajo yellow | ✅ | ❌ |
| Sector flags | ✅ | ❌ |

---

## PASADA 8 — Detección de posición y overtakes

### CrewChief: `Position.cs` (1000+ líneas)

**Sistemas**:
1. **Overtake detection**: Compara `getOpponentKeyInFront()` entre ticks
   - Valida: gap promedio < threshold, misma vuelta, no en pits, no en yellow
   - Verifica si fue "limpio" (sin daño, sin off-track, sin yellow)

2. **Being overtaken**: Detecta cuando un rival que estaba detrás pasa a estar delante

3. **Race start messages**:
   - "Terrible start" (pérdida > 5 posiciones)
   - "Bad start" (pérdida > 3)
   - "Good start" (ganancia > 1 o pole)
   - "OK start"

4. **Position reminders**: Anuncia posición cada 3-6 vueltas aleatoriamente

5. **Expected finish position**: Predice posición final en qualy

### Brecha crítica
| Funcionalidad | CrewChief | Vantare |
|--------------|-----------|---------|
| Overtake detection | ✅ | ❌ |
| Being overtaken | ✅ | ❌ |
| Race start quality | ✅ | ❌ |
| Position reminders | ✅ | ❌ |
| Expected finish position | ✅ | ❌ |

---

## PASADA 9 — Estado del modelo de datos

### CrewChief: `GameStateData.cs` (5000+ líneas)

**Estructura completa**:
```csharp
class GameStateData {
    public SessionData SessionData;
    public TelemetryData TelemetryData;
    public OpponentDataDictionary OpponentData; // ~50 campos/rival
    public PitData PitData;
    public FlagData FlagData;
    public TyreData TyreData; // 12+ campos/rueda
    public CarDamageData CarDamageData;
    public EngineData EngineData;
    public FuelData FuelData;
    public BatteryData BatteryData;
    public PositionAndMotionData PositionAndMotionData; // X,Y,Z + Pitch,Roll,Yaw
    public TimingData TimingData;
    public FrozenOrderData FrozenOrderData;
    public Conditions Conditions;
    public StockCarRulesData StockCarRulesData;
    public TransmissionData TransmissionData;
    public PenalitiesData PenalitiesData;
    public ControlData ControlData;
}
```

### Brecha crítica en datos
| Campo CrewChief | Tenemos | Notas |
|----------------|---------|-------|
| `Rotation.Yaw` | ❌ | CRÍTICO para spotter cartesiano |
| `SessionRunningTime` | ❌ | Solo tiempo restante |
| `GameTimeAtLastPositionFrontChange` | ❌ | Para PushNow |
| `PlayerLapTimeSessionBest` | ❌ | Mejor vuelta personal |
| `TrackDefinition` | ❌ | Longitud, corners, pit positions |
| `DeltaTime` con diferencias de vuelta | ❌ | Solo gaps en segundos |
| `OpponentData.DriverRawName` | ❌ | Nombre del piloto |
| `OpponentData.CarNumber` | ❌ | Número de coche |
| `OpponentData.Speed` | ❌ | Velocidad del rival |
| `OpponentData.DeltaTime` | ❌ | Delta con jugador |
| `OpponentData.CurrentBestLapTime` | ❌ | Mejor vuelta del rival |
| `OpponentData.CompletedLaps` | ❌ | Vueltas completadas |
| `TyreData.TyreType` | ❌ | Compound individual |
| `EngineData.EngineWaterTemp` | ❌ | Temp agua |
| `EngineData.EngineOilTemp` | ❌ | Temp aceite |
| `PitData.MandatoryPitMinDurationLeft` | ❌ | Tiempo mínimo parada |
| `PitData.PitSpeedLimit` | ❌ | Límite velocidad pit |
| `FlagData.fcyPhase` (7 valores) | ❌ | Solo booleanos |

---

## PASADA 10 — Sistema de cola de audio y mensajes

### CrewChief: `AudioPlayer.cs` (2300+ líneas)

**Características**:

1. **Dual cola**: `queuedClips` (normal) + `immediateClips` (urgente)
2. **Prioridad por inserción**: `getInsertionIndex()` — mayor prioridad = antes
3. **SoundType enum**:
   - `CRITICAL_MESSAGE` (priority 15)
   - `IMPORTANT_MESSAGE` (priority 10)
   - `SPOTTER` (priority 20)
   - `REGULAR_MESSAGE` (priority 0-5)
   - `VOICE_COMMAND_RESPONSE`
   - `NONE` (deshabilitado)

4. **Purgado selectivo**: 
   - Damage DESTROYED → purga toda la cola
   - Retiene mensajes de voice command con `speechRecognitionSessionID`

5. **Channel management**: `holdChannelOpen` para spotter continuo

6. **Beeps configurables**: 8 tipos de beep

7. **Sound cache**: Precarga en background thread

8. **Playback moderator**: Filtra por `enabledMessageTypes` por clase de coche

9. **Pause de cola**: `pauseQueue(seconds)` para FCY, pit stops

### Brecha crítica
| Característica | CrewChief | Vantare |
|---------------|-----------|---------|
| Cola dual | ✅ | ❌ (FIFO única) |
| Sistema de prioridades | ✅ (0-20) | ❌ |
| SoundType enum | ✅ (6 tipos) | ❌ |
| Purgado selectivo | ✅ | ❌ |
| Channel open/close | ✅ | ❌ |
| Beeps configurables | ✅ | ❌ |
| Sound cache | ✅ | ❌ |
| Playback moderator | ✅ | ❌ |

---

## PASADA 11 — Detalles arquitectónicos finos de AbstractEvent

### CrewChief: `AbstractEvent.cs`

**Características**:

1. **Sistema de fragmentos de mensaje compuestos**:
   ```csharp
   MessageContents(folderPitNow, Pause(200), folderBoxIn, 5, folderBoxIn, 4, ...)
   ```
   - `Pause(200)` — pausa de 200ms insertada en el mensaje
   - `MessageFragment.Integer(5)` — números leídos con NumberReader (no TTS genérico)
   - `MessageFragment.Time(TimeSpanWrapper)` — tiempos con precisión adaptativa
   - `MessageFragment.Opponent(opponentData)` — nombre/número automático
   - `MessageFragment.Text("celsius")` — texto con conversión unidades

2. **Validación de mensajes en dos momentos**:
   - Llamada 1: cuando el mensaje vence
   - Llamada 2: JUSTO ANTES de reproducirlo (delay en cola)
   - Permite cancelar mensajes que quedaron obsoletos

3. **Aplicabilidad por SessionType + SessionPhase + RacingType**:
   - Filtrado automático por tipo de sesión y fase

4. **Sistema de unidades configurable**:
   - `convertTemp()` — Celsius/Fahrenheit según settings
   - `convertPressure()` — kPa a PSI/Bar según settings

### Nuestra implementación
- Enviamos texto plano al TTS — sin pausas, sin énfasis, sin estructura
- No hay validación de mensajes
- No hay filtrado automático por sesión
- No hay conversión de unidades

---

## PASADA 12 — Sistema de audio: detalles adicionales

### Características adicionales de AudioPlayer:

1. **Pearls of Wisdom**:
   - `PearlType.GOOD` — "Beautifully executed!", "Nicely done"
   - `PearlType.BAD` — "That was terrible", "What were you thinking?"
   - `PearlType.NEUTRAL` — "Keep pushing", "Stay focused"
   - `maxComplaintsPerSession` — límite de quejas por sesión
   - Se suspenden en SafetyCar, última vuelta, daño destroyed

2. **Standby delays**:
   - `pauseQueueAndPlayDelayedImmediateMessage()` — responde "stand by" primero, luego mensaje real tras 5-11s
   - Usado en daños, opponent info, strategy

3. **DelayedMessageEvent**:
   - El mensaje se evalúa **en el momento de reproducirse**, no al crearse
   - Permite que mensajes de posición se actualicen si la posición cambió mientras estaba en cola

4. **Hanging channel close thread**:
   - Si el spotter deja el canal abierto y no hay más mensajes, lo cierra tras 6s

5. **Breath detection**:
   - `breathDueAt` — determina cuándo el spotter necesita respirar
   - `maxSecondsBeforeTakingABreath = 3`

6. **Device change detection**:
   - `NotificationClientImplementation` — detecta cambios de dispositivo de audio
   - Reindexa dispositivos automáticamente
   - `OnDefaultDeviceChanged`, `OnDeviceAdded`, `OnDeviceRemoved`, `OnDeviceStateChanged`

7. **Rant system**:
   - `playRant()` — mensajes de enfado aleatorios
   - `rantLikelihood = 0.1` — 10% de probabilidad
   - `playedRantInThisSession` — solo una por sesión

8. **NAudio integration**:
   - WASAPI para baja latencia
   - WaveOut como fallback
   - `InterruptCurrentlyPlayingSound()` — interrumpe sonido actual

---

## PASADA 13 — Detalles finos de datos de LMU

### a) Rotación del vehículo (CRÍTICO)
```csharp
// CrewChief GameStateData:
public class PositionAndMotionData {
    public float[] WorldPosition;  // [x, y, z]
    public Rotation Orientation;   // Pitch, Roll, Yaw en radianes
}

// CrewChief Spotter:
float alignedX = getAlignedXZCoordinates(playerRotation, playerX, playerZ, rivalX, rivalZ);
```
**LMU shared memory tiene**: `mPos.x/y/z` (que leemos) pero **NO leemos `mRot` o similar**.
La shared memory de LMU (`LMUVehicleTelemetry`) no expone directamente el yaw en la estructura que estamos leyendo actualmente.

### b) Datos de opponent que NO leemos (50+ campos por rival)
```csharp
class OpponentData {
    string DriverRawName;           // ❌
    string CarNumber;               // ❌
    int ClassPosition;              // ❌
    int OverallPosition;            // ✅ Tenemos place
    float Speed;                    // ❌
    float DistanceRoundTrack;       // ❌
    float DeltaTime;                // ❌
    float CurrentBestLapTime;       // ❌
    float LastLapTime;              // ❌
    int CompletedLaps;              // ❌
    int CurrentSectorNumber;        // ❌
    bool IsActive;                  // ❌
    TyreType CurrentTyres;          // ❌
    bool InPits;                    // ✅
    bool isEnteringPits();          // ❌
    bool isOnOutLap();              // ❌
    List<float> OpponentLapData;    // ❌
    // ... y 35+ campos más
}
```

### c) Datos de sesión que NO leemos
```csharp
class SessionData {
    bool IsNewLap;                 // ❌
    bool IsNewSector;              // ❌
    bool JustGoneGreen;            // ❌
    bool CurrentLapIsValid;        // ❌
    bool PreviousLapWasValid;      // ❌
    float SessionRunningTime;      // ❌
    float PlayerLapTimeSessionBest;// ❌
    float SessionFastestLapTime;   // ❌
    int NumCarsOverall;            // ❌
    int NumCarsInPlayerClass;      // ❌
    TrackDefinition TrackDefinition; // ❌
    // ...
}
```

### d) Datos de pits que NO leemos
```csharp
class PitData {
    bool InPitlane;                // ✅
    bool IsInGarage;               // ✅
    bool OnOutLap;                 // ❌
    PitWindow PitWindow;            // ❌
    bool HasMandatoryPitStop;      // ❌
    float PitSpeedLimit;           // ❌
    bool PitStallOccupied;         // ❌
    float MandatoryPitMinDurationLeft; // ❌
    bool HasRequestedPitStop;      // ❌
    float[] PitBoxLocationEstimate; // ❌
    float PitBoxPositionEstimate;  // ❌
    bool limiterStatus;            // ❌
    // ...
}
```

### e) Datos de flags que NO leemos
```csharp
class FlagData {
    FlagEnum[] sectorFlags;        // ❌
    bool isFullCourseYellow;       // ⚠️
    FullCourseYellowPhase fcyPhase; // ❌ (7 fases)
    float distanceToNearestIncident;// ❌
    int numCarsPassedIllegally;    // ❌
    bool isLocalYellow;            // ❌
    // ...
}
```

---

## PASADA 14 — Detalles de lógica de negocio

### a) Detección de out lap / in lap
CrewChief rastrea si el jugador está en vuelta de salida de boxes (`OnOutLap`).
- No se reportan laptimes de out laps
- No se reportan deltas de out laps
- El fuel no se trackea en out laps

### b) Detección de vuelta inválida
```csharp
if (!currentGameState.SessionData.CurrentLapIsValid || !currentGameState.SessionData.PreviousLapWasValid)
    // No reportar laptimes, deltas, pace
```

### c) Formación de parrilla (grid side)
```csharp
public Tuple<GridSide, Dictionary<int, GridSide>> getGridSide(Object currentStateObj)
```
CrewChief determina el lado de la parrilla usando coordenadas cartesianas de salida.

### d) Transiciones de fase de sesión
CrewChief detecta con precisión:
- `JustGoneGreen` → transición Countdown/Formation → Green
- `JustGoneCheckered` → transición Green → Checkered
- `OnManualFormationLap` → flag global

### e) Laptime validation con outlier detection
```csharp
// CrewChief LapTimes:
if (currentGameState.SessionData.LapTimePrevious < currentGameState.SessionData.PlayerLapTimeSessionBest + 
    LapTimes.outlierPaceLimits[currentGameState.SessionData.TrackDefinition.trackLengthClass])
```

### f) Cambio de neumáticos de rivales
```csharp
if (opponentData.hasJustChangedToDifferentTyreType && currentGameState.Now > suppressOpponentTyreChangeUntil)
    // Anunciar: "VST is now on mediums"
```

### g) Sistema de cooldown granular
```csharp
// CrewChief - cada evento tiene su propio cooldown:
private int minSecondsBetweenOpponentTyreChangeCalls = 10;
private int maxSecondsBetweenOpponentTyreChangeCalls = 20;
private TimeSpan timeBetweenYellowFlagMessages = TimeSpan.FromSeconds(25);
private TimeSpan timeBetweenBlueFlagMessages = TimeSpan.FromSeconds(15);
// ... más de 20 cooldowns diferentes
```

---

## PASADA 15 — Detalles del pipeline de datos

### a) Cálculo de velocidad robusto
```csharp
// CrewChief:
d["speed"] = float(pt.mSpeed)  // Lee mSpeed directamente

// Nosotros:
d["speed"] = abs(curr_ld - self._prev_lap_dist) / 0.05  // Derivada de lap distance
```
Nuestro cálculo es frágil: si `lap_distance` salta (reset de vuelta, datos corruptos), la velocidad se dispara.

### b) Detección de tiempo real de sesión
```csharp
// CrewChief tiene:
float SessionRunningTime  // Tiempo real desde que empezó
float SessionTimeRemaining // Tiempo restante

// Nosotros tenemos:
d["session_time_remaining"]  // Solo tiempo restante
```

### c) TrackDefinition completa
```csharp
class TrackDefinition {
    string name;
    float trackLength;
    TrackLengthClass trackLengthClass;  // VERY_SHORT/SHORT/MEDIUM/LONG/VERY_LONG
    List<Corner> corners;
    List<string> landmarks;
    float pitBoxPosition;
    float pitExitPosition;
}
```

### d) Condiciones climáticas con historial
```csharp
class Conditions {
    List<ConditionsSample> samples;  // Muestras cada 10 segundos
    ConditionsSample getMostRecentConditions();
    float getBestTime(ConditionsEnum);  // Filtra laptimes por condiciones
}
```

### e) PreviousTick tracking
```csharp
// CrewChief puede consultar el estado ANTERIOR:
getOpponentAtClassPosition(5, carClass, previousTick: true)
// Esto permite detectar: "había un coche en P5, ahora no está" = cambio de posición
```

---

## PASADA 16 — El Spotter Cartesiano: código completo

### CrewChief: `NoisyCartesianCoordinateSpotter.cs` (1000+ líneas)

**Características adicionales**:

1. **Spotter enable/disable**:
   ```csharp
   public void enableSpotter() {
       enabled = true;
       audioPlayer.playMessageImmediately(new QueuedMessage(folderEnableSpotter, 0));
   }
   public void disableSpotter() {
       enabled = false;
       audioPlayer.playMessageImmediately(new QueuedMessage(folderDisableSpotter, 0));
   }
   ```

2. **Spotter pause/unpause**:
   - Se pausa automáticamente en FCY
   - Se pausa si `DamageReporting.waitingForDriverIsOKResponse`

3. **Spotter voice commands**:
   - `SPOTTER_ENABLE` / `SPOTTER_DISABLE`

4. **Spotter radio check**:
   - `folderSpotterRadioCheck` — prueba de audio del spotter

5. **Oval-specific sounds**:
   - `folderCarInside` / `folderCarOutside` — para óvalos
   - `hasOvalSpecificSounds` — detecta si hay sonidos específicos

6. **Spotter folder per voice pack**:
   - `spotter_Jim/` — spotter por defecto
   - `spotter_Geoffrey/` — otro spotter
   - Detecta automáticamente carpetas de spotter

---

## PASADA 17 — Sistema de pits completo

### CrewChief: `PitStops.cs` (1500+ líneas)

**Sistemas**:

1. **Pit countdown posicional**: "Box in 5, 4, 3, 2, 1, BOX!"
   - `pitCountdownTriggerPoints` calculados por velocidad
   - Soporta metros y pies

2. **Pit countdown temporal**: "Wait... wait... wait... go!"

3. **Ventana de pits obligatoria**:
   - Anuncia apertura/cierre
   - "pit this lap" cuando estás en la vuelta correcta
   - "missed stop" si se pasó la ventana

4. **Pit limiter**: engage/disengage

5. **Velocidad de pit lane**:
   - "Watch your pit speed, 80 km/h"
   - Configurable metric/imperial

6. **Pit stall occupied/available**:
   - Detecta box ocupado al entrar

7. **R3E pit menu integration**:
   - "we're changing all 4 tyres"
   - "we're refuelling"
   - "we'll fix front aero"

8. **Mandatory stop con mínimo de duración**:
   - "Wait... 5 seconds... go!"
   - "left pit too soon"

9. **Pit exit warnings**:
   - "Pits exit clear" / "traffic behind exiting pits"

10. **Benchmark de paradas**:
    - Mide tiempo de parada en practice
    - Persiste en `pit_benchmarks.json`

11. **Estimación de posición post-parada**:
    - "we should emerge in P4, just behind P3"
    - Detecta tráfico: "expect traffic on pit exit"

---

## PASADA 18 — Sistema de safety car / FCY

### CrewChief: `FlagsMonitor.cs` (1600+ líneas)

**FCY 7 fases**:
```csharp
PENDING → IN_PROGRESS → PITS_CLOSED → 
PITS_OPEN_LEAD_LAP_VEHICLES → PITS_OPEN → 
LAST_LAP_NEXT → LAST_LAP_CURRENT → RACING
```

**Incident detection**:
- Compara distancia recorrida entre ticks
- Agrupa por corner
- Detecta pileup (>= 4 coches)
- Reporta nombres de pilotos

**Blue flag**:
- Detecta coche más rápido detrás
- Max 3 repeticiones por conductor

**Overtake bajo yellow**:
- Detecta adelantamientos ilegales

---

## PASADA 19 — Detalles del sistema de audio

### CrewChief: `AudioPlayer.cs` (2300+ líneas)

**Características completas**:

1. **Dual cola**: `queuedClips` + `immediateClips`
2. **Prioridad por inserción**: `getInsertionIndex()`
3. **SoundType enum**: 6 tipos
4. **Purgado selectivo**: `purgeQueues()`
5. **Channel management**: `holdChannelOpen`, `hangingChannelCloseThread`
6. **Beeps**: 8 tipos configurables
7. **Sound cache**: Precarga background
8. **Playback moderator**: Filtra por clase de coche
9. **Pause de cola**: `pauseQueue(seconds)`
10. **NAudio WASAPI/WaveOut**: Baja latencia
11. **Dispositivos separados**: Mensajes vs background
12. **Device change**: Reindexa automáticamente
13. **Pearls of Wisdom**: Mensajes aleatorios
14. **Standby delays**: Respuestas con delay
15. **DelayedMessageEvent**: Evalúa al reproducir
16. **Rant system**: Mensajes de enfado
17. **Breath detection**: Para spotter
18. **Retain on session end**: Mensajes que sobreviven a cambio de sesión

---

## PASADA 20 — Modelo de datos completo

### CrewChief: `GameStateData.cs` (5000+ líneas)

**Campos críticos que NO tenemos**:

| # | Campo | Tipo | Impacto |
|---|-------|------|---------|
| 1 | `Rotation.Yaw` | float rad | CRÍTICO spotter cartesiano |
| 2 | `SessionRunningTime` | float | Cooldowns rotos |
| 3 | `GameTimeAtLastPositionFrontChange` | float | PushNow |
| 4 | `PlayerLapTimeSessionBest` | float | Pace analysis |
| 5 | `TrackDefinition` | objeto | Thresholds adaptativos |
| 6 | `DeltaTime` (con lap diff) | objeto | Deltas correctos |
| 7 | `OpponentData.DriverRawName` | string | Nombres de rivales |
| 8 | `OpponentData.CarNumber` | string | Números de coche |
| 9 | `OpponentData.Speed` | float | Velocidad rival |
| 10 | `OpponentData.CompletedLaps` | int | Detección cambios |
| 11 | `TyreData.TyreType` | enum | Compound detection |
| 12 | `EngineData.EngineWaterTemp` | float | Engine monitor |
| 13 | `PitData.MandatoryPitMinDurationLeft` | float | Mandatory stops |
| 14 | `FlagData.fcyPhase` | enum 7 vals | FCY completo |
| 15 | `PositionAndMotionData.AccelerationVector` | objeto | Crash detection |
| 16 | `PositionAndMotionData.LocalVelocity` | float[3] | Velocidad precisa |

---

## PASADA 21 — Sistema de control de voz

### CrewChief: `SpeechRecogniser.cs`

**70+ comandos de voz**:
- `WHAT_TYRES_AM_I_ON`
- `WHATS_MY_POSITION`
- `WHATS_BEHIND_ME` / `WHATS_IN_FRONT_OF_ME`
- `WHATS_THE_GAP`
- `PIT_NOW` / `CANCEL_PIT`
- `WHAT_ARE_THE_PIT_ACTIONS`
- `WHATS_THE_PIT_SPEED_LIMIT`
- `IS_MY_PIT_BOX_OCCUPIED`
- `WHATS_MY_FUEL`
- `WHATS_TYRE_WEAR`
- `WHATS_MY_LAP_TIME`
- `WHATS_THE_BEST_LAP`
- `WHO_LEADING`
- `WHOS_BEHIND_ON_TRACK` / `WHOS_IN_FRONT_ON_TRACK`
- `WHERE_IS [nombre]`
- `WHATS [nombre] LAST_LAP/BEST_LAP`
- `HOW_GOOD_IS [nombre]`
- `WHAT_TYRE_IS [nombre] ON`
- `PACE_NOTES_START/STOP`
- `DRIVER_TRAINING_MODE`
- `KEEP_QUIET` / `UNKEEP_QUIET`
- `ENABLE_DELTAS` / `DISABLE_DELTAS`
- `REPEAT_LAST_MESSAGE`
- `SPOTTER_ENABLE` / `SPOTTER_DISABLE`
- `PRACTICE_PIT_STOP`
- `PLAY_POST_PIT_POSITION_ESTIMATE`

---

## PASADA 22 — Sistema de condiciones climáticas

### CrewChief: `ConditionsMonitor.cs`

**Sistema**:
1. Muestreo cada 10s: `TrackTemp`, `AmbientTemp`, `RainDensity`, `CloudBrightness`
2. Historial completo de muestras
3. Clasificación: 11 niveles (SNOW, ICE, VERY_WET, COLD_WET, WARM_WET, etc.)
4. Transiciones con delay (pista se adapta)
5. Filtrado de laptimes por condiciones similares
6. Best times por condiciones

---

## PASADA 23 — Sistema de datos congelados

### CrewChief: `FrozenOrderData.cs`

**Safety car / Rolling start**:
- `FrozenOrderPhase`: None, FCY, FormationStanding, Rolling, FastRolling
- `FrozenOrderColumn`: None, Left, Right
- `FrozenOrderAction`: Follow, CatchUp, AllowToPass, StayInPole, MoveToPole, PassSafetyCar
- `DriverToFollowRaw`: Piloto a seguir
- `SafetyCarSpeed`: Velocidad del safety car

---

## PASADA 24 — Sistema de reglas de stock cars

### CrewChief: `StockCarRulesData.cs`

**Reglas NASCAR/stock**:
- Lucky dog pass on outside/inside
- Wave around
- Move choose lane
- Two to green
- Penalty EOLL
- Leader choose lane

---

## PASADA 25 — Motor de juego multi-soporte

### CrewChief: `GameDataReader.cs` + mappers

**10+ juegos**:
- iRacing, rF2, rF1, Assetto Corsa, AMS2, PCars2/3, RaceRoom, GTR2, RBR, R3E

**Auto-detección**:
- Lee magic numbers de shared memory
- Detecta juego automáticamente
- Cambia de mapper sin intervención

---

## PASADA 26 — Loop principal (CrewChief.cs)

### Características del loop principal:

1. **Frecuencias variables**:
   - iRacing: 60Hz (`IRACING_INTERVAL = 16ms`)
   - Otros: configurable `update_interval`
   - Spotter: `spotterInterval` independiente
   - Start lights: `startLightsInterval = 10ms`

2. **Detección de proceso de juego**:
   - `IsGameRunning()` cada 1-2s
   - `DisconnectFromProcess()` si el juego se cierra

3. **Spotter thread separado**:
   - Thread dedicado para spotter
   - `gameDataReader.hasNewSpotterData()` para saber cuándo leer
   - `spotterInterval` independiente del loop principal

4. **Manejo de excepciones por evento**:
   - `maxEventFailuresBeforeDisabling = 10`
   - Deshabilita evento tras 10 fallos
   - `faultingEvents` + `faultingEventsCount`

5. **FCY spotter management**:
   - `waitingToPauseSpotter`
   - `minTurnSpotterOffForFCYTime` (10s)
   - `maxTurnSpotterOffForFCYTime` (30s)
   - No apaga inmediatamente en FCY, espera a que velocidad baje

6. **Pace notes auto-enable**:
   - `autoEnablePacenotesInPractice`
   - Detecta salida de garaje/pits

7. **Driver name loading**:
   - Carga sonidos de nombres al cambiar sesión
   - `SoundCache.loadDriverNameSounds()`
   - SRE grammar para nombres

8. **Session end handling**:
   - `sessionEndMessages.trigger()`
   - `audioPlayer.purgeQueues()`
   - `audioPlayer.disablePearlsOfWisdom = false`

---

## PASADA 27 — SessionEndMessages

### CrewChief: `SessionEndMessages.cs`

**Mensajes de fin de sesión**:

1. **Race**:
   - Posición 1: "won race"
   - Posición 2-3: "podium finish"
   - Posición 4+: "finished race PX" / rant si perdió muchas posiciones
   - Último: "finished race last" / rant
   - DNF: "finished race last"
   - DSQ: "disqualified"

2. **Qualify/Practice**:
   - Pole: "end of session pole"
   - Otro: "end of session, PX"
   - Expected finish position (solo qual)

3. **Rally**:
   - `CoDriver.PlayFinishMessage()`

**Lógica de rant**:
- Si perdió >= 9 posiciones Y es >= 50% del campo
- O si `failedExpectations` (expected + 5 < actual)
- `maxComplaintsPerSession` límite

---

## PASADA 28 — EngineMonitor

### CrewChief: `EngineMonitor.cs`

**Sistemas**:

1. **Temperaturas**:
   - `maxSafeWaterTemp` por clase de coche
   - `maxSafeOilTemp` por clase de coche
   - Muestra promedio de 60s
   - `HOT_WATER` / `HOT_OIL` / `HOT_OIL_AND_WATER`

2. **Presiones**:
   - `LOW_OIL_PRESSURE`
   - `LOW_FUEL_PRESSURE`

3. **Stall warning**:
   - `ENGINE_STALLED`
   - Solo en race/qual
   - No en coches eléctricos

4. **Voice commands**:
   - `WHAT_IS_MY_OIL_TEMP`
   - `WHAT_IS_MY_WATER_TEMP`
   - `WHAT_ARE_MY_ENGINE_TEMPS`

---

## PASADA 29 — LapCounter

### CrewChief: `LapCounter.cs` (55KB)

**Sistemas**:

1. **Pre-lights messages**:
   - Posición en parrilla
   - Ventana de pits
   - Longitud de carrera (laps/minutos)
   - "get ready"
   - Purga de cola al pulsar throttle

2. **Green flag**: "Green green green"

3. **Última vuelta**:
   - Leading: "last lap leading"
   - Top 3: "last lap top three"
   - General: "last lap" / "white flag last lap" (US terms)

4. **2 vueltas restantes**:
   - Leading: "two to go leading"
   - Top 3: "two to go top three"
   - General: "two to go"

5. **Formación manual**:
   - `manualFormationDoubleFile` — doble fila
   - `manualFormationGoWhenLeaderCrossesLine`
   - Grid side detection
   - "hold position behind [driver]"
   - "starting in left/right lane behind [driver]"
   - "leader has gone"
   - Detección de overtakes ilegales en formación

6. **Fin de sesión**: Integrado con SessionEndMessages

---

## PASADA 30 — MulticlassWarnings

### CrewChief: `MulticlassWarnings.cs` (56KB)

**Sistemas**:

1. **Detección de clases más rápidas/lentas**:
   - Calcula mejor vuelta por clase
   - Determina si clase es más rápida/lenta
   - Zonas de advertencia por tipo de pista

2. **Mensajes específicos**:
   - "faster cars behind" / "faster car behind"
   - "slower cars ahead" / "slower car ahead"
   - "faster cars fighting behind"
   - "you are being caught by the faster cars"
   - Nombres de clase: LMP1, LMP2, GT3, GTE, DTM, etc.

3. **Voice commands**:
   - `WHAT_CLASS_IS_CAR_AHEAD/BEHIND`
   - `IS_CAR_AHEAD/BEHIND_MY_CLASS`

---

## PASADA 31 — WatchedOpponents

### CrewChief: `WatchedOpponents.cs` (300 líneas)

**Sistemas**:

1. **Vigilancia de rivales específicos**:
   - `watchedOpponentKeys` — lista de vigilados
   - `teamMates` — compañeros de equipo
   - `rivals` — rivales

2. **Reportes automáticos**:
   - Laptime de vigilado: "[nombre] has just done a 1:34.2"
   - Salida de pits: "[nombre] is leaving the pits"
   - Cambio de posición: "[nombre] is now in P3"
   - Pit entry: "[nombre] is pitting from P3"

3. **Voice commands**:
   - `WATCH [nombre]` / `TEAM_MATE [nombre]` / `RIVAL [nombre]`
   - `STOP_WATCHING [nombre]` / `STOP_WATCHING_ALL`

---

## PASADA 32 — Eventos auxiliares

### CrewChief tiene muchos eventos auxiliares:

1. **`SafetyCarEvents.cs`**: Eventos específicos de safety car
2. **`Penalties.cs`** (1028+ líneas): 🔥 Sistema completo de penalizaciones
   - Cut track warnings progresivos (4 niveles: OK→MINOR→EXCESSIVE→TAKING_PISS)
   - Drive-through / Stop-and-go con 10+ causas detalladas
   - Sistema de 3/2/1 laps para servir penalización
   - Collision detection por incident points
   - Warning messages: wrong way, too slow, headlights, blue flag
   - DSQ: driving without headlights, exceeded lap count, ignored stop-and-go

3. **`Battery.cs`** (1082+ líneas): 🔥 Gestión de batería híbrida
   - **🚨 CRÍTICO para LMU WEC Hypercars/GT3 con VirtualEnergy**
   - Seguimiento por vuelta (ventana 5 laps) + por minuto
   - Thresholds dinámicos según consumo real
   - Detección de tendencia: INCREASING/DECREASING/STABLE
   - Sistema de consejos: "Increase/Reduce battery use", "Should make end"
   - Vehicle swap awareness para carreras de resistencia
   - Mensajes: LowBattery (10%), Critical (5%), HalfCharge, minutos/laps restantes

4. **`DriverSwaps.cs`** (100+ líneas): 🔥 Cambios de piloto
   - **🚨 CRÍTICO para LMU WEC**
   - DriverStintSecondsRemaining + DriverStintTotalSecondsRemaining
   - Mensajes: 15/10/5/2 minutos left in stint
   - "Pit this lap for driver change" / "No more stints"

5. **`RaceTime.cs`** (350+ líneas): Gestión de tiempo de sesión
   - Mensajes: 20/15/10/5/2/0 minutos remaining
   - "Half way home", "This is the last lap"
   - Extra laps after timed session (iRacing/rF2)
   - Deshabilitación de Pearls en últimos 3 minutos

6. **`Timings.cs`** (700+ líneas): Reporte de gaps
   - Gap status: CLOSE/INCREASING/DECREASING/OTHER/NONE
   - "Being held up" / "Being pressured" con track landmark analysis
   - "He is slower/faster through corner X, attack/defend there"
   - Reputation warnings (R3E): mal conductor detectado
   - Frecuencia configurable por setting

7. **`OvertakingAidsMonitor.cs`** (250+ líneas): DRS y Push-to-Pass
   - DRS beeps (detection + available)
   - DRS messages: "enabled"/"disabled", "off DRS range", "dont forget DRS"
   - Push-to-Pass: activaciones restantes, cooldown, recordatorios
   - DTM 2020 specific: reminder to use PtP

8. **`CommonActions.cs`** (400+ líneas): Orquestador de comandos
   - getStatus() → llama a 9 eventos diferentes
   - Keep quiet, deltas, yellow flags, cut warnings toggles
   - Pace notes recording/playback
   - Track landmark recording
   - Botones de volante mapeados a comandos

9. **`AlarmClock.cs`** (100+ líneas): Alarma horaria
   - Configurable por settings + voz
   - "Set alarm clock for X:Y" / "Clear alarm clock"

10. **`RaceTime.cs`**: Gestión de tiempo de sesión

### CrewChief tiene muchos eventos auxiliares:

1. **`SafetyCarEvents.cs`**: Eventos específicos de safety car
2. **`Penalties.cs`**: Penalizaciones drive-through, stop-and-go
3. **`Battery.cs`**: Gestión de batería híbrida (HERS, MGU-K, etc.)
4. **`RaceTime.cs`**: Gestión de tiempo de sesión
5. **`Timings.cs`**: Timing general
6. **`CommonActions.cs`**: Acciones comunes
7. **`IRacingBroadcastMessageEvent.cs`**: Mensajes broadcast iRacing
8. **`DriverSwaps.cs`**: Cambios de piloto
9. **`CoDriver.cs`**: Pace notes para rally
10. **`PitManagerVoiceCmds.cs`**: Comandos de voz para pits
11. **`OvertakingAidsMonitor.cs`**: DRS, push-to-pass
12. **`FrozenOrderMonitor.cs`**: Formación, safety car, rolling start

---

## RESUMEN FINAL

### Total de sistemas/funcionalidades identificados: **~70**

### Por severidad:

#### 🔴 CRÍTICO (bloquean funcionalidad sin LLM)
1. **rotation_yaw no leído** — Spotter cartesiano imposible
2. **Spotter cartesiano completo** — No detecta car left/right/clear/3-wide
3. **Evaluación paralela triggers** — 11/12 triggers bloqueados por break
4. **isMessageStillValid()** — Mensajes obsoletos se reproducen
5. **Conexión WebSocket Tauri→Backend** — Sin telemetría real
6. **SessionRunningTime** — Cooldowns rotos

#### 🟠 ALTO (funcionalidad principal ausente)
7. **Detección overtakes** — No anuncia overtake/being overtaken
8. **Sistema flags completo** — Sin FCY fases, blue flag, incidents
9. **Pit stops completo** — Sin countdown, mandatory stops, pit stall
10. **Combustible avanzado** — Sin ventana pits, max consumption, FCY adj
11. **Neumáticos avanzado** — Sin locking/spinning, camber, pressures
12. **Damage reporting completo** — Solo aero, sin engine/trans/susp/brakes
13. **LapTimes y sectores** — Sin deltas, pace analysis, outliers
14. **Opponents** — Sin leader change, retirement, tyre changes
15. **MessageFragment system** — Sin pausas, énfasis, estructura

#### 🟡 MEDIO (mejora de experiencia)
16. **Pearls of Wisdom** — Sin ánimo/desánimo natural
17. **Standby delays** — Sin delays naturales
18. **PushNow** — Sin push/pull estratégico
19. **Strategy** — Sin estimación post-parada
20. **LapCounter** — Sin pre-lights, última vuelta
21. **Driver names** — Sin nombres de rivales
22. **NumberReader** — Sin lectura natural de números
23. **TrackDefinition** — Sin definición de pista
24. **Conditions history** — Sin filtrado de pace por clima
25. **PreviousTick tracking** — No detecta cambios

#### 🟢 BAJO (nice to have)
26. **Multiclass** — Sin warnings de clases
27. **Watched opponents** — Sin seguimiento de rivales
28. **Speech recognition** — Sin comandos de voz
29. **Stock car rules** — Sin NASCAR/stock
30. **FrozenOrder** — Sin formación/safety car
31. **Session end messages** — Sin podio/ganador
32. **Driver training** — Sin modo entrenamiento
33. **Pace notes** — Sin notas de ritmo
34. **Multi-juego** — Solo LMU
35. **Audio devices** — Sin gestión avanzada
36. **Battery (VE)** 🔥 — Sin gestión de batería para Hypercars LMU WEC
37. **Penalties** 🔥 — Sin cut track, drive-through, stop-and-go, collision, DSQ
38. **DriverSwaps** 🔥 — Sin gestión de stints para LMU WEC
39. **RaceTime** — Sin mensajes de tiempo restante progresivos
40. **Timings** — Sin gap status tracking, sin track landmark analysis
41. **OvertakingAids** — Sin DRS/Push-to-Pass monitoring
42. **CommonActions** — Sin orquestador de comandos multi-evento
43. **AlarmClock** — Sin sistema de alarmas horarias
32. **Driver training** — Sin modo entrenamiento
33. **Pace notes** — Sin notas de ritmo
34. **Multi-juego** — Solo LMU
35. **Audio devices** — Sin gestión avanzada

---

## CAUSA RAÍZ DEFINITIVA

El spotter no funciona sin LLM por **3 capas concatenadas**:

### Capa 1: Datos rotos
- `rotation_yaw` no se lee → spotter cartesiano imposible
- WebSocket no conecta → datos simulados → `time_gap = 0.0` constante
- `SessionRunningTime` no existe → cooldowns basados en tiempo que va hacia atrás

### Capa 2: Arquitectura bloqueada
- 11/12 triggers son `LLM_REQUIRED` con `break` en ciclo
- Cuando LLM falla, el ciclo se bloquea
- Triggers `ALERT_ONLY` nunca se evalúan
- No hay validación de mensajes → spam

### Capa 3: Ausencia de sistemas CrewChief
- No hay overtake detection (necesita PreviousTick)
- No hay incident detection (necesita opponent speed/position tracking)
- No hay lap times (sin sectores, sin deltas)
- No hay damage reporting completo
- No hay pit stops completo
- No hay flags con fases
- No hay Pearl of Wisdom, standby, message fragments

---

*Documento generado tras análisis exhaustivo de ~25 archivos de CrewChiefV4 (C#) contra ~50 archivos de Vantare Ingeniero (Python/TypeScript).*
*Para revisión por DeepSeek V4 Pro.*
