import math
from shared_strategy.models import TelemetryFrame, TyreState, BrakeState, TrackConfig, TyreAdvice, BrakeAdvice, SpatialDeltaPair
from shared_strategy.calculation import delta_telemetry

def compute_tyre_strategy(
    telemetry: TelemetryFrame,
    state: TyreState,
    track: TrackConfig,
    consumption_history: list = None
) -> tuple[TyreAdvice, TyreState]:
    new_state = state.model_copy(deep=True)
    
    current_lap = telemetry.lap_number
    last_lap = int(new_state.last_lap_stime)
    
    pace = telemetry.lap_time_previous if telemetry.lap_time_previous > 0 else (telemetry.lap_time_best if telemetry.lap_time_best > 0 else 90.0)
    
    # 1. Detección de nueva vuelta
    if current_lap > last_lap and last_lap > 0:
        # Calcular desgaste sufrido en la vuelta
        wear_fl_inc = telemetry.tyre_wear_fl - new_state.tread_last[0]
        wear_fr_inc = telemetry.tyre_wear_fr - new_state.tread_last[1]
        wear_rl_inc = telemetry.tyre_wear_rl - new_state.tread_last[2]
        wear_rr_inc = telemetry.tyre_wear_rr - new_state.tread_last[3]
        
        lap_wear = [wear_fl_inc, wear_fr_inc, wear_rl_inc, wear_rr_inc]
        
        is_valid = (
            not telemetry.in_garage
            and not telemetry.is_invalid_lap
            and not new_state.is_pit_lap
            and sum(lap_wear) > 0.001
        )
        
        if is_valid:
            new_state.delta_array_last = [list(x) for x in new_state.delta_array_raw]
            new_state.tread_wear_valid = list(lap_wear)
            
        new_state.delta_array_raw = [[], [], [], []]
        new_state.tread_last = [telemetry.tyre_wear_fl, telemetry.tyre_wear_fr, telemetry.tyre_wear_rl, telemetry.tyre_wear_rr]
        new_state.is_pit_lap = False
        new_state.pos_last = 0.0
        
    elif last_lap == 0:
        new_state.tread_last = [telemetry.tyre_wear_fl, telemetry.tyre_wear_fr, telemetry.tyre_wear_rl, telemetry.tyre_wear_rr]
        
    new_state.last_lap_stime = float(current_lap)
    
    if telemetry.in_pits:
        new_state.is_pit_lap = True
        
    # 2. Grabación del Spatial Delta (cada 10m)
    delta_d = telemetry.lap_distance - new_state.pos_last
    if delta_d >= 10.0 or delta_d < 0:
        # Incremental wear in real time
        inc_fl = telemetry.tyre_wear_fl - new_state.tread_last[0]
        inc_fr = telemetry.tyre_wear_fr - new_state.tread_last[1]
        inc_rl = telemetry.tyre_wear_rl - new_state.tread_last[2]
        inc_rr = telemetry.tyre_wear_rr - new_state.tread_last[3]
        
        new_state.delta_array_raw[0].append(SpatialDeltaPair(distance=telemetry.lap_distance, value=inc_fl))
        new_state.delta_array_raw[1].append(SpatialDeltaPair(distance=telemetry.lap_distance, value=inc_fr))
        new_state.delta_array_raw[2].append(SpatialDeltaPair(distance=telemetry.lap_distance, value=inc_rl))
        new_state.delta_array_raw[3].append(SpatialDeltaPair(distance=telemetry.lap_distance, value=inc_rr))
        new_state.pos_last = telemetry.lap_distance
        
    # 3. Proyección de desgaste al final de la vuelta
    progress = telemetry.lap_distance / track.track_length if track.track_length > 0 else 0.0
    progress = min(1.0, max(0.0, progress))
    
    projected_wear_end = [0.0, 0.0, 0.0, 0.0]
    tyres_mapped = [
        (telemetry.tyre_wear_fl, 0),
        (telemetry.tyre_wear_fr, 1),
        (telemetry.tyre_wear_rl, 2),
        (telemetry.tyre_wear_rr, 3)
    ]
    
    for wear_val, idx in tyres_mapped:
        inc_curr = wear_val - new_state.tread_last[idx]
        if new_state.delta_array_last[idx]:
            ref_wear = delta_telemetry(
                new_state.delta_array_last[idx],
                new_state.delta_array_raw[idx],
                telemetry.lap_distance,
                track.track_length
            )
            delta_wear = inc_curr - ref_wear
            projected_wear_end[idx] = max(wear_val, new_state.tread_last[idx] + new_state.tread_wear_valid[idx] + delta_wear)
        else:
            # Fallback en out-laps (decay cuadrático)
            projected_wear_end[idx] = wear_val + max(0.01, new_state.tread_wear_valid[idx]) * (1.0 - progress**2)
            
    # 4. Cálculo de vida útil restante en vueltas y minutos
    # Tomamos el peor neumático para definir el límite estratégico
    max_rate = max(0.01, max(new_state.tread_wear_valid))
    max_wear = max(telemetry.tyre_wear_fl, telemetry.tyre_wear_fr, telemetry.tyre_wear_rl, telemetry.tyre_wear_rr)
    remaining_capacity = max(0.0, 100.0 - max_wear)
    
    wear_lifespan_laps = remaining_capacity / max_rate
    wear_lifespan_mins = wear_lifespan_laps * pace / 60.0
    
    # 5. Caída de rendimiento por desgaste (Regresión lineal simple)
    estimated_drop = 0.0
    avg_curr_wear = (telemetry.tyre_wear_fl + telemetry.tyre_wear_fr + telemetry.tyre_wear_rl + telemetry.tyre_wear_rr) / 4.0
    
    if consumption_history and len(consumption_history) >= 3:
        # Extraer puntos: x = desgaste_medio, y = tiempo_vuelta
        x_pts = [item.tyre_wear_avg for item in consumption_history]
        y_pts = [item.lap_time for item in consumption_history]
        n = len(x_pts)
        
        sum_x = sum(x_pts)
        sum_y = sum(y_pts)
        sum_xx = sum(x * x for x in x_pts)
        sum_xy = sum(x * y for x, y in zip(x_pts, y_pts))
        
        denom = n * sum_xx - sum_x * sum_x
        if denom != 0:
            m = (n * sum_xy - sum_x * sum_y) / denom
            if m > 0.001:  # Relación positiva: a más desgaste, más tiempo
                estimated_drop = m * avg_curr_wear
            else:
                # Fallback: 0.015s por cada 1% de desgaste promedio
                estimated_drop = 0.015 * avg_curr_wear
        else:
            estimated_drop = 0.015 * avg_curr_wear
    else:
        estimated_drop = 0.015 * avg_curr_wear
        
    advice = TyreAdvice(
        wear_fl=telemetry.tyre_wear_fl,
        wear_fr=telemetry.tyre_wear_fr,
        wear_rl=telemetry.tyre_wear_rl,
        wear_rr=telemetry.tyre_wear_rr,
        projected_wear_end_lap=projected_wear_end,
        wear_lifespan_laps=wear_lifespan_laps,
        wear_lifespan_mins=wear_lifespan_mins,
        estimated_performance_loss_laptime=estimated_drop
    )
    
    return advice, new_state


