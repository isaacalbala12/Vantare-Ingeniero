# 🏗️ ANÁLISIS DE INGENIERÍA INVERSA — CrewChiefV4
## Modelo arquitectónico completo para implementar en Vantare Ingeniero
### 5 pasadas analíticas desde datos frescos del repositorio GitLab

---

**Repositorio fuente**: https://gitlab.com/mr_belowski/CrewChiefV4
**Ramas analizadas**: `master` + `lmu`
**Archivos analizados**: ~30 archivos core de C# (~50K líneas)
**Fecha**: 31 mayo 2026

---

## PASADA 1 — Arquitectura del Mapper Genérico (GameDataReader + GameStateMapper)

### Hallazgo clave: CrewChief trata LMU como rF2 con variaciones mínimas

CrewChief **NO tiene un LMUDataMapper.cs separado**. En la rama `lmu`:
- El directorio `LMU/` solo contiene: `LMUPitMenuAPI.cs`, `LMUPitMenuAbstractionLayer.cs`, `LMUPitMenuController.cs`, `LMU_REST_API.cs`, `LMU_REST_API_classes.cs`
- El mapping de datos lo hace `RF2GameStateMapper.cs` con un `Game.LMU` flag
- El shared memory reader es el mismo `RF2SharedMemoryReader` que usa `rF2`

### Estructura del mapper genérico

```
GameDataReader (abstracto)
    └── RF2SharedMemoryReader (hereda)
            └── Lee shared memory mfx de LMU/rF2

GameStateMapper (abstracto)
    └── RF2GameStateMapper (hereda)
            └── RF2GameStateMapper(Game.RF2_64BIT) — rF2 settings
            └── RF2GameStateMapper(Game.LMU) — LMU settings

GameStateReaderFactory
    └── getGameStateMapper(GameDefinition gameDef) — factory
    └── getGameStateReader(GameDefinition gameDef) — factory
```

### ¿Cómo se instancia?

En `GameStateReaderFactory.cs`:
```csharp
if (gameDefinition.gameEnum == GameEnum.RF2_64BIT || gameDefinition.gameEnum == GameEnum.LMU)
    return new RF2GameStateMapper();
```

En `CrewChief.cs`:
```csharp
gameStateMapper = GameStateReaderFactory.getInstance().getGameStateMapper(gameDefinition);
gameDataReader = GameStateReaderFactory.getInstance().getGameStateReader(gameDefinition);
```

### Diferencias rF2 vs LMU en el mapper

En `RF2GameStateMapper` constructor:
```csharp
if (Game.RF2_64BIT)
{
    enablePitStopPrediction = settings.getBoolean("enable_rf2_pit_stop_prediction");
    // ... rf2 prefixed settings
}
else // Game.LMU
{
    enablePitStopPrediction = settings.getBoolean("enable_lmu_pit_stop_prediction");
    // ... lmu prefixed settings
}
```

### LMU REST API exclusiva

`LMU_REST_API.cs` expone:
- Puerto: `6397` (vs rF2 `5397`)
- Endpoints: `ReceivePitMenu`, `LoadPitMenu`, `OptionsSettings`, `Sessions`
- VirtualEnergy: Lee `mVirtualEnergy` desde shared memory en vez de REST
- Invulnerability: Lee `DRIVEAIDS_invulnerable` desde REST

### Conclusión para implementación

Nuestra implementación actual de LMUReader (`backend/src/services/lmu_reader.py`) es más detallada que el enfoque de CrewChief. CrewChief simplemente:
1. Lee shared memory cruda (RF2SharedMemoryReader → devuelve struct wrapper)
2. RF2GameStateMapper mapea structs → GameStateData
3. GameStateData pasa a events

**Lo que debemos copiar**: No el mapper (ya tenemos estructura de datos), sino la lógica de negocio (events).

---

## PASADA 2 — Pipeline de datos: De shared memory a GameStateData

### Flujo completo

