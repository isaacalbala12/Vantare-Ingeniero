from shared_strategy.calculation import (
    linear_interp,
    binary_search_higher_column,
    binary_search_lower_column,
    total_fuel_needed,
    end_stint_laps,
    one_less_pit_stop_consumption
)
from shared_strategy.models import SpatialDeltaPair

def test_linear_interp():
    assert linear_interp(5.0, 0.0, 0.0, 10.0, 100.0) == 50.0
    assert linear_interp(5.0, 5.0, 10.0, 5.0, 20.0) == 10.0

def test_binary_search_higher_column():
    arr = [
        SpatialDeltaPair(distance=0.0, value=0.0),
        SpatialDeltaPair(distance=100.0, value=2.0),
        SpatialDeltaPair(distance=200.0, value=4.0)
    ]
    assert binary_search_higher_column(arr, 50.0) == 1
    assert binary_search_higher_column(arr, 150.0) == 2
    assert binary_search_higher_column(arr, 250.0) == 2

def test_binary_search_lower_column():
    arr = [
        SpatialDeltaPair(distance=0.0, value=0.0),
        SpatialDeltaPair(distance=100.0, value=2.0),
        SpatialDeltaPair(distance=200.0, value=4.0)
    ]
    assert binary_search_lower_column(arr, 50.0) == 0
    assert binary_search_lower_column(arr, 150.0) == 1
    assert binary_search_lower_column(arr, 250.0) == 2

def test_total_fuel_needed():
    assert total_fuel_needed(10, 3.0, 2.0) == 32.0

def test_end_stint_laps():
    assert end_stint_laps(30.0, 3.0) == 10.0
    assert end_stint_laps(30.0, 0.0) == 0.0

def test_one_less_pit_stop_consumption():
    # 10 laps remain, capacity = 100, current fuel = 50, est pits = 2.0
    # Target pits = ceil(2) - 1 = 1 pit stop
    # Target fuel = 1 * 100 + 50 = 150
    # target consumption = 150 / 10 = 15.0
    assert one_less_pit_stop_consumption(10, 100, 50, 2.0) == 15.0
