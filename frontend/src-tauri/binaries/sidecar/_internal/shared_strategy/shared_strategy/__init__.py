from shared_strategy.models import TelemetryFrame, StrategyState, TrackConfig, StrategyAdvice, FuelState, TyreState, BrakeState, HybridState, CompetitorTrackerState
from shared_strategy.fuel import compute_fuel_strategy
from shared_strategy.tyres import compute_tyre_strategy, compute_brake_strategy
from shared_strategy.hybrid import compute_hybrid_strategy
from shared_strategy.competitors import track_competitor_pace
from shared_strategy.pit_window import compute_pit_window, adjust_strategy_for_fcy
from shared_strategy.calculation import pitlane_length

def autocalibrate_track(telemetry: TelemetryFrame, track: TrackConfig) -> TrackConfig:
    new_track = track.model_copy(deep=True)
    
    # 1. Calibrar entrada y salida de pit lane en base a coordenadas de distancia
    if telemetry.in_pits:
        if new_track.pit_entry_position is None:
            new_track.pit_entry_position = telemetry.lap_distance
    else:
        if new_track.pit_entry_position is not None and new_track.pit_exit_position is None:
            new_track.pit_exit_position = telemetry.lap_distance
            
    # 2. Calcular longitud del pit lane si tenemos entrada y salida
    if new_track.pit_entry_position is not None and new_track.pit_exit_position is not None:
        if new_track.pit_lane_length is None:
            new_track.pit_lane_length = pitlane_length(
                new_track.pit_entry_position,
                new_track.pit_exit_position,
                new_track.track_length
            )
            
    # 3. Calibrar límite de velocidad en pit lane cuando el limitador está activo
    if telemetry.pit_limiter_active and telemetry.speed > 1.0:
        if new_track.pit_speed_limit is None:
            # Capturar velocidad estable de pit lane
            new_track.pit_speed_limit = telemetry.speed
            
    # 4. Calcular tiempo de tránsito
    if new_track.pit_lane_length is not None and new_track.pit_speed_limit is not None and new_track.pit_speed_limit > 0.1:
        if new_track.pit_pass_time is None:
            # Tránsito total = longitud / velocidad + 10s de parada promedio (estacionario)
            new_track.pit_pass_time = (new_track.pit_lane_length / new_track.pit_speed_limit) + 10.0
            
    return new_track


def compute_strategy(
    telemetry: TelemetryFrame,
    state: StrategyState,
    track: TrackConfig
) -> tuple[StrategyAdvice, StrategyState]:
    """
    Punto de entrada unificado y determinista para shared-strategy.
    Toma un TelemetryFrame, el estado anterior del motor y la configuración del circuito.
    Retorna el consejo estratégico unificado y el nuevo estado a persistir.
    """
    # 1. Autocalibrar circuito en tiempo real
    updated_track = autocalibrate_track(telemetry, track)
    
    # 2. Cómputo del motor de combustible
    fuel_advice, new_fuel_state = compute_fuel_strategy(telemetry, state.fuel, updated_track)
    
    # 3. Cómputo del motor de neumáticos (le inyectamos el historial para la regresión de ritmo)
    tyre_advice, new_tyre_state = compute_tyre_strategy(
        telemetry,
        state.tyres,
        updated_track,
        consumption_history=new_fuel_state.consumption_history
    )
    
    # 4. Cómputo del motor de frenos
    brake_advice, new_brake_state = compute_brake_strategy(telemetry, state.brakes, updated_track)
    
    # 5. Cómputo del motor híbrido
    hybrid_advice, new_hybrid_state = compute_hybrid_strategy(telemetry, state.hybrid, updated_track)
    
    # 6. Cómputo del seguimiento de competidores
    comp_advice, new_comp_state = track_competitor_pace(telemetry, state.competitors, player_index=0)
    
    # 7. Cómputo de la ventana de pit stop
    pit_advice = compute_pit_window(
        telemetry,
        fuel_advice,
        tyre_advice,
        comp_advice,
        updated_track
    )
    
    # 8. Ensamblar Advice estratégico general
    raw_advice = StrategyAdvice(
        fuel=fuel_advice,
        tyres=tyre_advice,
        brakes=brake_advice,
        hybrid=hybrid_advice,
        competitors=comp_advice,
        pit_window=pit_advice,
        track=updated_track
    )
    
    # 9. Adaptar estrategia en caso de FCY o Safety Car
    final_advice = adjust_strategy_for_fcy(raw_advice, telemetry, updated_track)
    
    # 10. Re-ensamblar nuevo estado de la estrategia
    new_strategy_state = StrategyState(
        fuel=new_fuel_state,
        tyres=new_tyre_state,
        brakes=new_brake_state,
        hybrid=new_hybrid_state,
        competitors=new_comp_state
    )
    
    return final_advice, new_strategy_state