```
[LMU Shared Memory mfx] 
    ↓ (16-60ms tick)
RF2SharedMemoryReader.ReadGameData(forSpotter)
    ↓ devuelve RF2StructWrapper
RF2GameStateMapper.mapToGameStateData(wrapper, previousGameState)
    ↓ devuelve GameStateData (5000 líneas, ~30 clases)
CrewChief.cs [loop principal]
    ↓ llama populateDerivedRaceSessionData()
    ↓ llama triggerEvents() para 30+ eventos
    ↓
Events.trigger(previousGameState, currentGameState)
    ↓
AudioPlayer.playMessage(QueuedMessage)
    ↓
NAudio/WaveOut → altavoz
```

### ¿Qué hace exactamente RF2GameStateMapper?

1. **Extrae SessionData**: 
   - `scoring.mScoringInfo.mSession` → SessionType
   - `scoring.mScoringInfo.mGamePhase` → SessionPhase
   - `scoring.mScoringInfo.mCurrentET` → SessionRunningTime
   - `extended.mVersion` → version check

2. **Extrae PositionAndMotionData**:
   - `telemetry.mPos.x/y/z` → WorldPosition[3]
   - `scoring.mVehicles[playerIdx].mOrientation[3][3]` → Rotation (Pitch, Roll, Yaw)
   - Cálculo del Yaw: `Math.Atan2(orientation[RowZ].x, orientation[RowZ].z)`
   - `telemetry.mLocalAccel.x/y/z` → AccelerationVector
   - `telemetry.mLocalVel.x/y/z` → LocalVelocity
   - `telemetry.mSpeed` → CarSpeed (directa, no derivada)

3. **Extrae vehicle data**:
   - `vehicle.mDriverName` → DriverRawName
   - `vehicle.mVehicleClass` → CarClass
   - `vehicle.mPlace` → OverallPosition
   - `vehicle.mTotalLaps` → CompletedLaps
   - `vehicle.mLapDist` → DistanceRoundTrack
   - `vehicle.mSector` → SectorNumber (0→3, 1→1, 2→2)
   - `vehicle.mTimeDeltaLeader` → DeltaTime
   - `vehicle.mBestLapTime` → CurrentBestLapTime
   - `vehicle.mLastLapTime` → LastLapTime

4. **Cálculo de deltas con diferencias de vuelta**:
   ```csharp
   // DeltaTime.cs
   public int GetSignedLapDifference(DeltaTime other)
   public float GetAbsoluteTimeDeltaAllowingForLapDifferences(DeltaTime other)
   public Tuple<int, float> GetSignedDeltaTimeWithLapDifference(DeltaTime other)
   ```

5. **Filtrado de posiciones en carrera** (anti-bouncing):
   ```csharp
   protected int getRacePosition(driverName, oldPosition, newPosition, now, isClassPosition)
   ```
   - Delay de 1s en cambios de posición
   - Solo acepta si nuevo valor se mantiene >1s

6. **Manejo de ghost vehicles**:
   - Filtra `driverName == "transparent trainer"` (isGhost)
   - No los incluye en opponent tracking

### Lo que NO hace nuestro LMUReader

| Función | CrewChief | Nosotros |
|---------|-----------|----------|
| Cálculo de Yaw desde matriz rotación | ✅ | ❌ |
| Delta con diferencias de vuelta | ✅ | ❌ (solo gaps simples) |
| Filtrado anti-bouncing posición | ✅ (1s delay) | ❌ |
| Detección de ghost vehicles | ✅ | ❌ |
| SessionRunningTime | ✅ (mCurrentET) | ❌ |
| JustGoneGreen / JustGoneCheckered | ✅ (transiciones) | ❌ |
| Lap validity tracking | ✅ | ❌ |
| Sector detection (IsNewSector) | ✅ | ❌ |
| Out/In lap detection | ✅ | ❌ |
| Pit lane approach heuristics | ✅ | ❌ |
| Frozen order data | ✅ | ❌ |
| Stock car rules | ✅ | ❌ |

---

## PASADA 3 — Ciclo de eventos: Cómo CrewChief decide QUÉ decir y CUÁNDO

### Loop principal (CrewChief.cs)

