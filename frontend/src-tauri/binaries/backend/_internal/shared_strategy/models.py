from pydantic import BaseModel, Field

class CompetitorTelemetry(BaseModel):
    driver_index: int
    driver_name: str
    driver_class: str
    standing_position: int
    class_position: int
    lap_number: int
    lap_distance: float
    lap_time_best: float
    lap_time_previous: float
    in_pits: bool
    pit_requested: bool
    estimated_time_into_lap: float
    speed: float  # m/s
    fuel_capacity_fraction: float  # 0.0 a 1.0

class TelemetryFrame(BaseModel):
    # Sesión y Tiempos
    session_type: str  # "practice", "qualifying", "race"
    session_time_left: float  # segundos
    session_laps_left: float
    lap_number: int
    lap_distance: float  # metros acumulados en la vuelta actual
    lap_time_best: float
    lap_time_previous: float
    is_invalid_lap: bool
    in_garage: bool
    in_pits: bool
    pit_limiter_active: bool
    
    # Banderas de la Sesión
    yellow_flag_active: bool
    safety_car_active: bool
    full_course_yellow_active: bool

    # Combustible e Híbrido
    fuel_in_tank: float  # litros
    fuel_capacity: float  # litros
    fuel_used_lap_raw: float  # litros consumidos en la vuelta actual
    battery_charge: float  # porcentaje 0-100
    battery_drain: float  # energía descargada en la vuelta actual
    battery_regen: float  # energía regenerada en la vuelta actual
    motor_state: int | None = None  # 1=Idle, 2=Drain, 3=Regen

    # Ruedas (Desgaste 0-100% y Temperaturas)
    tyre_wear_fl: float
    tyre_wear_fr: float
    tyre_wear_rl: float
    tyre_wear_rr: float
    tyre_temp_fl: float
    tyre_temp_fr: float
    tyre_temp_rl: float
    tyre_temp_rr: float
    
    # Frenos (Desgaste 0-100%)
    brake_wear_fl: float
    brake_wear_fr: float
    brake_wear_rl: float
    brake_wear_rr: float

    # Física y Coordenadas
    speed: float  # m/s
    throttle: float  # 0.0 a 1.0
    brake: float  # 0.0 a 1.0
    pos_x: float
    pos_y: float
    pos_z: float

    # Competidores
    competitors: list[CompetitorTelemetry] = Field(default_factory=list)

class TrackConfig(BaseModel):
    track_length: float  # metros
    pit_entry_position: float | None = None  # distancia de entrada
    pit_exit_position: float | None = None   # distancia de salida
    pit_lane_length: float | None = None      # metros
    pit_speed_limit: float | None = None      # m/s
    pit_pass_time: float | None = None        # segundos de tránsito en pit lane

class SpatialDeltaPair(BaseModel):
    distance: float
    value: float

class ConsumptionDataSet(BaseModel):
    lap_num: int
    lap_time: float
    fuel_used: float
    battery_regen: float
    battery_drain: float
    tyre_wear_avg: float
    fuel_capacity: float

class StintData(BaseModel):
    laps: int
    time: float
    fuel: float
    energy: float
    tyre_wear: float
    lap_consistency: float
    compound: str

class FuelState(BaseModel):
    delta_array_raw: list[SpatialDeltaPair] = Field(default_factory=list)
    delta_array_last: list[SpatialDeltaPair] = Field(default_factory=list)
    amount_start: float = 0.0
    amount_last: float = 0.0
    last_lap_stime: float = 0.0
    used_last_valid: float = 0.0
    is_pit_lap: bool = False
    validating: bool = True
    recording: bool = False
    pos_last: float = 0.0
    pos_recorded: float = 0.0
    gps_last: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    laps_left: float = 0.0
    end_timer_laps_left: float = 0.0
    consumption_history: list[ConsumptionDataSet] = Field(default_factory=list)
    stint_history: list[StintData] = Field(default_factory=list)

