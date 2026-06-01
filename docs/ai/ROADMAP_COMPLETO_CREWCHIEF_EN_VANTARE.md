# 🏗️ ROADMAP COMPLETO — Replicar CrewChiefV4 en Vantare Ingeniero
## Documento maestro de implementación: todas las funcionalidades, todos los detalles

**Versión**: 1.0  
**Fecha**: 31 mayo 2026  
**Basado en**: 30+ pasadas de análisis sobre ~30 archivos core de CrewChiefV4 (C#, ~50K líneas)  
**Repo fuente**: https://gitlab.com/mr_belowski/CrewChiefV4 (rama `master` + `lmu`)

---

## 📋 ÍNDICE DE SISTEMAS A DESARROLLAR

1. Infraestructura Base
2. Modelo de Datos Unificado (GameStateData)
3. Sistema de Spotter Cartesiano
4. Sistema de Eventos
5. Sistema de Audio y Mensajes
6. Sistema de Oponentes
7. Sistema de Vueltas y Tiempos
8. Sistema de Combustible
9. Sistema de Neumáticos
10. Sistema de Banderas e Incidentes
11. Sistema de Pits
12. Sistema de Daños
13. Sistema de Motor
14. Sistema de Estrategia
15. Sistema de Clima
16. Sistema de Control de Voz
17. Sistema de Personalización
18. Sistema de Configuración y Persistencia
19. Sistema de Formación/Safety Car
20. Sistema Multiclase
21. Sistema de Oponentes Vigilados
22. Sistema de Fin de Sesión
23. Sistema de Pearls of Wisdom
24. Sistema de Audio Avanzado
25. Sistema de Pipeline LLM

---

## FASE 0 — INFRAESTRUCTURA BASE (URGENTE)

### 0.1 Leer rotation_yaw de shared memory

**Archivo a modificar**: `backend/src/services/lmu_reader.py`

**Campo CrewChief**: `vehicleScoring.mOrientation[RowZ].x` y `vehicleScoring.mOrientation[RowZ].z`
**Fórmula CrewChief**: `Yaw = Math.Atan2(orientation[RowZ].x, orientation[RowZ].z)`

Donde `orientation` es una matriz 3x3 de `rF2Vec3` (struct con x,y,z) obtenida de la shared memory de LMU.

**Campos a añadir al flat dict**:
```python
"orientation": {  # Matriz 3x3 de rotación
    "row_x": {"x": float, "y": float, "z": float},
    "row_y": {"x": float, "y": float, "z": float},
    "row_z": {"x": float, "y": float, "z": float},
},
"rotation": {
    "yaw": float,    # Atan2(row_z.x, row_z.z) en radianes
    "pitch": float,  # Atan2(-row_y.z, sqrt(row_x.z^2 + row_z.z^2))
    "roll": float,   # Atan2(row_y.x, sqrt(row_x.x^2 + row_z.x^2))
},
"speed_ms": float,  # mSpeed directa de telemetría (no derivada)
"acceleration": {
    "long": float,   # mLocalAccel.x (m/s²)
    "lat": float,    # mLocalAccel.y
    "vert": float,   # mLocalAccel.z
},
"velocity_local": {
    "x": float,      # mLocalVel.x (m/s)
    "y": float,
    "z": float,
},
```

**Dependencias**: Ninguna  
**Esfuerzo**: 1 día  
**Prioridad**: 🔴 1

---

### 0.2 SessionRunningTime

**Archivo a modificar**: `backend/src/services/lmu_reader.py`

Leer `scoring.mCurrentET` (tiempo transcurrido de sesión en segundos).

**Campos a añadir**:
```python
"session_running_time": float,  # Tiempo desde que empezó la sesión (va hacia adelante)
"session_time_remaining": float, # Tiempo restante (ya existe)
```

**Impacto**: Sin este campo, los cooldowns basados en tiempo no funcionan (actualmente solo tenemos tiempo restante, que va hacia atrás).

**Dependencias**: Ninguna  
**Esfuerzo**: 0.5 días  
**Prioridad**: 🔴 2

---

### 0.3 Arreglar conexión WebSocket Tauri → Backend

**Archivos**: `frontend/src/hooks/useWebSocket.ts`, `frontend/src/store/config.ts`, `backend/src/routers/websocket.py`

**Problema**: El frontend no conecta por WebSocket al backend.

**Solución**:
1. Verificar que `config.vllmIP` y `config.serverPort` sean correctos
2. Asegurar que `useWebSocket()` se llama en el árbol de componentes
3. Añadir logging explícito en la conexión WebSocket
4. En el backend, verificar que `/ws` acepta conexiones

**Dependencias**: Ninguna  
**Esfuerzo**: 1 día  
**Prioridad**: 🔴 3

---

### 0.4 Desbloquear ciclo de triggers

**Archivo a modificar**: `backend/src/intelligence/engine.py`

**Cambio 1**: Eliminar el `break` en el ciclo de evaluación para triggers `ALERT_ONLY`
```python
# Actual: break después de LLM_REQUIRED bloquea todo
# Nuevo: dos pasadas
for trigger in triggers:
    if trigger.action in [LLM_REQUIRED, DETERMINISTIC_ONLY]:
        if trigger.evaluate(...):
            break  # Solo bloquea LLM_REQUIRED y DETERMINISTIC

for trigger in triggers:
    if trigger.action == ALERT_ONLY:
        trigger.evaluate(...)  # Siempre se evalúan
```

**Cambio 2**: Todos los triggers que no requieren LLM deben ser `ALERT_ONLY`:
- SafetyCarTrigger → ALERT_ONLY (no necesita LLM)
- FuelCriticalTrigger → ALERT_ONLY (es determinista)
- GapClosedTrigger → ALERT_ONLY (es determinista)
- TiresThermalOverheatingTrigger → ALERT_ONLY (es determinista)
- PitWindowOpenedTrigger → ALERT_ONLY (es determinista)
- PitWindowClosingTrigger → ALERT_ONLY (es determinista)
- CompetitorPittedTrigger → ALERT_ONLY (es determinista)

**Dependencias**: Ninguna  
**Esfuerzo**: 0.5 días  
**Prioridad**: 🔴 4

---

### 0.5 PreviousTick tracking

**Archivos a crear**: `backend/src/services/state_diff.py`

**Arquitectura CrewChief**: Cada evento recibe `previousGameState` y `currentGameState`. CrewChief puede consultar el estado de oponentes en el tick anterior mediante `previousTick: true`.

**Implementación**:
```python
class StateDiff:
    """Detecta cambios entre ticks de telemetría."""
    
    def __init__(self):
        self._prev_state: Optional[dict] = None
        self._prev_opponents: Dict[str, dict] = {}
    
    def update(self, current: dict) -> 'TickChanges':
        """Compara estado actual vs anterior y devuelve cambios."""
        changes = TickChanges()
        
        if self._prev_state:
            # Cambios de posición
            if current.get("place") != self._prev_state.get("place"):
                changes.position_changed = True
                changes.old_position = self._prev_state.get("place")
                changes.new_position = current.get("place")
            
            # Cambios de líder
            if current.get("leader_raw_name") != self._prev_state.get("leader_raw_name"):
                changes.leader_changed = True
                changes.old_leader = self._prev_state.get("leader_raw_name")
                changes.new_leader = current.get("leader_raw_name")
            
            # Entrada/salida de pits de oponentes
            # Retirements
            # Cambios de neumáticos
            # Nuevas vueltas
            # Nuevos sectores
            
        self._prev_state = deepcopy(current)
        return changes
    
    def get_opponent_at_position(self, pos: int, previous_tick: bool = False) -> Optional[dict]:
        """Obtiene oponente en una posición, opcionalmente del tick anterior."""
        state = self._prev_state if previous_tick else self._current_state
        ...
```

**Campos a añadir a oponentes en flat dict** (50+ campos por rival):
```python
"rivals": [
    {
        "driver_raw_name": str,       # mDriverName
        "car_number": str,            # Número de coche
        "place": int,                 # Posición general
        "class_place": int,           # Posición en clase
        "speed": float,               # Velocidad m/s
        "distance_round_track": float, # Posición en pista
        "gap_to_player": float,       # Gap en segundos
        "laps_completed": int,        # Vueltas completadas
        "current_lap_time": float,    # Tiempo de vuelta actual
        "last_lap_time": float,       # Última vuelta
        "best_lap_time": float,       # Mejor vuelta
        "in_pits": bool,              # En boxes
        "is_active": bool,            # Activo (no ghost)
        "is_entering_pits": bool,     # Entrando a boxes
        "is_exiting_pits": bool,      # Saliendo de boxes
        "current_sector": int,        # Sector actual
        "current_tyre_compound": str, # Compound actual
        "has_just_changed_tyres": bool, # Cambió de compound
        "vehicle_class": str,         # Clase del vehículo
        "delta_to_player": {          # Delta con diferencias de vuelta
            "lap_difference": int,    # Diferencia de vueltas
            "time_delta": float,      # Diferencia de tiempo
        },
    }
    for rival in racing_rivals[:6]
]
```

**Dependencias**: 0.1 (orientation/yaw), 0.2 (SessionRunningTime)  
**Esfuerzo**: 3 días  
**Prioridad**: 🔴 5

---

## FASE 1 — MODELO DE DATOS UNIFICADO

### 1.1 Crear GameStateData equivalente

**Archivo a crear**: `backend/src/models/game_state_data.py`

**Estructura CrewChief** (5000 líneas, ~30 clases):

```python
@dataclass
class SessionData:
    session_type: str                # Practice, Qualify, Race, HotLap, LonePractice
    session_phase: str               # Unavailable, Garage, Gridwalk, Formation, Countdown, Green, FullCourseYellow, Checkered, Finished
    session_running_time: float      # Tiempo transcurrido
    session_time_remaining: float    # Tiempo restante
    session_total_run_time: float    # Tiempo total de sesión
    session_number_of_laps: int      # Vueltas totales
    session_laps_remaining: int      # Vueltas restantes
    session_has_fixed_time: bool     # Si la sesión es por tiempo
    completed_laps: int              # Vueltas completadas
    player_lap_time_session_best: float  # Mejor vuelta personal
    player_lap_time_previous: float  # Última vuelta
    previous_lap_was_valid: bool     # Última vuelta válida
    current_lap_is_valid: bool       # Vuelta actual válida
    lap_time_previous: float         # Tiempo de última vuelta
    class_position: int              # Posición en clase
    overall_position: int            # Posición general
    num_cars_overall: int            # Coches totales
    num_cars_in_player_class: int    # Coches en clase
    num_cars_in_player_class_at_start: int  # Coches en clase al inicio
    session_start_class_position: int  # Posición inicial
    class_position_at_start_of_current_lap: int
    is_new_lap: bool                 # Transición de vuelta
    is_new_sector: bool              # Transición de sector
    sector_number: int               # Sector 1/2/3
    just_gone_green: bool            # Transición a verde
    just_gone_checkered: bool        # Transición a bandera a cuadros
    has_lead_changed: bool           # Cambio de líder
    is_racing_same_car_in_front: bool  # Mismo coche delante
    is_racing_same_car_behind: bool    # Mismo coche detrás
    game_time_at_last_position_front_change: float  # Para PushNow
    game_time_at_last_position_behind_change: float  # Para PushNow
    driver_raw_name: str             # Nombre del piloto
    player_car_nr: str               # Número de coche
    track_definition: 'TrackDefinition'  # Definición de pista
    expected_finishing_position: Tuple[int, int]  # Posición esperada
    is_disqualified: bool
    is_dnf: bool
    is_last_lap: bool
    leader_sector_number: int
    laps_delta_front: int
    laps_delta_behind: int
    time_delta_front: float
    time_delta_behind: float
    extra_laps_after_timed_session: int
    formatted_player_lap_times: List[str]
    abrupt_session_end_detected: bool
    is_new_session: bool

@dataclass
class TrackDefinition:
    name: str
    track_length: float
    track_length_class: str  # VERY_SHORT, SHORT, MEDIUM, LONG, VERY_LONG
    corners: List[Corner]
    landmarks: List[str]
    pit_box_position: float       # Posición de boxes en track distance
    pit_exit_position: float      # Posición de salida de pits
    distance_for_near_pit_entry_checks: float
    is_oval: bool

@dataclass
class Corner:
    name: str
    distance: float  # Distancia en pista
    start: float
    end: float

@dataclass
class PositionAndMotionData:
    world_position: Tuple[float, float, float]  # X, Y, Z
    orientation: Rotation                        # Pitch, Roll, Yaw
    local_velocity: Tuple[float, float, float]   # X, Y, Z m/s
    local_acceleration: Tuple[float, float, float]  # X, Y, Z m/s²
    car_speed: float  # m/s (directo de telemetría)
    distance_round_track: float

@dataclass
class Rotation:
    pitch: float  # radianes
    roll: float   # radianes
    yaw: float    # radianes — CRÍTICO para spotter cartesiano

@dataclass
class PitData:
    in_pitlane: bool
    is_in_garage: bool
    on_out_lap: bool
    has_requested_pit_stop: bool
    pit_window: str                 # Unavailable, Disabled, Closed, Open, StopInProgress, Completed
    pit_window_start: float         # Tiempo/minuto de apertura
    pit_window_end: float           # Tiempo/minuto de cierre
    has_mandatory_pit_stop: bool
    mandatory_pit_stop_completed: bool
    mandatory_pit_min_duration_left: float
    pit_speed_limit: float          # km/h
    pit_stall_occupied: bool
    pit_box_position_estimate: float
    pit_box_location_estimate: Tuple[float, float]
    leader_is_pitting: bool
    car_in_front_is_pitting: bool
    car_behind_is_pitting: bool
    is_at_pit_exit: bool
    limiter_status: str             # INACTIVE, ACTIVE
    is_approaching_pits: bool
    pit_speed_limit_warning_announced: bool

@dataclass
class FlagData:
    sector_flags: List[str]         # GREEN, YELLOW, BLUE por sector
    is_full_course_yellow: bool
    is_local_yellow: bool
    fcy_phase: str                  # PENDING, IN_PROGRESS, PITS_CLOSED, PITS_OPEN_LEAD_LAP, PITS_OPEN, LAST_LAP_NEXT, LAST_LAP_CURRENT, RACING
    distance_to_nearest_incident: float
    num_cars_passed_illegally: int
    can_overtake_car_in_front: str  # YES, NO, NO_DATA
    current_lap_is_fcy: bool
    previous_lap_was_fcy: bool
    lap_count_when_last_went_green: int
    use_improvised_incident_calling: bool

@dataclass
class TyreData:
    front_left_temp: float
    front_right_temp: float
    rear_left_temp: float
    rear_right_temp: float
    front_left_wear: float          # 0.0-1.0
    front_right_wear: float
    rear_left_wear: float
    rear_right_wear: float
    front_left_pressure: float      # kPa
    front_right_pressure: float
    rear_left_pressure: float
    rear_right_pressure: float
    front_left_compound: str        # SOFT, MEDIUM, HARD, WET, etc.
    front_right_compound: str
    rear_left_compound: str
    rear_right_compound: str
    front_left_flat: bool
    front_right_flat: bool
    rear_left_flat: bool
    rear_right_flat: bool
    front_left_brake_temp: float    # °C
    front_right_brake_temp: float
    rear_left_brake_temp: float
    rear_right_brake_temp: float
    front_left_brake_wear: float    # 0.0-1.0
    front_right_brake_wear: float
    rear_left_brake_wear: float
    rear_right_brake_wear: float

@dataclass
class CarDamageData:
    damage_enabled: bool
    aero_damage_level: str          # UNKNOWN, NONE, TRIVIAL, MINOR, MAJOR, DESTROYED
    engine_damage_level: str
    transmission_damage_level: str
    suspension_damage_fl: str
    suspension_damage_fr: str
    suspension_damage_rl: str
    suspension_damage_rr: str
    brake_damage_fl: str
    brake_damage_fr: str
    brake_damage_rl: str
    brake_damage_rr: str
    overall_aero_damage: str
    overall_engine_damage: str
    overall_transmission_damage: str
    last_impact_time: float

@dataclass
class EngineData:
    engine_rpm: float
    max_engine_rpm: float
    engine_water_temp: float        # °C
    engine_oil_temp: float          # °C
    engine_oil_pressure: float
    engine_water_temp_warning: bool
    engine_oil_pressure_warning: bool
    engine_fuel_pressure_warning: bool
    engine_stalled_warning: bool
    gear: int
    minutes_into_session_before_monitoring: int

@dataclass
class FuelData:
    fuel_left: float                # Litros
    fuel_capacity: float            # Litros
    fuel_pressure: float
    fuel_use_active: bool

@dataclass
class BatteryData:
    battery_percentage_left: float  # %
    battery_use_active: bool
    battery_capacity: float

@dataclass 
class OpponentData:
    """Datos de UN oponente."""
    driver_raw_name: str
    car_number: str
    vehicle_class: str
    class_position: int
    overall_position: int
    class_position_at_previous_tick: int
    overall_position_at_previous_tick: int
    speed: float                   # m/s
    distance_round_track: float    # Metros
    delta_time: DeltaTime          # Gap con diferencias de vuelta
    current_best_lap_time: float
    last_lap_time: float
    completed_laps: int
    current_sector: int
    in_pits: bool
    is_active: bool
    is_new_lap: bool
    is_entering_pits: bool
    is_exiting_pits: bool
    is_on_out_lap: bool
    current_tyres: str             # Compound
    has_just_changed_tyre_type: bool
    last_lap_valid: bool
    can_use_name: bool
    opponent_lap_data: List[float]  # Últimos N tiempos de vuelta
    position_on_approach_to_pit_entry: int = -1

@dataclass
class DeltaTime:
    """Sistema de delta con diferencias de vuelta."""
    time: float
    lap: int
    
    def get_signed_lap_difference(self, other: 'DeltaTime') -> int:
        """Diferencia de vueltas: positivo = detrás."""
        ...
    
    def get_signed_delta_time_only(self, other: 'DeltaTime') -> float:
        """Delta sin tener en cuenta vueltas."""
        ...
    
    def get_absolute_time_delta_allowing_for_lap_differences(self, other: 'DeltaTime') -> Tuple[int, float]:
        """(lap_difference, time_delta) considerando diferencias de vuelta."""
        ...

@dataclass
class TimingData:
    """Mejores tiempos filtrados por condiciones climáticas."""
    player_best_lap_time_by_conditions: Dict[str, float]
    player_best_sector1_time_by_conditions: Dict[str, float]
    player_best_sector2_time_by_conditions: Dict[str, float]
    player_best_sector3_time_by_conditions: Dict[str, float]
    player_class_best_lap_time_by_conditions: Dict[str, float]
    player_class_opponent_best_lap_time_by_conditions: Dict[str, float]
    
    def get_player_best_lap_time(self, conditions: str = "CURRENT") -> float: ...
    def get_player_class_best_lap_time(self, conditions: str = "CURRENT") -> float: ...
    def get_player_class_opponent_best_lap_time(self, conditions: str = "CURRENT") -> float: ...

@dataclass
class FrozenOrderData:
    """Datos de orden congelada para safety car/rolling start."""
    phase: str                     # None, FullCourseYellow, FormationStanding, Rolling, FastRolling
    action: str                    # None, Follow, CatchUp, AllowToPass, StayInPole, MoveToPole, PassSafetyCar
    assigned_position: int
    assigned_column: str           # None, Left, Right
    assigned_grid_position: int
    driver_to_follow_raw: str
    safety_car_speed: float        # m/s

@dataclass 
class ControlData:
    control_type: str              # Unavailable, Player, AI, Remote, Replay
    throttle_pedal: float
    brake_pedal: float

@dataclass
class GameStateData:
    """Objeto único de estado de juego — equivalente a GameStateData de CrewChief."""
    now: float                     # Timestamp
    session_data: SessionData
    position_and_motion_data: PositionAndMotionData
    pit_data: PitData
    flag_data: FlagData
    tyre_data: TyreData
    car_damage_data: CarDamageData
    engine_data: EngineData
    fuel_data: FuelData
    battery_data: BatteryData
    timing_data: TimingData
    frozen_order_data: FrozenOrderData
    control_data: ControlData
    conditions: 'ConditionsData'
    opponent_data: Dict[str, OpponentData]
    car_class: str
    multiclass: bool
    number_of_classes: int
    on_manual_formation_lap: bool
    in_car: bool
```

**Dependencias**: Fase 0 completa  
**Esfuerzo**: 5 días  
**Prioridad**: 🔴 6

---

### 1.2 TrackDefinition y TrackLengthClass

**Archivos a crear**: `backend/src/data/track_data.json`, `backend/src/services/track_data.py`

**Arquitectura CrewChief**: `TrackData.cs` con definición de pistas, `TrackLengthClass`, `trackLandmarksData.json`

**Implementación**:
```python
@dataclass
class TrackDefinition:
    name: str                       # Nombre de la pista
    track_length: float             # Longitud en metros
    track_length_class: str         # VERY_SHORT(<2km), SHORT(2-3.5km), MEDIUM(3.5-5.5km), LONG(5.5-8km), VERY_LONG(>8km)
    corners: List[Corner]           # Curvas con distancias
    landmarks: List[str]            # Puntos de referencia
    pit_box_position: float         # Posición en pista del box
    pit_exit_position: float        # Posición en pista de salida de pits
    distance_for_near_pit_entry_checks: float
    is_oval: bool
    number_of_sectors: int          # 2 o 3

# Uso en eventos:
# LapTimes.outlierPaceLimits[track.track_length_class]
# Laps before announcing gaps: lapsBeforeAnnouncingGaps[track.track_length_class]
# Fuel window length: fuelUseByLapsWindowLengthToUse[track.track_length_class]
```

**Dependencias**: 1.1 (GameStateData)  
**Esfuerzo**: 2 días  
**Prioridad**: 🟠 8

---

## FASE 2 — SPOTTER CARTESIANO

### 2.1 Implementar NoisyCartesianCoordinateSpotter

**Archivo a crear**: `backend/src/intelligence/noisy_cartesian_spotter.py`

**Algoritmo CrewChief** (1000+ líneas):

```python
class NoisyCartesianCoordinateSpotter:
    """
    Spotter basado en coordenadas cartesianas (NO time gaps).
    
    Toma la posición mundial (X, Z) del jugador y de cada rival,
    rota las coordenadas usando el yaw del jugador, y determina
    si algún rival está solapado lateralmente.
    """
    
    def __init__(self, audio_player=None):
        # Configuración (toda configurable por usuario)
        self.track_zone_to_consider = 20.0       # Metros alrededor
        self.min_speed_for_spotter = 10.0        # m/s (~36 km/h)
        self.max_closing_speed = 50.0            # m/s máximo cierre
        self.gap_needed_for_clear = 1.0          # Metros extra para "clear"
        self.car_length = 4.5                    # Metros
        self.car_width = 1.8                     # Metros
        self.car_behind_extra_length = 0.4       # Metros extra detrás
        self.max_overlaps_per_side = 3           # Máximo coches por lado
        
        # Delays (configurables)
        self.clear_message_delay = 0.500         # ms antes de decir "clear"
        self.overlap_message_delay = 0.100       # ms antes de decir "overlap"
        self.repeat_hold_frequency = 3.0         # s entre "still there"
        self.on_single_overlap_to_3_wide_delay = 0.5  # s
        
        # Expiración de mensajes
        self.clear_message_expires_after = 2000  # ms
        self.hold_message_expires_after = 1000   # ms
        self.in_the_middle_expires_after = 1000  # ms
        
        # Estado
        self.cars_on_left = 0
        self.cars_on_right = 0
        self.cars_on_left_previous = 0
        self.cars_on_right_previous = 0
        self.has_overlap = False
        self.previous_velocity_data = {}  # opponent_id -> PreviousPositionAndVelocity
        
        # Flags de reporting
        self.reported_single_overlap_left = False
        self.reported_single_overlap_right = False
        self.reported_double_overlap_left = False
        self.reported_double_overlap_right = False
        self.was_in_middle = False
        
        # Timers
        self.next_message_due = 0.0
        self.time_when_channel_should_be_closed = 0.0
        self.channel_left_open_timer_started = False
        self.next_message_type = None
        
        # Audio
        self.audio_player = audio_player
    
    def trigger(self, player_state: dict, opponents: List[dict], now: float):
        """
        Evalúa el spotter.
        
        Args:
            player_state: dict con rotation_yaw, world_x, world_z, speed
            opponents: lista de dicts con world_x, world_z, speed
            now: timestamp actual
        """
        player_x = player_state.get("world_x", 0)
        player_z = player_state.get("world_z", 0)
        player_yaw = player_state.get("rotation_yaw", 0)
        player_speed = player_state.get("speed_ms", 0)
        
        # 1. Filtro por velocidad mínima
        if player_x == 0 or player_z == 0 or player_speed < self.min_speed_for_spotter:
            # Cerrar canal si estaba abierto
            return
        
        # 2. Procesar cada oponente
        cars_on_left = 0
        cars_on_right = 0
        
        for opponent in opponents:
            opp_x = opponent.get("world_x", 0)
            opp_z = opponent.get("world_z", 0)
            opp_speed = opponent.get("speed")
            
            if opp_x == 0 or opp_z == 0:
                continue
            
            # 2a. Filtro por rango
            if abs(opp_x - player_x) > self.track_zone_to_consider or \
               abs(opp_z - player_z) > self.track_zone_to_consider:
                continue
            
            # 2b. Calcular velocidad del oponente (derivada de posición)
            is_speed_in_range = self._check_opponent_velocity(
                opponent.get("id"), opp_x, opp_z, nown
            )
            
            # 2c. Si ya tenemos max overlaps, no calcular más
            if cars_on_left >= self.max_overlaps_per_side and \
               cars_on_right >= self.max_overlaps_per_side:
                break
            
            # 2d. Rotar coordenadas y determinar lado
            side, lateral_sep = self._get_side_and_separation(
                player_yaw, player_x, player_z, opp_x, opp_z, is_speed_in_range
            )
            
            if side == "left":
                cars_on_left += 1
            elif side == "right":
                cars_on_right += 1
        
        # 3. Detección 3-wide: verificar que no sean line-astern
        # Si la separación lateral entre coches del mismo lado es < car_width,
        # están en fila india, no 3-wide.
        
        # 4. Determinar próximo mensaje
        self._get_next_message(cars_on_left, cars_on_right, now)
        
        # 5. Reproducir mensaje si toca
        self._play_next_message(cars_on_left, cars_on_right, now)
        
        # 6. Actualizar estado
        self.cars_on_left_previous = self.cars_on_left
        self.cars_on_right_previous = self.cars_on_right
        self.cars_on_left = cars_on_left
        self.cars_on_right = cars_on_right
        self.has_overlap = cars_on_left > 0 or cars_on_right > 0
    
    def get_aligned_xz_coordinates(
        self, player_yaw: float, player_x: float, player_z: float,
        opp_x: float, opp_z: float
    ) -> Tuple[float, float]:
        """
        Rota coordenadas del oponente usando el yaw del jugador.
        
        Returns:
            (aligned_x, aligned_z) donde:
            - aligned_x > 0: oponente a la derecha
            - aligned_x < 0: oponente a la izquierda
            - aligned_z > 0: oponente detrás
            - aligned_z < 0: oponente delante
        """
        # Vector del jugador al oponente
        dx = opp_x - player_x
        dz = opp_z - player_z
        
        # Matriz de rotación 2D con el yaw del jugador
        cos_yaw = math.cos(-player_yaw)
        sin_yaw = math.sin(-player_yaw)
        
        aligned_x = dx * cos_yaw - dz * sin_yaw
        aligned_z = dx * sin_yaw + dz * cos_yaw
        
        return (aligned_x, aligned_z)
    
    def _check_opponent_velocity(self, opp_id: int, x: float, z: float, now: float) -> bool:
        """Calcula velocidad del oponente por derivada de posición cada 0.2s."""
        prev = self.previous_velocity_data.get(opp_id)
        if prev is None:
            self.previous_velocity_data[opp_id] = {
                "x": x, "z": z, "time": now
            }
            return True
        
        time_diff = now - prev["time"]
        if time_diff >= 0.2:
            x_speed = (x - prev["x"]) / time_diff
            z_speed = (z - prev["z"]) / time_diff
            self.previous_velocity_data[opp_id] = {
                "x": x, "z": z, "time": now,
                "x_speed": x_speed, "z_speed": z_speed
            }
        
        # Velocidad de cierre
        opponent_speed = math.sqrt(
            prev.get("x_speed", 0)**2 + prev.get("z_speed", 0)**2
        )
        return opponent_speed < self.max_closing_speed
    
    def _get_side_and_separation(self, player_yaw, px, pz, ox, oz, 
                                 is_opponent_speed_in_range):
        """Determina si el oponente está a la izquierda/derecha y su separación."""
        aligned_x, aligned_z = self.get_aligned_xz_coordinates(
            player_yaw, px, pz, ox, oz
        )
        
        if abs(aligned_x) >= self.track_zone_to_consider:
            return (None, -1)
        
        if aligned_x < 0:  # Izquierda
            if self.cars_on_right_previous > 0:
                if abs(aligned_z) < self.car_length + self.gap_needed_for_clear:
                    return ("left", abs(aligned_x))
            elif ((aligned_z < 0 and -aligned_z < self.car_length) or
                  (aligned_z > 0 and aligned_z < self.car_length + self.car_behind_extra_length)) and \
                  abs(aligned_x) > self.car_width and is_opponent_speed_in_range:
                return ("left", abs(aligned_x))
        else:  # Derecha
            if self.cars_on_left_previous > 0:
                if abs(aligned_z) < self.car_length + self.gap_needed_for_clear:
                    return ("right", abs(aligned_x))
            elif ((aligned_z < 0 and -aligned_z < self.car_length) or
                  (aligned_z > 0 and aligned_z < self.car_length + self.car_behind_extra_length)) and \
                  abs(aligned_x) > self.car_width and is_opponent_speed_in_range:
                return ("right", abs(aligned_x))
        
        return (None, -1)
    
    def _get_next_message(self, left_count, right_count, now):
        """Determina qué mensaje toca reproducir."""
        if left_count == 0 and right_count == 0 and \
           self.cars_on_left_previous > 0 and self.cars_on_right_previous > 0:
            self.next_message_type = "clear_all_round"
            self.next_message_due = now + self.clear_message_delay
        elif left_count == 0 and self.cars_on_left_previous > 0:
            self.next_message_type = "clear_left"
            self.next_message_due = now + self.clear_message_delay
        elif right_count == 0 and self.cars_on_right_previous > 0:
            self.next_message_type = "clear_right"
            self.next_message_due = now + self.clear_message_delay
        elif left_count > 0 and right_count > 0 and \
             (self.cars_on_left_previous == 0 or self.cars_on_right_previous == 0):
            self.next_message_type = "three_wide"
            self.next_message_due = now
        elif left_count > 0 and right_count == 0 and \
             self.cars_on_left_previous == 0 and self.cars_on_right_previous == 0:
            self.next_message_type = "three_wide_on_right" if left_count > 1 else "car_left"
            self.next_message_due = now
        elif left_count == 0 and right_count > 0 and \
             self.cars_on_left_previous == 0 and self.cars_on_right_previous == 0:
            self.next_message_type = "three_wide_on_left" if right_count > 1 else "car_right"
            self.next_message_due = now
    
    def _play_next_message(self, left_count, right_count, now):
        """Reproduce el mensaje determinado."""
        if self.next_message_type is None or now < self.next_message_due:
            return
        
        if not self._message_is_valid(self.next_message_type, left_count, right_count):
            return
        
        # Mapear tipo de mensaje a ruta de audio
        message_map = {
            "car_left": "spotter/car_left",
            "car_right": "spotter/car_right",
            "clear_left": "spotter/clear_left",
            "clear_right": "spotter/clear_right",
            "clear_all_round": "spotter/clear_all_round",
            "three_wide": "spotter/in_the_middle",
            "still_there": "spotter/still_there",
            "three_wide_on_left": "spotter/three_wide_on_left",
            "three_wide_on_right": "spotter/three_wide_on_right",
        }
        
        audio_path = message_map.get(self.next_message_type)
        if audio_path and self.audio_player:
            self.audio_player.play_spotter_message(audio_path, keep_channel_open=True)
        
        # Actualizar estado para próximo mensaje
        if self.next_message_type in ("car_left", "car_right", "three_wide"):
            self.next_message_type = "still_there"
            self.next_message_due = now + self.repeat_hold_frequency
```

**Mensajes del spotter** (audios pre-grabados necesarios):
- `spotter/car_left` — "Car left"
- `spotter/car_right` — "Car right"
- `spotter/still_there` — "Still there" (repeat)
- `spotter/clear_left` — "Clear left"
- `spotter/clear_right` — "Clear right"
- `spotter/clear_all_round` — "Clear all round"
- `spotter/in_the_middle` — "In the middle" (3-wide)
- `spotter/three_wide_on_right` — "3 wide, you're on the right"
- `spotter/three_wide_on_left` — "3 wide, you're on the left"
- `spotter/three_wide_on_inside` — "3 wide, you're on the inside" (óvalo)
- `spotter/three_wide_on_outside` — "3 wide, you're on the outside" (óvalo)

**Dependencias**: 0.1 (Yaw), 0.5 (PreviousTick), 1.1 (GameStateData)  
**Esfuerzo**: 5 días  
**Prioridad**: 🔴 7

---

## FASE 3 — SISTEMA DE EVENTOS

### 3.1 Arquitectura base de eventos

**Archivo a crear**: `backend/src/intelligence/base_event.py`

```python
class AbstractEvent(ABC):
    """Clase base para todos los eventos de CrewChief."""
    
    # Filtros automáticos
    applicable_session_types: List[str] = ["Practice", "Qualify", "Race"]
    applicable_session_phases: List[str] = ["Green", "Countdown"]
    applicable_racing_types: List[str] = ["Circuit"]
    
    def __init__(self, audio_player=None):
        self.audio_player = audio_player
    
    @abstractmethod
    def trigger_internal(self, previous: GameStateData, current: GameStateData):
        """Lógica principal del evento. Llamada en cada tick."""
        pass
    
    @abstractmethod
    def clear_state(self):
        """Reinicia estado del evento entre sesiones."""
        pass
    
    def is_applicable(self, session_type: str, session_phase: str) -> bool:
        """Filtro automático por tipo y fase de sesión."""
        return (session_type in self.applicable_session_types and 
                session_phase in self.applicable_session_phases)
    
    def is_message_still_valid(self, event_subtype: str, 
                                current: GameStateData,
                                validation_data: dict) -> bool:
        """
        Validación de mensaje en 2 momentos:
        1) Cuando vence
        2) Justo antes de reproducirse
        """
        return current is not None and self.is_applicable(
            current.session_data.session_type,
            current.session_data.session_phase
        )
    
    def respond(self, voice_message: str):
        """Responde a un comando de voz."""
        pass
    
    # Sistema de fragmentos de mensaje
    @staticmethod
    def message_contents(*objects) -> List[dict]:
        """
        Construye mensaje compuesto a partir de objetos tipados.
        
        Tipos soportados:
        - str → referencia a archivo de audio
        - int → número leído con NumberReader
        - TimeSpanWrapper → tiempo con precisión adaptativa
        - OpponentData → nombre/número automático
        - Pause(int) → silencio en ms
        """
        fragments = []
        for obj in objects:
            if obj is None:
                fragments.append(None)
            elif isinstance(obj, dict) and obj.get("type") == "pause":
                fragments.append(obj)
            elif isinstance(obj, str):
                fragments.append({"type": "text", "text": obj})
            elif isinstance(obj, int):
                fragments.append({"type": "integer", "value": obj})
            elif isinstance(obj, TimeSpanWrapper):
                fragments.append({"type": "time", "value": obj})
            elif isinstance(obj, OpponentData):
                fragments.append({"type": "opponent", "data": obj})
        return fragments
    
    @staticmethod
    def Pause(ms: int) -> dict:
        """Pausa de silencio en milisegundos."""
        return {"type": "pause", "duration_ms": ms}
    
    def convert_temp(self, temp_celsius: float, precision: int = 1) -> int:
        """Convierte temperatura según configuración del usuario."""
        if self._use_fahrenheit:
            return int(round((temp_celsius * 9/5) + 32))
        return int(round(temp_celsius / precision) * precision)
    
    def convert_pressure(self, pressure_kpa: float) -> float:
        """Convierte presión según configuración."""
        if self._use_psi:
            return round(pressure_kpa / 6.894, 1)
        return round(pressure_kpa / 100, 2)
```

### 3.2 Registro y ciclo de eventos

**Archivo a modificar**: `backend/src/intelligence/engine.py`

```python
class EventEngine:
    """Motor de eventos — equivalente al loop de CrewChief.cs."""
    
    def __init__(self):
        self.events: Dict[str, AbstractEvent] = {}
        self.faulting_events: Dict[str, int] = {}  # Contador de fallos
        self.max_failures_before_disable = 10
    
    def register_event(self, name: str, event: AbstractEvent):
        self.events[name] = event
    
    def clear_all_state(self):
        for event in self.events.values():
            event.clear_state()
    
    def tick(self, previous: GameStateData, current: GameStateData):
        """Llama a todos los eventos aplicables."""
        for name, event in self.events.items():
            if not event.is_applicable(
                current.session_data.session_type,
                current.session_data.session_phase
            ):
                continue
            
            # Verificar si el evento está deshabilitado por fallos
            failures = self.faulting_events.get(name, 0)
            if failures >= self.max_failures_before_disable:
                continue
            
            try:
                event.trigger_internal(previous, current)
            except Exception as e:
                failures = self.faulting_events.get(name, 0) + 1
                self.faulting_events[name] = failures
                logger.error(f"Event {name} failed ({failures}/{self.max_failures_before_disable}): {e}")
```

**Registro de eventos** (todos los que CrewChief tiene):
```python
# En main.py o config de eventos:
engine.register_event("Position", PositionEvent(audio_player))
engine.register_event("PitStops", PitStopsEvent(audio_player))
engine.register_event("Fuel", FuelEvent(audio_player))
engine.register_event("TyreMonitor", TyreMonitorEvent(audio_player))
engine.register_event("FlagsMonitor", FlagsMonitorEvent(audio_player))
engine.register_event("DamageReporting", DamageReportingEvent(audio_player))
engine.register_event("EngineMonitor", EngineMonitorEvent(audio_player))
engine.register_event("Opponents", OpponentsEvent(audio_player))
engine.register_event("LapTimes", LapTimesEvent(audio_player))
engine.register_event("LapCounter", LapCounterEvent(audio_player))
engine.register_event("PushNow", PushNowEvent(audio_player))
engine.register_event("Strategy", StrategyEvent(audio_player))
engine.register_event("MulticlassWarnings", MulticlassWarningsEvent(audio_player))
engine.register_event("WatchedOpponents", WatchedOpponentsEvent(audio_player))
engine.register_event("SessionEndMessages", SessionEndMessagesEvent(audio_player))
engine.register_event("Battery", BatteryEvent(audio_player))
engine.register_event("Penalties", PenaltiesEvent(audio_player))
engine.register_event("ConditionsMonitor", ConditionsMonitorEvent(audio_player))
engine.register_event("FrozenOrderMonitor", FrozenOrderMonitorEvent(audio_player))
engine.register_event("OvertakingAidsMonitor", OvertakingAidsMonitorEvent(audio_player))
engine.register_event("RaceTime", RaceTimeEvent(audio_player))
```

**Dependencias**: 1.1 (GameStateData)  
**Esfuerzo**: 2 días (base) + por evento  
**Prioridad**: 🔴 (base), 🟠 (eventos individuales)

---

## FASE 4 — SISTEMA DE AUDIO Y MENSAJES

### 4.1 Sistema de cola dual

**Archivo a crear**: `backend/src/services/audio_player.py`

```python
class AudioPlayer:
    """
    Sistema de reproducción de audio con cola dual.
    
    - queued_clips (OrderedDict): Mensajes normales
    - immediate_clips (OrderedDict): Mensajes urgentes
    - Prioridad: spotter (20) > critical (15) > important (10) > normal (0-5)
    """
    
    # SoundType enum
    CRITICAL = 15
    IMPORTANT = 10
    NORMAL = 5
    SPOTTER = 20
    VOICE_COMMAND = 8
    NONE = 0
    
    def __init__(self):
        self.queued_clips = OrderedDict()
        self.immediate_clips = OrderedDict()
        self.last_message_played = None
        self.channel_open = False
        self.hold_channel_open = False
        self.disable_pearls = False
        self.monitor_running = False
        
        # Configuración
        self.enable_radio_beeps = True
        self.use_alternate_beeps = False
        self.pause_between_messages = 0.5  # segundos
        
        # Thread de monitor
        self.monitor_thread = None
    
    def play_message(self, message: 'QueuedMessage', 
                     pearl_type: str = "NONE",
                     pearl_probability: float = 0.0):
        """Añade mensaje a la cola normal."""
        # 1. Verificar cooldown/duplicados
        if message.message_name in self.queued_clips:
            logger.debug(f"Clip {message.message_name} ya en cola, ignorando")
            return
        
        # 2. Verificar PlaybackModerator
        if not PlaybackModerator.message_can_be_queued(message, len(self.queued_clips)):
            return
        
        # 3. Añadir Pearl of Wisdom si aplica
        if pearl_type != "NONE" and self._can_add_pearl(pearl_type):
            pearl_msg = self._create_pearl_message(pearl_type)
            self._insert_by_priority(pearl_msg)
        
        # 4. Insertar por prioridad
        self._insert_by_priority(message)
    
    def play_message_immediately(self, message: 'QueuedMessage',
                                  keep_channel_open: bool = False):
        """Añade mensaje a la cola inmediata (interrumpe lo que suene)."""
        if message.message_name in self.immediate_clips:
            return
        
        if not PlaybackModerator.immediate_message_can_be_queued(message):
            return
        
        self.hold_channel_open = keep_channel_open
        self._insert_by_priority(self.immediate_clips, message)
        self._wake_monitor()
    
    def play_spotter_message(self, message: 'QueuedMessage',
                              keep_channel_open: bool = True):
        """Spotter siempre a prioridad 20, interrumpe todo."""
        message.priority = AudioPlayer.SPOTTER
        self.hold_channel_open = keep_channel_open
        self._insert_by_priority(self.immediate_clips, message)
        
        # Interrumpir sonido actual
        SoundCache.interrupt_currently_playing(allow_beep_interrupt=False)
        self._wake_monitor()
    
    def purge_queues(self, retain_session_end: bool = True):
        """Limpia todas las colas."""
        purged = 0
        for queue in [self.queued_clips, self.immediate_clips]:
            keys_to_purge = list(queue.keys())
            for key in keys_to_purge:
                if retain_session_end and "RETAIN_ON_SESSION_END" in key:
                    continue
                queue.pop(key, None)
                purged += 1
        return purged
    
    def _insert_by_priority(self, queue: OrderedDict, message: 'QueuedMessage'):
        """Inserta mensaje en orden de prioridad (mayor = primero)."""
        insert_idx = 0
        for key, existing in queue.items():
            if message.priority > existing.priority:
                break
            insert_idx += 1
        queue.insert(insert_idx, message.message_name, message)
    
    def _monitor_loop(self):
        """Thread que reproduce mensajes de las colas."""
        while self.monitor_running:
            now = time.time()
            
            # 1. Procesar mensajes inmediatos (primero)
            message = self._get_next_immediate()
            if message:
                self._play_message(message)
                continue
            
            # 2. Procesar cola normal
            if not self.regular_queue_paused:
                message = self._get_next_queued()
                if message:
                    self._play_message(message)
                    continue
            
            # 3. Esperar wakeup o timeout
            self._wait_for_wakeup(timeout=0.5)
    
    def _play_message(self, message: 'QueuedMessage'):
        """Reproduce un mensaje individual."""
        # 1. Beep de inicio si aplica
        if self.enable_radio_beeps and message.priority >= AudioPlayer.IMPORTANT:
            self._play_start_beep()
        
        # 2. Procesar fragmentos → audio
        for fragment in message.message_fragments:
            if fragment is None:
                continue
            if fragment.get("type") == "pause":
                time.sleep(fragment["duration_ms"] / 1000)
            elif fragment.get("type") == "text":
                SoundCache.play(fragment["text"])
            elif fragment.get("type") == "integer":
                NumberReader.read_integer(fragment["value"])
            # etc.
        
        # 3. Beep de fin
        if self.enable_radio_beeps:
            self._play_end_beep()
        
        # 4. Pausa entre mensajes
        time.sleep(self.pause_between_messages)


class QueuedMessage:
    """Mensaje encolable para reproducción."""
    
    def __init__(self, message_name: str, expiry_time: float,
                 message_fragments: List[dict] = None,
                 alternate_message_fragments: List[dict] = None,
                 seconds_delay: float = 0,
                 abstract_event: AbstractEvent = None,
                 priority: int = 5,
                 validation_data: dict = None,
                 delayed_message_event: dict = None,
                 metadata: dict = None):
        
        self.message_name = message_name
        self.expiry_time = expiry_time          # Segundos hasta expirar
        self.seconds_delay = seconds_delay      # Delay antes de encolar
        self.message_fragments = message_fragments or []
        self.alternate_message_fragments = alternate_message_fragments
        self.abstract_event = abstract_event     # Para isMessageStillValid
        self.priority = priority
        self.validation_data = validation_data   # Para validación
        self.delayed_message_event = delayed_message_event  # Evalúa al reproducir
        self.metadata = metadata or {}
        self.can_be_played = True
        self.creation_time = time.time()
        self.due_time = self.creation_time + seconds_delay
        self.is_rant = False
```

### 4.2 SoundCache

**Archivo a crear**: `backend/src/services/sound_cache.py`

```python
class SoundCache:
    """
    Caché de sonidos pre-grabados.
    
    CrewChief NO usa TTS para mensajes comunes. Todo son archivos .wav
    organizados en carpetas. Solo usa TTS para nombres y números.
    """
    
    available_sounds: Set[str] = set()  # "spotter/car_left", "opponents/the_leader", etc.
    available_driver_names: Set[str] = set()
    has_suitable_tts_voice: bool = False
    is_playing: bool = False
    cancel_lazy_loading: bool = False
    
    def __init__(self, sound_path: str):
        self.sound_path = Path(sound_path)
        self._cache: Dict[str, bytes] = {}  # folder → audio_data
        self._load_available_sounds()
    
    @classmethod
    def play(cls, folder: str, metadata: dict = None):
        """Reproduce un sonido de la caché."""
        pass
    
    @classmethod
    def interrupt_currently_playing(cls, allow_beep_interrupt: bool = False):
        """Interrumpe el sonido actual."""
        pass
    
    @classmethod
    def load_driver_name_sounds(cls, names: List[str]):
        """Carga sonidos de nombres de pilotos."""
        pass
    
    @classmethod
    def expire_cached_sounds(cls):
        """Limpia sonidos de la caché."""
        pass
```

### 4.3 NumberReader

**Archivo a crear**: `backend/src/services/number_reader.py`

```python
class NumberReader:
    """
    Sistema de lectura de números en múltiples idiomas.
    
    NO usa TTS para números — usa audios pre-grabados dígito por dígito.
    """
    
    # Idiomas soportados
    LANGUAGES = ["en", "es", "it", "pt-br"]
    
    @staticmethod
    def read_integer(value: int, language: str = "en") -> List[str]:
        """
        Convierte un entero a lista de rutas de audio.
        
        123 → ["numbers/one", "numbers/hundred_and", "numbers/twenty", "numbers/three"]
        5 → ["numbers/five"]
        """
        pass
    
    @staticmethod
    def read_time(seconds: float, precision: str = "AUTO") -> List[str]:
        """
        Lee un tiempo con precisión adaptativa.
        
        Precision.AUTO_LAPTIMES: "one minute thirty four point two"
        Precision.AUTO_GAPS: "one point five"
        Precision.SECONDS: "thirty four seconds"
        Precision.TENTHS: "one point two"
        """
        pass
```

### 4.4 PlaybackModerator

**Archivo a crear**: `backend/src/services/playback_moderator.py`

```python
class PlaybackModerator:
    """
    Decide qué mensajes pueden encolarse según reglas de negocio.
    """
    
    last_blocked_message_id: int = -1
    enabled_message_types: Set[str] = set()  # Filtro por clase de coche
    
    @staticmethod
    def message_can_be_queued(message: QueuedMessage, queue_length: int, 
                               current_time: float) -> bool:
        """Verifica si el mensaje puede entrar en la cola normal."""
        # Reglas:
        # 1. Máximo de mensajes en cola según frecuencia
        # 2. Cooldown por tipo de mensaje
        # 3. Desactivado por clase de coche
        return True
    
    @staticmethod
    def immediate_message_can_be_queued(message: QueuedMessage) -> bool:
        """Verifica si el mensaje puede entrar en la cola inmediata."""
        return True
```

**Dependencias**: 1.1 (GameStateData), 2.1 (Spotter)  
**Esfuerzo**: 5 días (AudioPlayer) + 3 días (SoundCache) + 2 días (NumberReader) + 1 día (PlaybackModerator)  
**Prioridad**: 🟠

---

## FASE 5 — EVENTOS INDIVIDUALES

### 5.1 Position (Overtakes, Race Start)

**Archivo**: `backend/src/intelligence/events/position.py`
**CrewChief referencia**: `Events/Position.cs` (1000+ líneas)

```python
class PositionEvent(AbstractEvent):
    """
    Detecta overtakes, being overtaken, race start quality, position reminders.
    
    Funciona comparando el oponente delante/atrás entre ticks (PreviousTick).
    """
    
    def __init__(self, audio_player):
        super().__init__(audio_player)
        self.folder_stub = "position/"
        self._last_opponent_ahead = None
        self._last_opponent_behind = None
        self._race_start_position = None
        self._last_position_reminder_time = 0
        
        # Cooldowns
        self.min_seconds_between_overtake_messages = 10
        self.position_reminder_interval_min = 180  # 3 vueltas
        self.position_reminder_interval_max = 360  # 6 vueltas
        
        # Mensajes
        self.folder_overtake = "position/overtake"
        self.folder_being_overtaken = "position/being_overtaken"
        self.folder_terrible_start = "position/terrible_start"  # lost > 5
        self.folder_bad_start = "position/bad_start"  # lost > 3
        self.folder_good_start = "position/good_start"  # gained > 1
        self.folder_ok_start = "position/ok_start"
        self.folder_you_are_in_position = "position/you_are_in_position"
        self.folder_leading = "position/leading"
        self.folder_last = "position/last"
        self.folder_pole = "position/pole"
        self.folder_stub = "position/"
        self.folder_ahead = "position/ahead"
        self.folder_behind = "position/behind"
        self.folder_laps_ahead = "position/laps_ahead"
        self.folder_laps_behind = "position/laps_behind"
    
    def trigger_internal(self, previous: GameStateData, current: GameStateData):
        if previous is None or current.session_data.session_type != "Race":
            return
        
        # 1. Detectar overtake completado
        prev_ahead = previous.get_opponent_key_in_front(current.car_class)
        curr_ahead = current.get_opponent_key_in_front(current.car_class)
        
        if prev_ahead and curr_ahead and prev_ahead != curr_ahead:
            # Posible overtake — validar
            self._check_overtake(current, prev_ahead, curr_ahead)
        
        # 2. Detectar race start (primeras vueltas)
        if current.session_data.completed_laps == 0 and \
           current.session_data.session_phase == "Green" and \
           previous.session_data.session_phase != "Green":
            self._check_race_start(previous, current)
        
        # 3. Position reminders (cada 3-6 vueltas aleatorio)
        if current.session_data.is_new_lap and \
           current.session_data.completed_laps > 0 and \
           time.time() - self._last_position_reminder_time > \
           random.randint(self.position_reminder_interval_min, 
                         self.position_reminder_interval_max):
            self._play_position_reminder(current)
    
    def _check_overtake(self, current, prev_ahead_key, curr_ahead_key):
        """Valida si hubo un overtake limpio."""
        # Criterios CrewChief:
        # - Misma vuelta
        # - No en pits
        # - No bajo yellow
        # - Gap promedio < threshold
        # - Sin daño/off-track reciente
        
        if current.pit_data.in_pitlane:
            return
        if current.flag_data.is_full_course_yellow:
            return
        
        # Anunciar
        msg = QueuedMessage(
            "overtake", 10,
            message_fragments=AbstractEvent.message_contents(
                self.folder_overtake
            ),
            abstract_event=self,
            priority=7
        )
        self.audio_player.play_message(msg)
    
    def _check_race_start(self, previous, current):
        """Evalúa calidad de salida."""
        if self._race_start_position is None:
            self._race_start_position = current.session_data.class_position
        
        pos_change = self._race_start_position - current.session_data.class_position
        
        if pos_change <= -5:
            msg = QueuedMessage("terrible_start", 7, 
                message_fragments=AbstractEvent.message_contents(
                    self.folder_terrible_start), priority=10)
        elif pos_change <= -3:
            msg = QueuedMessage("bad_start", 7,
                message_fragments=AbstractEvent.message_contents(
                    self.folder_bad_start), priority=10)
        elif pos_change >= 1:
            msg = QueuedMessage("good_start", 7,
                message_fragments=AbstractEvent.message_contents(
                    self.folder_good_start), priority=10)
        else:
            return
        
        self.audio_player.play_message(msg, 
            pearl_type="NEUTRAL", pearl_probability=0.5)
    
    def clear_state(self):
        self._last_opponent_ahead = None
        self._last_opponent_behind = None
        self._race_start_position = None
        self._last_position_reminder_time = 0
```

### 5.2 PitStops

**Archivo**: `backend/src/intelligence/events/pit_stops.py`
**CrewChief referencia**: `Events/PitStops.cs` (1500+ líneas)

**Funcionalidades**:
1. Pit countdown posicional: "Box in 5, 4, 3, 2, 1, BOX!"
2. Pit countdown temporal: "Wait... wait... wait... go!"
3. Ventana de pits obligatoria (apertura/cierre)
4. Pit limiter engage/disengage
5. Velocidad de pit lane: "Watch your pit speed, 80 km/h"
6. Pit stall occupied/available
7. R3E/LMU pit menu integration (REST API :6397)
8. Mandatory stop con mínimo de duración
9. Pit exit warnings
10. Benchmark de paradas (persistido en JSON)
11. Estimación de posición post-parada

### 5.3 Fuel

**Archivo**: `backend/src/intelligence/events/fuel.py`
**CrewChief referencia**: `Events/Fuel.cs` (900+ líneas)

**Funcionalidades**:
1. Ventana deslizante por track length class (1-5 vueltas)
2. Máximo consumo por vuelta y por minuto
3. FCY awareness (usa max consumption si SC)
4. Ventana de pits óptima
5. Mensajes: "2 minutes of fuel", "fuel tight", "pit now"
6. Refuel detection
7. Low fuel run detection (prac/qual)

### 5.4 TyreMonitor

**Archivo**: `backend/src/intelligence/events/tyre_monitor.py`
**CrewChief referencia**: `Events/TyreMonitor.cs` (2500+ líneas)

**Funcionalidades**:
1. Clasificación temp: COLD/WARM/HOT/COOKING por compound
2. Clasificación wear: NEW/SCRUBBED/MINOR/MAJOR/WORN_OUT
3. Presión con tendencias (sampleo 1000ms)
4. Flat spot detection por diferencia de presión (threshold ~5psi)
5. Locking/Spinning acumulado por vuelta (por rueda y grupo)
6. Camber analysis (temp interno vs externo)
7. Compound detection (identifica tipo de neumático)

### 5.5 FlagsMonitor

**Archivo**: `backend/src/intelligence/events/flags_monitor.py`
**CrewChief referencia**: `Events/FlagsMonitor.cs` (1600+ líneas)

**Funcionalidades**:
1. FCY 7 fases: PENDING → IN_PROGRESS → PITS_CLOSED → PITS_OPEN_LEAD_LAP → PITS_OPEN → LAST_LAP → RACING
2. Incident detection: compara distance_round_track entre ticks
3. Pileup detection: >= 4 coches en misma zona
4. Blue flag: max 3 repeticiones por conductor
5. Overtake bajo yellow: detecta adelantamientos ilegales
6. Sector flags individuales

### 5.6 DamageReporting

**Archivo**: `backend/src/intelligence/events/damage_reporting.py`
**CrewChief referencia**: `Events/DamageReporting.cs` (1087+ líneas)

**Funcionalidades**:
1. Daños por componente: ENGINE, TRANNY, AERO, SUSPENSION, BRAKES
2. Niveles: NONE, TRIVIAL, MINOR, MAJOR, DESTROYED
3. Puncture detection por rueda
4. Crash detection: >40G (270G ACC), con wait 3s speed check
5. Rollover detection: orientation sampling 30 muestras/3s
6. "Are you OK?" system: pregunta tras crash, retry 3 veces
7. Missing wheel detection
8. Validación: si componente X está DESTROYED, no reportar daños menores

### 5.7 EngineMonitor

**Archivo**: `backend/src/intelligence/events/engine_monitor.py`
**CrewChief referencia**: `Events/EngineMonitor.cs` (250+ líneas)

**Funcionalidades**:
1. Temperatura agua/aceite: promedio 60s
2. Stall warning: inmediato, no en eléctricos
3. Presión aceite/combustible: check cada 2 minutos
4. Voice commands: "what's my oil temp", "what's my water temp"

### 5.8 Opponents

**Archivo**: `backend/src/intelligence/events/opponents.py`
**CrewChief referencia**: `Events/Opponents.cs` (1200+ líneas)

**Funcionalidades**:
1. Leader change detection
2. New car ahead/behind detection (con validación)
3. Retirement/DQ announcements
4. Opponent tyre change announcements
5. Opponent fast lap announcements
6. Voice commands (10+)

### 5.9 LapTimes

**Archivo**: `backend/src/intelligence/events/lap_times.py`
**CrewChief referencia**: `Events/LapTimes.cs` (900+ líneas)

**Funcionalidades**:
1. Sector delta categorization: FAST/A_TENTH/TWO_TENTHS/A_SECOND/AUTO_GAPS
2. Self-pace vs opponent pace comparison
3. Consistency analysis (ventana 5 vueltas)
4. Outlier detection por track length class
5. Qualifying pace messages
6. Race pace messages

### 5.10 LapCounter

**Archivo**: `backend/src/intelligence/events/lap_counter.py`
**CrewChief referencia**: `Events/LapCounter.cs` (55KB)

**Funcionalidades**:
1. Pre-lights messages (posición, temp pista, ventana pits)
2. Green flag message
3. Last lap announcements (leading/top 3/general)
4. Two laps remaining announcements
5. Manual formation lap mode (doble fila, grid side, leader has gone)
6. Purge queue at green flag

### 5.11 PushNow

**Archivo**: `backend/src/intelligence/events/push_now.py`
**CrewChief referencia**: `Events/PushNow.cs` (400+ líneas)

**Funcionalidades**:
1. Push to improve/hold position (calcula si alcanzas al de delante)
2. Pit exit warnings (traffic behind exiting pits)
3. Qualify exit messages ("we have X minutes/laps")
4. Opponent leaving pits warning

### 5.12 Strategy

**Archivo**: `backend/src/intelligence/events/strategy.py`
**CrewChief referencia**: `Events/Strategy.cs` (1500+ líneas)

**Funcionalidades**:
1. Post-pit position prediction (with traffic estimation)
2. Pit stop benchmarking (persistido)
3. Opponent pit exit estimation
4. Pit stall blocking detection (RF1)
5. R3E/LMU pit menu actions announcement

### 5.13 MulticlassWarnings

**Archivo**: `backend/src/intelligence/events/multiclass_warnings.py`
**CrewChief referencia**: `Events/MulticlassWarnings.cs` (56KB)

**Funcionalidades**:
1. Faster class cars behind detection
2. Slower class cars ahead detection
3. "Faster cars fighting behind" / "Slower cars ahead"
4. Class identification (LMP1, LMP2, GT3, GTE, etc.)
5. Zone adjustments by track length class
6. First-time session warnings ("you are being caught by the faster cars")

### 5.14 WatchedOpponents

**Archivo**: `backend/src/intelligence/events/watched_opponents.py`
**CrewChief referencia**: `Events/WatchedOpponents.cs` (300+ líneas)

**Funcionalidades**:
1. Watch opponent: "watch Verstappen"
2. Team mate / rival designation
3. Laptime reporting for watched opponents
4. Pit exit reporting for watched opponents
5. Position change reporting for watched opponents
6. Voice commands: "watch", "stop watching", "team mate", "rival"

### 5.15 SessionEndMessages

**Archivo**: `backend/src/intelligence/events/session_end.py`
**CrewChief referencia**: `Events/SessionEndMessages.cs` (150+ líneas)

**Funcionalidades**:
1. Win: "won race"
2. Podium: "podium finish"
3. General: "finished race PX"
4. Last: "finished race last"
5. DNF/DSQ: specific messages
6. Qualify: "pole" / "end of session PX"
7. Rant system on bad finish

**Dependencias**: 3.1 (EventEngine), 4.1 (AudioPlayer)  
**Esfuerzo**: ~2-3 días por evento  
**Prioridad**: Por determinar según necesidad

---

## FASE 6 — SISTEMA DE CONTROL DE VOZ

### 6.1 SpeechRecogniser

**Archivo a crear**: `backend/src/services/speech_recogniser.py`

```python
class SpeechRecogniser:
    """
    Sistema de reconocimiento de voz para comandos.
    
    CrewChief: 70+ comandos de voz vía Windows SRE.
    Nosotros: Opción 1 = Whisper local, Opción 2 = cloud API.
    """
    
    # Comandos de CrewChief
    COMMANDS = {
        "what_tyres_am_i_on": ["what tyres am i on", "tyres"],
        "whats_my_position": ["whats my position", "position"],
        "whats_behind_me": ["whos behind me", "whos behind"],
        "whats_in_front_of_me": ["whos in front", "whos in front of me"],
        "whats_the_gap": ["whats the gap", "gap"],
        "pit_now": ["box now", "pit now", "box this lap"],
        "cancel_pit": ["cancel pit", "cancel"],
        "whats_my_fuel": ["how much fuel", "fuel", "whats my fuel"],
        "whats_tyre_wear": ["tyre wear", "whats tyre wear"],
        "whats_my_lap_time": ["lap time", "whats my lap time"],
        "whats_the_best_lap": ["best lap", "whats the best lap"],
        "who_leading": ["whos leading", "who is leading", "leader"],
        "whos_in_front_on_track": ["whos in front on track"],
        "whos_behind_on_track": ["whos behind on track"],
        "where_is": ["where is", "wheres"],  # + driver name
        "whos_in": ["whos in"],  # + position/car
        "enable_spotter": ["enable spotter"],
        "disable_spotter": ["disable spotter"],
        "repeat_last": ["repeat", "repeat last"],
        "keep_quiet": ["keep quiet"],
        "status": ["status", "car status", "damage report"],
        "enable_deltas": ["enable deltas"],
        "disable_deltas": ["disable deltas"],
    }
    
    def __init__(self):
        self.waiting_for_speech = False
        self.got_recognition_result = False
        self.recognised_text = ""
    
    def process_command(self, text: str) -> str:
        """Procesa texto reconocido y devuelve comando."""
        text_lower = text.lower().strip()
        
        for command, phrases in self.COMMANDS.items():
            for phrase in phrases:
                if phrase in text_lower:
                    return command
        return "unknown"
    
    def extract_driver_name(self, text: str) -> Optional[str]:
        """Extrae nombre de piloto del texto."""
        for name in self._available_driver_names:
            if name.lower() in text.lower():
                return name
        return None
```

**Dependencias**: TTS/STT pipeline existente  
**Esfuerzo**: 3 días  
**Prioridad**: 🟢

---

## FASE 7 — PERSONALIZACIÓN Y CONFIGURACIÓN

### 7.1 UserSettings

**Archivo a crear**: `backend/src/config/user_settings.py`

```python
class UserSettings:
    """
    Sistema de configuración de usuario.
    
    CrewChief: ~200+ settings persistidos en properties/XML.
    """
    
    # Settings por categoría
    AUDIO = {
        "use_naudio": True,
        "naudio_messages_device": "",
        "naudio_background_device": "",
        "pause_between_messages": 0.5,
        "enable_radio_beeps": True,
    }
    
    SPOTTER = {
        "spotter_enabled": True,
        "spotter_gap_for_clear": 1.0,
        "min_speed_for_spotter": 10.0,
        "max_closing_speed_for_spotter": 50.0,
        "spotter_hold_repeat_frequency": 3,
        "spotter_clear_delay": 500,
        "spotter_overlap_delay": 100,
        "spotter_enable_three_wide": True,
        "spotter_name": "Jim (default)",
    }
    
    UNITS = {
        "use_metric": True,
        "use_fahrenheit": False,
        "use_psi": False,
        "use_american_terms": False,
        "use_hundredths": False,
    }
    
    EVENTS = {
        "enable_yellow_flag_messages": True,
        "enable_driver_names": True,
        "enable_damage_messages": True,
        "enable_crash_messages": True,
        "enable_session_end_messages": True,
        "enable_multiclass_messages": True,
        "enable_green_light_messages": True,
        "enable_pit_exit_brake_temp_warning": True,
        "enable_pit_exit_tyre_temp_warning": True,
        "frequency_of_opponent_race_lap_times": 3,
        "frequency_of_player_race_lap_time_reports": 5,
        "frequency_of_race_sector_delta_reports": 3,
    }
    
    LMU_SPECIFIC = {
        "enable_lmu_rest_api": True,
        "enable_lmu_pit_stop_prediction": True,
        "enable_lmu_frozen_order_messages": True,
        "enable_lmu_cut_track_heuristics": True,
        "enable_lmu_pit_lane_approach_heuristics": True,
        "enable_lmu_pit_state_during_fcy": True,
        "enable_lmu_wrong_way_message": True,
    }
```

### 7.2 DriverNameHelper

**Archivo a crear**: `backend/src/services/driver_name_helper.py`

```python
class DriverNameHelper:
    """
    Sistema de nombres de pilotos.
    
    CrewChief lee archivos de mapeo de nombres y verifica qué nombres
    tienen sonidos grabados disponibles.
    """
    
    @staticmethod
    def get_usable_driver_name(raw_name: str) -> str:
        """Limpia y mapea el nombre del juego a formato usable."""
        pass
    
    @staticmethod
    def get_usable_driver_name_for_sre(raw_name: str) -> str:
        """Versión para speech recognition."""
        pass
```

**Dependencias**: 4.2 (SoundCache), 6.1 (SpeechRecogniser)  
**Esfuerzo**: 2 días  
**Prioridad**: 🟠

---

## FASE 8 — PEARLS OF WISDOM Y SISTEMA DE RANTS

### 8.1 PearlsOfWisdom

**Archivo a crear**: `backend/src/services/pearls_of_wisdom.py`

```python
class PearlsOfWisdom:
    """
    Mensajes aleatorios de ánimo/desánimo.
    
    Se añaden automáticamente a mensajes de overtake, position change, lap time.
    Se suspenden en SafetyCar, última vuelta, daño destroyed.
    """
    
    PEARL_TYPES = {
        "GOOD": {
            "probability": 0.8,
            "messages": [
                "pearls/beautifully_executed",
                "pearls/nicely_done",
                "pearls/perfect",
                "pearls/excellent_driving",
            ]
        },
        "BAD": {
            "probability": 0.3,
            "messages": [
                "pearls/that_was_terrible",
                "pearls/what_were_you_thinking",
                "pearls/you_can_do_better",
            ]
        },
        "NEUTRAL": {
            "probability": 0.5,
            "messages": [
                "pearls/keep_pushing",
                "pearls/stay_focused",
                "pearls/keep_it_up",
            ]
        }
    }
    
    def __init__(self):
        self.max_complaints_per_session = 3
        self.complaints_count = 0
    
    def get_message_position(self, probability: float) -> str:
        """Determina si el pearl va ANTES o DESPUÉS del mensaje principal."""
        pass
    
    def get_worst_unreported_damage(self, damage_data) -> Optional[Tuple]:
        """Obtiene el peor daño no reportado."""
        pass
```

### 8.2 Rant System

```python
class RantSystem:
    """
    Sistema de rants (mensajes de enfado).
    
    CrewChief: probabilidad 10%, solo una vez por sesión.
    """
    
    def __init__(self, sweary: bool = False):
        self.played_rant_in_this_session = False
        self.rant_likelihood = 0.1 if sweary else 0.0
    
    def try_play_rant(self, message_fragments: List[dict]) -> bool:
        """Intenta jugar un rant después de los fragmentos dados."""
        if not self.played_rant_in_this_session and \
           random.random() < self.rant_likelihood:
            self.played_rant_in_this_session = True
            return True
        return False
```

**Dependencias**: 4.1 (AudioPlayer)  
**Esfuerzo**: 2 días  
**Prioridad**: 🟢

---

## FASE 9 — SISTEMA DE AUDIO AVANZADO

### 9.1 Background Player

**Archivo a crear**: `backend/src/services/background_player.py`

```python
class BackgroundPlayer:
    """
    Reproductor de fondo.
    
    CrewChief usa un reproductor separado para sonidos de fondo
    (pit window open/close, DTM, etc.) que no interfieren con
    los mensajes principales.
    """
    
    def __init__(self):
        self._playing = False
        self._current_background = None
    
    def play_background(self, sound_path: str, loop: bool = False):
        """Reproduce sonido de fondo."""
        pass
    
    def stop(self):
        """Detiene sonido de fondo."""
        pass
```

### 9.2 Device Management

**Archivo a crear**: `backend/src/services/audio_devices.py`

```python
class AudioDeviceManager:
    """
    Gestión de dispositivos de audio.
    
    CrewChief: NAudio con WASAPI/WaveOut, dispositivos separados
    para mensajes y background, detección de cambios en caliente.
    """
    
    @staticmethod
    def enumerate_devices() -> List[Dict]:
        """Enumera dispositivos de audio disponibles."""
        pass
    
    @staticmethod
    def get_default_device() -> Dict:
        """Obtiene dispositivo por defecto."""
        pass
```

### 9.3 Radio Beep System

```python
class RadioBeepSystem:
    """
    Sistema de beeps de radio.
    
    CrewChief: 8 tipos de beep configurables.
    """
    
    ENABLE_RADIO_BEEPS = True
    USE_ALTERNATE_BEEPS = False
    
    @staticmethod
    def play_start_beep():
        """Beep al empezar a hablar."""
        pass
    
    @staticmethod
    def play_end_beep():
        """Beep al terminar."""
        pass
    
    @staticmethod
    def play_listen_beep():
        """Beep al empezar a escuchar."""
        pass
    
    @staticmethod
    def play_listen_end_beep():
        """Beep al dejar de escuchar."""
        pass
    
    @staticmethod
    def play_mute_beep():
        """Beep al mutear."""
        pass
    
    @staticmethod
    def play_unmute_beep():
        """Beep al desmutear."""
        pass
    
    @staticmethod
    def play_pace_note_beep():
        """Beep de pace note recording."""
        pass
```

**Dependencias**: 4.1 (AudioPlayer)  
**Esfuerzo**: 2 días  
**Prioridad**: 🟢

---

## RESUMEN DE ESFUERZO

| Fase | Descripción | Archivos | Días |
|------|-------------|----------|------|
| 0 | Infraestructura base | 5 modificar + 2 crear | 7 |
| 1 | Modelo de datos | 2 crear + 1 modificar | 7 |
| 2 | Spotter cartesiano | 1 crear | 5 |
| 3 | Sistema de eventos | 2 crear + 1 modificar | 19 |
| 3.1 | BaseEvent + EventEngine | 2 crear | 2 |
| 3.2-3.14 | 13 eventos individuales | 13 crear | 17+ |
| 4 | Sistema de audio | 4 crear | 11 |
| 5 | Control de voz | 1 crear | 3 |
| 6 | Personalización | 2 crear | 2 |
| 7 | Pearls & Rants | 1 crear | 2 |
| 8 | Audio avanzado | 3 crear | 2 |
| **TOTAL** | | **~35 archivos** | **~58 días** |

### Prioridad de implementación

**Semana 1-2**: Fase 0 (infraestructura) — Sin esto no hay spotter
**Semana 2-4**: Fase 2 (spotter cartesiano) + Fase 3.1 (event engine) — Spotter funcional
**Semana 4-5**: Fase 4 (audio system) — Audio funcional
**Semana 5-7**: Fase 3 eventos core (Position, PitStops, Fuel, TyreMonitor, FlagsMonitor, Opponents)
**Semana 7-9**: Fase 3 eventos avanzados (LapTimes, DamageReporting, etc.)
**Semana 9-10**: Fase 1 (modelo de datos completo)
**Semana 10+**: Fases 5-9 (voz, personalización, pearls, audio avanzado)

---

*Documento maestro generado tras 30+ pasadas de análisis sobre el código fuente de CrewChiefV4.*
*Contiene el plan completo de implementación para replicar el 100% de las funcionalidades de CrewChiefV4 en Vantare Ingeniero.*