```csharp
while (running) {
    // 1. Leer shared memory
    Object nextRawData = gameDataReader.ReadGameData(forSpotter: false);
    
    // 2. Mapear a GameStateData
    GameStateData nextGameState = gameStateMapper.mapToGameStateData(nextRawData, currentGameState);
    
    // 3. Datos derivados
    if (race) gameStateMapper.populateDerivedRaceSessionData(nextGameState);
    else      gameStateMapper.populateDerivedNonRaceSessionData(nextGameState);
    
    // 4. Detectar inicio de sesión
    if (nextGameState.SessionData.IsNewSession) {
        displayNewSessionInfo(nextGameState);
        audioPlayer.purgeQueues();
        foreach (event in eventsList) event.clearState();
        SoundCache.loadDriverNameSounds(...);
        if (spotter) spotter.clearState();
    }
    
    // 5. Detectar fin de sesión
    if (currentGameState.SessionData.SessionPhase == SessionPhase.Finished) {
        audioPlayer.purgeQueues();
        sessionEndMessages.trigger(...);
        audioPlayer.disablePearlsOfWisdom = false;
    }
    
    // 6. Gestionar spotter (FCY, driver OK)
    if (DamageReporting.waitingForDriverIsOKResponse) spotter.pause();
    else if (FCY) spotter.pause();
    else spotter.unpause();
    
    // 7. Disparar eventos
    foreach (event in eventsList) {
        if (event.isApplicableForCurrentSessionAndPhase(sessionType, sessionPhase)) {
            if (eventName != "DamageReporting" || !waitingForDriverIsOKResponse) {
                triggerEvent(eventName, event, previousGameState, currentGameState);
            }
        }
    }
    
    // 8. Reproductor de audio
    audioPlayer.wakeMonitorThreadForRegularMessages(currentGameState.Now);
    
    // 9. Thread del spotter
    if (spotter != null && !spotterIsRunning)
        startSpotterThread();
    
    // 10. Sleep
    Thread.Sleep(timeInterval); // 16ms (iRacing) o configurable
}
```

### ¿Qué hace triggerEvent?

```csharp
private void triggerEvent(eventName, abstractEvent, previous, current) {
    try {
        abstractEvent.trigger(previous, current);
    } catch (Exception e) {
        failureCount++;
        if (failureCount >= maxEventFailuresBeforeDisabling) {
            sessionHasFailingEvent = true;
            // Deshabilita el evento por el resto de la sesión
        }
    }
}
```

### ¿Qué hace abstractEvent.trigger?

```csharp
public void trigger(previousGameState, currentGameState) {
    // Checks comunes (si los hubiera)
    triggerInternal(previousGameState, currentGameState);
}
```

Cada evento implementa `triggerInternal()` con su lógica específica.

### ¿Cuándo se considera que la sesión está corriendo?

```csharp
private bool shouldTriggerEvents(previousGameState, currentGameState) {
    if (previousGameState == null) return false;
    
    // Normal: tiempo avanza
    if (current.SessionRunningTime > previous.SessionRunningTime) return true;
    if (previous.SessionPhase != current.SessionPhase) return true;
    
    // Juego-específico:
    // F1 2018-2021: siempre
    // PCars2/AMS2: solo en Countdown o FixedTime
    // ACC: formation, hotlap
    // rF2: gridwalk (para warnings)
}
```

### El sistema de spotter thread separado

```csharp
private void spotterWork() {
    while (runSpotterThread) {
        if (spotter != null && gameDataReader.hasNewSpotterData()) {
            currentSpotterState = gameDataReader.ReadGameData(forSpotter: true);
            if (lastSpotterState != null && currentSpotterState != null) {
                spotter.trigger(lastSpotterState, currentSpotterState, currentGameState);
            }
            lastSpotterState = currentSpotterState;
        }
        Thread.Sleep(spotterInterval); // 16ms (iRacing) o configurable
    }
}
```

**Clave**: El spotter corre en su PROPIO THREAD con su PROPIO intervalo. No está bloqueado por el loop principal.

### Conclusión para implementación

Nuestra arquitectura actual tiene un solo loop asyncio. Para emular a CrewChief necesitamos:

1. **Loop principal** (2-20Hz): Lectura de datos + eventos principales
2. **Loop de spotter** (10-60Hz): Solo spotter cartesiano, thread separado
3. **Loop de evaluación LLM** (0.5Hz): Aparte, no bloquea los otros loops

**Regla de CrewChief**: El spotter NUNCA debe ser bloqueado por la evaluación de eventos o el LLM.