class TyreState(BaseModel):
    tread_last: list[float] = Field(default_factory=lambda: [100.0, 100.0, 100.0, 100.0])  # FL, FR, RL, RR
    tread_wear_curr: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    tread_wear_valid: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    delta_array_raw: list[list[SpatialDeltaPair]] = Field(default_factory=lambda: [[], [], [], []])  # 4 neumáticos
    delta_array_last: list[list[SpatialDeltaPair]] = Field(default_factory=lambda: [[], [], [], []])
    is_valid_delta: bool = False
    pos_last: float = 0.0
    last_lap_stime: float = 0.0
    is_pit_lap: bool = False
    delta_recording: bool = False

class BrakeState(BaseModel):
    brake_wear_curr: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    brake_wear_valid: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    delta_array_raw: list[list[SpatialDeltaPair]] = Field(default_factory=lambda: [[], [], [], []])
    delta_array_last: list[list[SpatialDeltaPair]] = Field(default_factory=lambda: [[], [], [], []])
    pos_last: float = 0.0
    is_pit_lap: bool = False
    delta_recording: bool = False

class HybridState(BaseModel):
    motor_state: int = 1  # 1=Idle, 2=Drain, 3=Regen
    motor_state_debounce_counter: int = 0
    battery_charge_last: float = 0.0
    delta_array_raw: list[SpatialDeltaPair] = Field(default_factory=list)
    delta_array_last: list[SpatialDeltaPair] = Field(default_factory=list)
    motor_active_timer: float = 0.0
    motor_inactive_timer: float = 0.0

class CompetitorHistoryState(BaseModel):
    lap_time_history: list[float] = Field(default_factory=list)  # Ring buffer de hasta 5 vueltas
    fuel_history: list[tuple[int, float]] = Field(default_factory=list)  # (vuelta, fraccion_combustible)
    num_pit_stops: int = 0
    last_in_pits: bool = False
    stint_laps_done: int = 0
    pit_requested_last: bool = False
    best_lap: float = 0.0
    average_lap: float = 0.0

class CompetitorTrackerState(BaseModel):
    competitors: dict[int, CompetitorHistoryState] = Field(default_factory=dict)  # Mapeado por driver_index

class StrategyState(BaseModel):
    fuel: FuelState = Field(default_factory=FuelState)
    tyres: TyreState = Field(default_factory=TyreState)
    brakes: BrakeState = Field(default_factory=BrakeState)
    hybrid: HybridState = Field(default_factory=HybridState)
    competitors: CompetitorTrackerState = Field(default_factory=CompetitorTrackerState)

class FuelAdvice(BaseModel):
    estimated_laps_remaining: float
    estimated_time_remaining: float  # segundos
    fuel_needed_to_finish: float     # litros
    stint_end_fuel: float            # litros sobrantes al acabar stint
    stint_end_laps: float            # vueltas que durará el combustible
    pit_stops_needed: int
    one_less_stop_target_consumption: float  # litros/vuelta
    instantaneous_delta_fuel: float  # combustible respecto a la vuelta de referencia

class TyreAdvice(BaseModel):
    wear_fl: float
    wear_fr: float
    wear_rl: float
    wear_rr: float
    projected_wear_end_lap: list[float]  # FL, FR, RL, RR
    wear_lifespan_laps: float
    wear_lifespan_mins: float
    estimated_performance_loss_laptime: float

class BrakeAdvice(BaseModel):
    wear_fl: float
    wear_fr: float
    wear_rl: float
    wear_rr: float
    lifespan_laps: float

class HybridAdvice(BaseModel):
    inferred_motor_state: int
    battery_net_delta_lap: float
    fuel_energy_ratio: float
    fuel_energy_bias: float

class CompetitorPace(BaseModel):
    driver_index: int
    driver_name: str
    driver_class: str
    standing_position: int
    class_position: int
    gap_to_player: float
    best_lap: float
    average_lap: float
    estimated_stint_length: int
    num_pit_stops: int
    in_pits: bool

class PitWindowAdvice(BaseModel):
    earliest_pit_lap: int
    latest_pit_lap: int
    optimal_pit_lap: int
    undercut_potential: bool
    overcut_potential: bool
    pit_loss_time_estimate: float

class StrategyAdvice(BaseModel):
    fuel: FuelAdvice
    tyres: TyreAdvice
    brakes: BrakeAdvice
    hybrid: HybridAdvice
    competitors: list[CompetitorPace] = Field(default_factory=list)
    pit_window: PitWindowAdvice
    track: TrackConfig
