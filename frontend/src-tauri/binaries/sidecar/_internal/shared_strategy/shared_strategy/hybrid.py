from shared_strategy.models import TelemetryFrame, HybridState, TrackConfig, HybridAdvice, SpatialDeltaPair
from shared_strategy.calculation import delta_telemetry

def compute_hybrid_strategy(
    telemetry: TelemetryFrame,
    state: HybridState,
    track: TrackConfig
) -> tuple[HybridAdvice, HybridState]:
    new_state = state.model_copy(deep=True)
    
    # 1. Máquina de estados de inferencia del motor con Debounce de 5 ticks
    if telemetry.motor_state is not None:
        new_state.motor_state = telemetry.motor_state
    else:
        diff = telemetry.battery_charge - new_state.battery_charge_last
        candidate = 1  # Idle
        if diff < -0.005:
            candidate = 2  # Drain (descargando)
        elif diff > 0.005:
            candidate = 3  # Regen (cargando)
            
        if candidate == new_state.motor_state:
            new_state.motor_state_debounce_counter = 0
        else:
            new_state.motor_state_debounce_counter += 1
            if new_state.motor_state_debounce_counter >= 5:
                new_state.motor_state = candidate
                new_state.motor_state_debounce_counter = 0
                
    new_state.battery_charge_last = telemetry.battery_charge
    
    # 2. Control de tiempo de funcionamiento del motor híbrido en esta vuelta
    if new_state.motor_state == 2:
        new_state.motor_active_timer += 0.1  # Asumimos ticks de ~100ms
    else:
        new_state.motor_inactive_timer += 0.1
        
    # 3. Spatial Delta de carga neta de la batería (regen - drain)
    net_battery = telemetry.battery_regen - telemetry.battery_drain
    
    # Detectar nueva vuelta para promover el Spatial Delta
    # En este módulo, usaremos la distancia o la telemetría para detectar
    # pero para alineación completa, podemos sincronizarlo.
    # Si la distancia vuelve a 0, reiniciamos el delta
    if telemetry.lap_distance < 10.0 and len(new_state.delta_array_raw) > 50:
        if new_state.delta_array_raw:
            new_state.delta_array_last = list(new_state.delta_array_raw)
        new_state.delta_array_raw = []
        new_state.motor_active_timer = 0.0
        new_state.motor_inactive_timer = 0.0
        
    # Graba cada 10 metros
    if not new_state.delta_array_raw or (telemetry.lap_distance - new_state.delta_array_raw[-1].distance) >= 10.0:
        new_state.delta_array_raw.append(
            SpatialDeltaPair(distance=telemetry.lap_distance, value=net_battery)
        )
        
    # Proyección neta de la batería al final de la vuelta
    progress = telemetry.lap_distance / track.track_length if track.track_length > 0 else 0.0
    progress = min(1.0, max(0.0, progress))
    
    if new_state.delta_array_last:
        ref_val = delta_telemetry(
            new_state.delta_array_last,
            new_state.delta_array_raw,
            telemetry.lap_distance,
            track.track_length
        )
        delta_net = net_battery - ref_val
        battery_net_delta_lap = delta_net + new_state.delta_array_last[-1].value
    else:
        battery_net_delta_lap = net_battery / progress if progress > 0.05 else net_battery
        
    # 4. Eficiencia térmica vs eléctrica (ICE vs EV)
    # Comparar tasa de combustible usado vs descarga de batería en la vuelta
    fuel_used = telemetry.fuel_used_lap_raw
    drain = telemetry.battery_drain
    
    fuel_energy_ratio = fuel_used / drain if drain > 0.1 else 0.0
    
    # Bias: diferencia entre autonomía estimadas
    if fuel_used > 0.1 and drain > 0.1:
        thermal_est_laps = telemetry.fuel_in_tank / fuel_used
        electrical_est_laps = telemetry.battery_charge / drain
        fuel_energy_bias = thermal_est_laps - electrical_est_laps
    else:
        fuel_energy_bias = 0.0
        
    advice = HybridAdvice(
        inferred_motor_state=new_state.motor_state,
        battery_net_delta_lap=battery_net_delta_lap,
        fuel_energy_ratio=fuel_energy_ratio,
        fuel_energy_bias=fuel_energy_bias
    )
    
    return advice, new_state