---

## PASADA 4 — Sistema de mensajes y audio: De evento a altavoz

### Pipeline completo de mensaje

```
Evento → MessageFragment(s) → QueuedMessage → AudioPlayer → SoundCache → NAudio → Altavoz
```

### 1. MessageFragment — Construcción del mensaje

```csharp
public static List<MessageFragment> MessageContents(
    Object o1, // Puede ser: string (folder path), int, OpponentData, TimeSpanWrapper, Pause
    Object o2,
    ...
)
```

Tipos de fragmentos:
- `MessageFragment.Text("rutas/sonido")` → Referencia a archivo de audio
- `MessageFragment.Integer(5)` → Número leído con NumberReader
- `MessageFragment.Time(TimeSpanWrapper)` → Tiempo con precisión adaptativa
- `MessageFragment.Opponent(opponentData)` → Nombre/número automático
- `MessageFragment.Pause(200)` → Silencio de 200ms

**Ejemplo real** (PitStops):
```csharp
MessageContents(folderBoxNow, 5, folderBoxIn, 4, folderBoxIn, 3, folderBoxIn, 2, folderBoxIn, 1, folderBoxIn, folderBoxNow)
```
Esto produce: "BOX NOW... 5... 4... 3... 2... 1... BOX NOW"

### 2. QueuedMessage — El mensaje en cola

```csharp
class QueuedMessage {
    string messageName;          // Identificador único
    int expiryTime;              // Tiempo hasta expirar (segundos)
    int secondsDelay;            // Delay antes de poner en cola
    List<MessageFragment> messageFragments;  // Mensaje principal
    List<MessageFragment> alternateMessageFragments;  // Alternativa si faltan sonidos
    Dictionary<string, object> validationData;  // Para validación al reproducir
    Dictionary<string, object> delayedMessageEvent;  // Evalúa en el momento de reproducir
    SoundMetadata metadata;      // Tipo + prioridad
    AbstractEvent abstractEvent; // Evento origen (para isMessageStillValid)
    int priority;                // 0-20
    bool canBePlayed;            // Flag de cancelación
}
```

**3 formas de crear mensajes**:

```csharp
// Normal (cola regular)
audioPlayer.playMessage(new QueuedMessage("nombre", 10, 
    messageFragments: ..., abstractEvent: this, priority: 5));

// Inmediato (interrumpe)
audioPlayer.playMessageImmediately(new QueuedMessage("nombre", 0,
    type: SoundType.CRITICAL_MESSAGE, priority: 15));

// Spotter (prioridad 20, canal abierto)
audioPlayer.playSpotterMessage(new QueuedMessage("spotter/car_left", 1000));
```

### 3. AudioPlayer — Gestión de colas

**Dos colas**:
```csharp
private OrderedDictionary queuedClips;    // Cola normal
private OrderedDictionary immediateClips; // Cola inmediata
```

**Inserción por prioridad**:
```csharp
private int getInsertionIndex(OrderedDictionary queue, QueuedMessage msg) {
    // Insert WHERE priority > existingMessagePriority
    // Mayor prioridad = antes en la cola
}
```

**Monitor thread**:
```csharp
private void monitorQueue() {
    while (monitorRunning) {
        // 1. Revisar mensajes vencidos, llamar isMessageStillValid
        // 2. Reproducir siguiente mensaje de immediateClips
        // 3. Si no hay inmediatos, reproducir siguiente de queuedClips
        // 4. Esperar wakeup event o timeout
    }
}
```

**Purgado**:
```csharp
public int purgeQueues() {
    purgeQueue(queuedClips, false);
    purgeQueue(immediateClips, true);
}
// NO elimina: sessionEndMessages, smokeTest, RETAIN_ON_SESSION_END
```

### 4. Validación en reproducción

Cuando un mensaje vence O está a punto de reproducirse:
```csharp
abstractEvent.isMessageStillValid(eventSubType, currentGameState, validationData)
```

Ejemplo (PitStops):
```csharp
if (eventSubType == folderPitStopRequestReceived) {
    return currentGameState.PitData.HasRequestedPitStop;
}
```

