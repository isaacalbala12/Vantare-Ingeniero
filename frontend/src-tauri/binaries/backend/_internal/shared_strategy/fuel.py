import math
from shared_strategy.models import TelemetryFrame, FuelState, TrackConfig, FuelAdvice, SpatialDeltaPair, ConsumptionDataSet
from shared_strategy.calculation import (
    delta_telemetry,
    time_type_laps_remain,
    total_fuel_needed,
    end_stint_fuel,
    end_stint_laps,
    end_stint_pit_counts,
    one_less_pit_stop_consumption
)

def compute_fuel_strategy(
    telemetry: TelemetryFrame,
    state: FuelState,
    track: TrackConfig
) -> tuple[FuelAdvice, FuelState]:
    # Hacemos una copia profunda de estado para evitar efectos secundarios
    new_state = state.model_copy(deep=True)
    
    # 1. Ritmo y tiempos
    pace = telemetry.lap_time_previous if telemetry.lap_time_previous > 0 else (telemetry.lap_time_best if telemetry.lap_time_best > 0 else 90.0)
    
    # 2. Detección de cruce de meta (Vuelta nueva)
    last_lap = int(new_state.amount_last)
    current_lap = telemetry.lap_number
    
    if current_lap > last_lap and last_lap > 0:
        # Calcular consumo real de la vuelta previa
        lap_used = max(0.0, new_state.amount_start - telemetry.fuel_in_tank)
        
        # Validar si fue una vuelta limpia para registrar en el Spatial Delta
        is_valid = (
            not telemetry.in_garage
            and not telemetry.is_invalid_lap
            and not new_state.is_pit_lap
            and lap_used > 0.1
        )
        
        if is_valid:
            new_state.delta_array_last = list(new_state.delta_array_raw)
            new_state.used_last_valid = lap_used
            
            # Registrar en el historial de consumos
            avg_wear = (telemetry.tyre_wear_fl + telemetry.tyre_wear_fr + telemetry.tyre_wear_rl + telemetry.tyre_wear_rr) / 4.0
            history_item = ConsumptionDataSet(
                lap_num=last_lap,
                lap_time=pace,
                fuel_used=lap_used,
                battery_regen=telemetry.battery_regen,
                battery_drain=telemetry.battery_drain,
                tyre_wear_avg=avg_wear,
                fuel_capacity=telemetry.fuel_capacity
            )
            new_state.consumption_history.append(history_item)
            
        # Resetear estado de la nueva vuelta
        new_state.delta_array_raw = []
        new_state.amount_start = telemetry.fuel_in_tank
        new_state.is_pit_lap = False
        new_state.pos_last = 0.0
        
    elif last_lap == 0:
        new_state.amount_start = telemetry.fuel_in_tank
        
    new_state.amount_last = float(current_lap)
    
    # Registrar si entra a pits en cualquier punto de la vuelta
    if telemetry.in_pits:
        new_state.is_pit_lap = True
        
    # 3. Spatial Delta en tiempo real
    fuel_used_curr = max(0.0, new_state.amount_start - telemetry.fuel_in_tank)
    
    # Graba cada 10 metros la distancia y el combustible usado
    delta_d = telemetry.lap_distance - new_state.pos_last
    if delta_d >= 10.0 or delta_d < 0:
        new_state.delta_array_raw.append(
            SpatialDeltaPair(distance=telemetry.lap_distance, value=fuel_used_curr)
        )
        new_state.pos_last = telemetry.lap_distance
        
    # 4. Proyección de consumo por vuelta actual
    instantaneous_delta = 0.0
    if new_state.delta_array_last:
        ref_fuel = delta_telemetry(
            new_state.delta_array_last,
            new_state.delta_array_raw,
            telemetry.lap_distance,
            track.track_length
        )
        instantaneous_delta = fuel_used_curr - ref_fuel
        used_estimate = max(0.1, new_state.used_last_valid + instantaneous_delta)
    else:
        # Fallback a promedios históricos
        if new_state.consumption_history:
            recent = new_state.consumption_history[-3:]
            used_estimate = sum(x.fuel_used for x in recent) / len(recent)
        else:
            used_estimate = max(3.0, telemetry.fuel_used_lap_raw if telemetry.fuel_used_lap_raw > 0.1 else 3.0)
            
    # 5. Proyecciones de final de carrera y stint
    if telemetry.session_laps_left > 0:
        laps_remain = telemetry.session_laps_left
    else:
        laps_remain = time_type_laps_remain(telemetry.session_time_left, pace, lap_into=0.0)
        
    estimated_laps_remaining = end_stint_laps(telemetry.fuel_in_tank, used_estimate)
    estimated_time_remaining = estimated_laps_remaining * pace
    
    # Margen de seguridad: 3 litros por defecto
    safety_margin = 3.0
    fuel_needed_to_finish = total_fuel_needed(laps_remain, used_estimate, safety_margin)
    
    stint_end_fuel_val = end_stint_fuel(telemetry.fuel_in_tank, used_estimate)
    
    # Calcular paradas en boxes necesarias
    if fuel_needed_to_finish > telemetry.fuel_in_tank:
        raw_pits = end_stint_pit_counts(fuel_needed_to_finish - telemetry.fuel_in_tank, telemetry.fuel_capacity, amount_end=safety_margin)
        pit_stops_needed = math.ceil(raw_pits)
    else:
        pit_stops_needed = 0
        
    # Combustible objetivo para reducir una parada en carrera
    one_less_target = one_less_pit_stop_consumption(
        laps_remain,
        telemetry.fuel_capacity,
        telemetry.fuel_in_tank,
        pit_stops_needed
    )
    
    advice = FuelAdvice(
        estimated_laps_remaining=estimated_laps_remaining,
        estimated_time_remaining=estimated_time_remaining,
        fuel_needed_to_finish=fuel_needed_to_finish,
        stint_end_fuel=stint_end_fuel_val,
        stint_end_laps=estimated_laps_remaining,
        pit_stops_needed=pit_stops_needed,
        one_less_stop_target_consumption=one_less_target,
        instantaneous_delta_fuel=instantaneous_delta
    )
    
    return advice, new_state