def compute_brake_strategy(
    telemetry: TelemetryFrame,
    state: BrakeState,
    track: TrackConfig
) -> tuple[BrakeAdvice, BrakeState]:
    new_state = state.model_copy(deep=True)
    
    current_lap = telemetry.lap_number
    # Usamos pos_last como marcador para el last_lap si es necesario
    # Pero aquí podemos implementar una lógica simplificada
    # ya que el desgaste de frenos es lineal y progresivo
    
    # Ritmo y tiempos
    pace = telemetry.lap_time_previous if telemetry.lap_time_previous > 0 else 90.0
    
    # 1. Grabación lineal simple
    lap_wear = [
        telemetry.brake_wear_fl - new_state.brake_wear_curr[0],
        telemetry.brake_wear_fr - new_state.brake_wear_curr[1],
        telemetry.brake_wear_rl - new_state.brake_wear_curr[2],
        telemetry.brake_wear_rr - new_state.brake_wear_curr[3]
    ]
    
    # Si detecta nueva vuelta, actualizar el estado
    # En frenos, podemos simplificar el tracking
    if any(w > 0.001 for w in lap_wear):
        new_state.brake_wear_valid = [max(0.001, w) for w in lap_wear]
        
    new_state.brake_wear_curr = [
        telemetry.brake_wear_fl,
        telemetry.brake_wear_fr,
        telemetry.brake_wear_rl,
        telemetry.brake_wear_rr
    ]
    
    max_rate = max(0.0001, max(new_state.brake_wear_valid))
    max_wear = max(telemetry.brake_wear_fl, telemetry.brake_wear_fr, telemetry.brake_wear_rl, telemetry.brake_wear_rr)
    remaining_capacity = max(0.0, 100.0 - max_wear)
    
    lifespan_laps = remaining_capacity / max_rate
    
    advice = BrakeAdvice(
        wear_fl=telemetry.brake_wear_fl,
        wear_fr=telemetry.brake_wear_fr,
        wear_rl=telemetry.brake_wear_rl,
        wear_rr=telemetry.brake_wear_rr,
        lifespan_laps=lifespan_laps
    )
    
    return advice, new_state