Ejemplo (Opponents):
```csharp
if (validationData.TryGetValue(validationDriverAheadKey, out validationValue)) {
    string expectedOpponent = (string)validationValue;
    OpponentData actualOpponent = getOpponentInFront();
    if (actualOpponent.DriverRawName != expectedOpponent) return false;
}
```

### 5. SoundCache — Caché de audio

```csharp
class SoundCache {
    static bool cancelLazyLoading;
    static bool cancelDriverNameLoading;
    static Thread cacheSoundsThread;
    
    void Play(string folder, SoundMetadata metadata);
    void loadDriverNameSounds(List<string> driverNames);
    static void InterruptCurrentlyPlayingSound(bool allowBeepInterrupt);
    void ExpireCachedSounds();
}
```

Los sonidos son archivos `.wav` precargados en memoria. No hay TTS para mensajes comunes — solo para nombres de pilotos y números.

### Conclusión para implementación

Nuestro sistema actual es:
- Generamos texto → lo enviamos a TTS (Edge/Piper) → reproducción
- Cola FIFO simple, sin prioridades
- Sin validación de mensajes
- Sin MessageFragment system

**Lo que necesitamos**:
1. **Sistema de MessageFragment** → audios pre-grabados para mensajes comunes
2. **Dual cola con prioridades** → normal + inmediata
3. **Validación en reproducción** → isMessageStillValid
4. **Audio pre-cargado** → para spotter <100ms de latencia
5. **Thread separado para monitor de cola**

---

## PASADA 5 — Arquitectura específica de LMU en CrewChief

### ¿Qué hace CrewChief EXACTAMENTE para LMU?

Basado en el código de `RF2GameStateMapper` con flag `Game.LMU`:

#### 1. Shared Memory
Usa el mismo formato mfx que rF2:
- `rF2Scoring.mScoringInfo` → datos de sesión
- `rF2VehicleScoring[]` → datos de cada vehículo
- `rF2VehicleTelemetry` → telemetría del jugador
- `rF2Extended` → datos extendidos (versión, frozen order, LSI)

**Campos específicos para LMU**:
```csharp
// En rF2VehicleScoring:
mDriverName     → string
mVehicleClass   → string  
mPlace          → int (posición)
mTotalLaps      → int (vueltas completadas)
mLapDist        → float (distancia en pista)
mSector         → int (0=last, 1, 2)
mTimeDeltaLeader → float (gap al líder)
mBestLapTime    → float (mejor vuelta)
mLastLapTime    → float (última vuelta)
mInPits         → int (0/1)
mTrackSurf      → int (superficie)
mID             → long (ID único)
mVehicleName    → string
mExpansion      → byte[] (datos extra)

// En rF2VehicleTelemetry:
mPos.x/y/z      → float (posición mundial)
mLocalAccel.x/y/z → float (aceleración)
mLocalVel.x/y/z → float (velocidad local)
mSpeed          → float (velocidad m/s)
mGear           → int (marcha)
mEngineRPM      → float
mEngineWaterTemp → float
mEngineOilTemp  → float
mFuelInTank     → float
mFuelCapacity   → float
mTireFL/Friction→ float (temperatura/desgaste)
mTireFR/Friction→ float
mTireRL/Friction→ float
mTireRR/Friction→ float
mBrakeTemps     → float[4]
mBrakeWear      → float[4]
mVirtualEnergy  → float (solo Hypercars/GT3)

// En rF2Extended:
mVersion        → string (ej: "3.7.14.0")
mSessionStarted → int
mTicksSessionEnded → long
mGamePhase      → int (para LMU)
mLSIPhaseMessage → string (para LMU)
mLSIOrderInstructionMessage → string
mLSIRulesInstructionMessage → string
mUnsubscribedBuffersMask → int
mDirectMemoryAccessEnabled → int
mSCRPluginEnabled → int
```

#### 2. Obtención de Yaw

