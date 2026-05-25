import pytest
from shared_strategy import compute_strategy
from shared_strategy.models import StrategyState, TrackConfig, CompetitorTelemetry

def test_full_strategy_pipeline(telemetry_builder):
    state = StrategyState()
    track = TrackConfig(
        track_length=1000.0,
        pit_entry_position=800.0,
        pit_exit_position=100.0,
        pit_lane_length=300.0,
        pit_speed_limit=22.2,
        pit_pass_time=25.0
    )
    
    # 1. Simular primera vuelta, progresando distancia y reduciendo combustible
    frame = telemetry_builder.with_lap_number(1).with_lap_distance(0.0).with_fuel(100.0).build()
    advice, state = compute_strategy(frame, state, track)
    
    assert advice.fuel.estimated_laps_remaining > 0
    assert advice.tyres.wear_lifespan_laps > 0
    
    # Avanzar 500m con consumo de combustible
    frame = telemetry_builder.with_lap_number(1).with_lap_distance(500.0).with_fuel(98.5).build()
    advice, state = compute_strategy(frame, state, track)
    
    # Verificar que el Spatial Delta tiene puntos grabados
    assert len(state.fuel.delta_array_raw) > 0
    
    # 2. Simular cruce de meta a vuelta 2
    frame = telemetry_builder.with_lap_number(2).with_lap_distance(0.0).with_fuel(97.0).build()
    advice, state = compute_strategy(frame, state, track)
    
    # El delta de la vuelta anterior se debió haber promovido como referencia
    assert len(state.fuel.delta_array_last) > 0
    assert state.fuel.used_last_valid == pytest.approx(3.0)
    
    # 3. Testear Spatial Delta comparativo en tiempo real
    frame = telemetry_builder.with_lap_number(2).with_lap_distance(500.0).with_fuel(95.4).build() # 1.6 de consumo a mitad de vuelta vs 1.5 esperado
    advice, state = compute_strategy(frame, state, track)
    
    # El delta instantáneo debería ser positivo (usando un poco más de lo normal)
    assert advice.fuel.instantaneous_delta_fuel > 0.0
    
def test_fcy_adaptation(telemetry_builder):
    state = StrategyState()
    track = TrackConfig(track_length=1000.0, pit_pass_time=25.0)
    
    # Simular condiciones normales
    frame_normal = telemetry_builder.with_fcy(False).build()
    advice_normal, _ = compute_strategy(frame_normal, state, track)
    
    # Simular FCY
    frame_fcy = telemetry_builder.with_fcy(True).build()
    advice_fcy, _ = compute_strategy(frame_fcy, state, track)
    
    # Verificar que bajo FCY el coste del pitlane es la mitad
    assert advice_fcy.pit_window.pit_loss_time_estimate == pytest.approx(advice_normal.pit_window.pit_loss_time_estimate * 0.5)
    # Y la ventana óptima se adelanta inmediatamente a la vuelta siguiente
    assert advice_fcy.pit_window.optimal_pit_lap == frame_fcy.lap_number + 1

def test_competitor_pace(telemetry_builder):
    state = StrategyState()
    track = TrackConfig(track_length=1000.0)
    
    # Añadir un rival
    comp = CompetitorTelemetry(
        driver_index=5,
        driver_name="Alonso",
        driver_class="GT3",
        standing_position=2,
        class_position=2,
        lap_number=1,
        lap_distance=100.0,
        lap_time_best=92.0,
        lap_time_previous=92.0,
        in_pits=False,
        pit_requested=False,
        estimated_time_into_lap=2.0,
        speed=50.0,
        fuel_capacity_fraction=0.9
    )
    
    frame = telemetry_builder.with_competitor(comp).build()
    advice, state = compute_strategy(frame, state, track)
    
    assert len(advice.competitors) == 1
    assert advice.competitors[0].driver_name == "Alonso"
