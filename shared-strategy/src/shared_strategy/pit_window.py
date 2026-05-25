import math
from shared_strategy.models import TelemetryFrame, FuelAdvice, TyreAdvice, CompetitorPace, TrackConfig, PitWindowAdvice, StrategyAdvice

def compute_pit_window(
    telemetry: TelemetryFrame,
    fuel: FuelAdvice,
    tyres: TyreAdvice,
    competitors: list[CompetitorPace],
    track: TrackConfig
) -> PitWindowAdvice:
    current_lap = telemetry.lap_number
    
    # 1. Definición de límites duros (combustible y neumáticos)
    fuel_limit = int(fuel.stint_end_laps)
    tyre_limit = int(tyres.wear_lifespan_laps)
    
    latest_pit_lap = current_lap + min(fuel_limit, tyre_limit)
    if latest_pit_lap <= current_lap:
        latest_pit_lap = current_lap + 1
        
    # Ventana temprana es el 80% del stint teórico restante
    stint_total_est = min(fuel_limit, tyre_limit)
    earliest_pit_lap = current_lap + int(stint_total_est * 0.8)
    if earliest_pit_lap <= current_lap:
        earliest_pit_lap = current_lap + 1
        
    # Asegurar orden lógico
    if earliest_pit_lap > latest_pit_lap:
        earliest_pit_lap = latest_pit_lap
        
    # 2. Pérdida estimada en boxes
    pit_loss_time_estimate = track.pit_pass_time if track.pit_pass_time is not None else 25.0
    
    # 3. Evaluación de Undercut / Overcut
    # Buscar rival directo adelante y atrás (misma clase)
    ahead_comp = None
    behind_comp = None
    
    for c in competitors:
        if c.driver_class == telemetry.session_type: # o misma clase si tuviéramos campo de clase
            # Como fallback evaluamos por gap cercano
            if 0.1 < c.gap_to_player < 5.0:
                if ahead_comp is None or c.gap_to_player < ahead_comp.gap_to_player:
                    ahead_comp = c
            elif -5.0 < c.gap_to_player < -0.1:
                if behind_comp is None or c.gap_to_player > behind_comp.gap_to_player:
                    behind_comp = c
                    
    # Undercut: si tenemos degradación y el de adelante está cerca
    undercut_potential = False
    if ahead_comp and tyres.estimated_performance_loss_laptime > 1.0:
        undercut_potential = True
        
    # Overcut: si tenemos neumáticos muy sanos y el de atrás presiona
    overcut_potential = False
    if behind_comp and tyres.estimated_performance_loss_laptime < 0.3:
        overcut_potential = True
        
    # 4. Vuelta Óptima
    # Por defecto es 1 vuelta antes del límite físico
    optimal_pit_lap = latest_pit_lap - 1
    if optimal_pit_lap < earliest_pit_lap:
        optimal_pit_lap = earliest_pit_lap
        
    # Evitar tráfico si es posible
    # Si al salir de pits (con pérdida de pit_loss) caemos encima de un rival lento,
    # retrasamos o adelantamos 1 vuelta
    for c in competitors:
        est_gap_after_pit = c.gap_to_player - pit_loss_time_estimate
        if -1.5 < est_gap_after_pit < 1.5:
            # Hay tráfico en el pit exit! Intentar retrasar parada si los neumáticos lo permiten
            if tyres.wear_lifespan_laps > 2:
                optimal_pit_lap = min(latest_pit_lap, optimal_pit_lap + 1)
            else:
                optimal_pit_lap = max(earliest_pit_lap, optimal_pit_lap - 1)
            break
            
    return PitWindowAdvice(
        earliest_pit_lap=earliest_pit_lap,
        latest_pit_lap=latest_pit_lap,
        optimal_pit_lap=optimal_pit_lap,
        undercut_potential=undercut_potential,
        overcut_potential=overcut_potential,
        pit_loss_time_estimate=pit_loss_time_estimate
    )

def adjust_strategy_for_fcy(
    advice: StrategyAdvice,
    telemetry: TelemetryFrame,
    track: TrackConfig
) -> StrategyAdvice:
    is_fcy = telemetry.full_course_yellow_active or telemetry.safety_car_active or telemetry.yellow_flag_active
    
    if not is_fcy:
        return advice
        
    # Copia profunda de los consejos estratégicos para modificarlos bajo bandera amarilla
    new_advice = advice.model_copy(deep=True)
    
    # 1. Bajo FCY el consumo de combustible e ICE cae un 40%
    new_advice.fuel.estimated_laps_remaining *= 1.4
    new_advice.fuel.stint_end_laps *= 1.4
    new_advice.fuel.fuel_needed_to_finish *= 0.7
    
    # 2. El desgaste de neumáticos se reduce un 30%
    new_advice.tyres.wear_lifespan_laps *= 1.3
    
    # 3. La pérdida en pit lane relativa a pista se reduce un 50%
    new_advice.pit_window.pit_loss_time_estimate *= 0.5
    
    # 4. Parada súper barata: Recomendamos entrar en la vuelta siguiente inmediatamente
    new_advice.pit_window.optimal_pit_lap = telemetry.lap_number + 1
    new_advice.pit_window.earliest_pit_lap = telemetry.lap_number + 1
    
    return new_advice