```csharp
// RF2GameStateMapper.cs línea ~1400
private static PositionAndMotionData.Rotation GetRotation(ref rF2Vec3[] orientation)
{
    return new PositionAndMotionData.Rotation() {
        Yaw = (float)Math.Atan2(
            orientation[rFactor2Constants.RowZ].x,  // orientation[2].x
            orientation[rFactor2Constants.RowZ].z   // orientation[2].z
        ),
        Pitch = (float)Math.Atan2(
            -orientation[rFactor2Constants.RowY].z,
            Math.Sqrt(orientation[RowX].z^2 + orientation[RowZ].z^2)
        ),
        Roll = (float)Math.Atan2(
            orientation[rFactor2Constants.RowY].x,
            Math.Sqrt(orientation[RowX].x^2 + orientation[RowZ].x^2)
        )
    };
}
```

La orientación se obtiene de `vehicleScoring.mOrientation`, que es una matriz 3x3 de `rF2Vec3` (la matriz de rotación del vehículo).

#### 3. Sistema de pit menu (LMU REST API)

```csharp
// LMU_REST_API.cs
private const string URL = "http://localhost:6397";

// Endpoints:
ReceivePitMenu → GET /rest/garage/UIScreen/RepairAndRefuel
LoadPitMenu    → POST (envía cambios)
OptionsSettings → GET /rest/system/settings (para invulnerability)
Sessions       → GET /rest/sessions (para fuel multiplier)
```

#### 4. Virtual Energy

```csharp
// VirtualEnergy.cs
public static int VE { get; set; }
public static int Read() {
    if (Game.LMU) return VE; // Lee desde shared memory mVirtualEnergy
    return Int32.MaxValue; // No aplica para otros juegos
}
```

#### 5. Cuándo es LMU vs rF2

```csharp
// En RF2GameStateMapper:
if (Game.RF2_64BIT) { ... }
else if (Game.LMU) { ... }

// En FrozenOrderData:
if (Game.RF2_64BIT) { /* rF2 column enum */ }
else // Game.LMU
{
    if ((lmuTrackRulesColumn)vehicleRules.mColumnAssignment == lmuTrackRulesColumn.LeftLane)
        fod.AssignedColumn = FrozenOrderColumn.Left;
}
```

### Conclusión: Diferencia entre nuestra app y el enfoque de CrewChief

| Aspecto | CrewChief LMU | Nosotros (Vantare) |
|---------|---------------|---------------------|
| Reader | RF2SharedMemoryReader (mfx) | LMUReader (Python ctypes) |
| Mapper | RF2GameStateMapper → GameStateData | Flat dict (80 campos) |
| Yaw | ✅ `Atan2(orientation[2].x, orientation[2].z)` | ❌ No leemos |
| VirtualEnergy | ✅ `mVirtualEnergy` en shared memory | ❌ No leemos |
| Pit menu | ✅ REST API `:6397` | ❌ No tenemos |
| Invulnerability | ✅ `DRIVEAIDS_invulnerable` | ❌ No tenemos |
| Fuel multiplier | ✅ `SESSSET_Fuel_Usage` | ❌ No tenemos |
| Driver names | ✅ `mDriverName` (string) | ❌ Solo índices |
| Delta con lap diff | ✅ `DeltaTime` class | ❌ Solo gaps |
| Anti-bouncing pos | ✅ 1s delay | ❌ |

---

## TABLA COMPARATIVA: Eventos CrewChief vs Nuestros Triggers

| Evento CrewChief | Archivo | Líneas | ¿Tenemos? | Acción |
|-----------------|---------|--------|-----------|--------|
| Spotter (cartesiano) | NoisyCartesianCoordinateSpotter.cs | 1000+ | ❌ Parcial | ALERT_ONLY |
| Position | Position.cs | 1000+ | ❌ | ALERT_ONLY |
| PitStops | PitStops.cs | 1500+ | ❌ Parcial | ALERT_ONLY |
| Fuel | Fuel.cs | 900+ | ❌ Parcial | ALERT_ONLY |
| TyreMonitor | TyreMonitor.cs | 2500+ | ❌ Parcial | ALERT_ONLY |
| FlagsMonitor | FlagsMonitor.cs | 1600+ | ❌ Parcial | ALERT_ONLY |
| DamageReporting | DamageReporting.cs | 1087+ | ❌ | ALERT_ONLY |
| EngineMonitor | EngineMonitor.cs | 250+ | ❌ | ALERT_ONLY |
| Opponents | Opponents.cs | 1200+ | ❌ | ALERT_ONLY |
| LapTimes | LapTimes.cs | 900+ | ❌ | ALERT_ONLY |
| LapCounter | LapCounter.cs | 1500+ | ❌ | ALERT_ONLY |
| PushNow | PushNow.cs | 400+ | ❌ | ALERT_ONLY |
| Strategy | Strategy.cs | 1500+ | ❌ | ALERT_ONLY |
| MulticlassWarnings | MulticlassWarnings.cs | 900+ | ❌ | ALERT_ONLY |
| WatchedOpponents | WatchedOpponents.cs | 300+ | ❌ | ALERT_ONLY |
| SessionEndMessages | SessionEndMessages.cs | 150+ | ❌ | ALERT_ONLY |
| Battery | Battery.cs | ~200 | ❌ Parcial | ALERT_ONLY |
| Penalties | Penalties.cs | ~200 | ❌ | ALERT_ONLY |
| ConditionsMonitor | ConditionsMonitor.cs | ~300 | ❌ | ALERT_ONLY |
| FrozenOrderMonitor | FrozenOrderMonitor.cs | ~400 | ❌ | ALERT_ONLY |
| OvertakingAidsMonitor | OvertakingAidsMonitor.cs | ~100 | ❌ | ALERT_ONLY |
| DriverTrainingService | DriverTrainingService.cs | ~500 | ❌ | ALERT_ONLY |

**Total eventos CrewChief: ~22+**
**Total triggers nuestros: 12 (1 ALERT_ONLY)**

---

## PLAN DE IMPLEMENTACIÓN — Prioridades

### Fase 0 — Infraestructura (urgente, 1 semana)

1. **Leer rotation_yaw de shared memory**
   - Desde `vehicle.mOrientation` (matriz 3x3 de rF2Vec3)
   - Calcular: `Atan2(orientation[2].x, orientation[2].z)`

2. **Arreglar WebSocket Tauri→Backend**
   - Verificar IP/puerto en configuración
   - Asegurar que `useWebSocket.ts` se ejecuta

3. **SessionRunningTime**
   - Leer `mCurrentET` en lugar de solo session_time_remaining
   - Almacenar ambas

4. **Desbloquear ciclo de triggers**
   - Eliminar `break` para ALERT_ONLY
   - Evaluar todos los triggers, no parar en LLM_REQUIRED

### Fase 1 — Spotter determinista (2 semanas)

5. **Implementar NoisyCartesianCoordinateSpotter**
   - Algoritmo cartesiano con Yaw
   - Car left/right/clear/3-wide
   - Velocidad de cierre
   - Delays configurables
   - "Still there" con repeat

6. **Añadir PreviousTick tracking**
   - Guardar estado de oponentes entre ticks
   - Detectar cambios de posición, retirements

7. **Sistema de cola dual de audio**
   - Normal + inmediata
   - Prioridades 0-20
   - Spotter con prioridad 20

### Fase 2 — Eventos core (3 semanas)

8. **Position** — Overtakes, race start, position reminders
9. **PitStops** — Countdown, limiter, mandatory stops, pit stall
10. **Fuel** — Windows, max consumption, FCY adjustment
11. **Opponents** — Leader change, retirements, tyre changes
12. **FlagsMonitor** — FCY 7 fases, blue flag, incident detection

### Fase 3 — Eventos avanzados (4+ semanas)

13. **LapTimes** — Sector deltas, consistency, outliers
14. **DamageReporting** — Componentes, puncture, crash detection
15. **EngineMonitor** — Temps, pressures, stall
16. **MulticlassWarnings** — Clases más rápidas/lentas
17. **WatchedOpponents** — Vigilancia de rivales
18. **MessageFragment system** — Pausas, nombres, números
19. **Pearls of Wisdom** — Mensajes aleatorios
20. **Standby delays** — Respuestas con delay

---

*Documento generado tras 5 pasadas adicionales con datos frescos del repositorio GitLab de CrewChiefV4 (rama `master` + rama `lmu`).*
*Contiene el modelo arquitectónico exacto que usa CrewChief para LMU, incluyendo la lectura de shared memory, el pipeline de datos, el ciclo de eventos, el sistema de audio y la lógica específica de LMU.*
