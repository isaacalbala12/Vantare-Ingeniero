import time
from src.intelligence.spotter_v2 import SpotterV2

s = SpotterV2()

scenarios = {
    # (nombre, flat_dict, expected_categories)
    "gap_ahead": {
        "in_pits": False, "time_gap_car_ahead": 0.3, "time_gap_car_behind": 5.0,
        "speed": 50.0, "throttle": 0.8,
    },
    "gap_behind": {
        "in_pits": False, "time_gap_car_ahead": 5.0, "time_gap_car_behind": 0.3,
        "speed": 50.0, "throttle": 0.8,
    },
    "pit_limiter_entry": {
        "in_pits": True, "pit_limiter_active": False, "pit_state": 2,
        "speed": 30.0, "throttle": 0.3,
    },
    "pit_limiter_exit": {
        "in_pits": True, "pit_limiter_active": True, "pit_state": 4,
        "speed": 40.0, "throttle": 0.4,
    },
    "safety_car": {
        "in_pits": False, "safety_car_active": True,
        "speed": 60.0, "throttle": 0.6,
    },
    "fuel_critical": {
        "in_pits": False, "estimated_laps_remaining": 2.5,
        "speed": 70.0, "throttle": 0.8,
    },
    "aero_damage": {
        "in_pits": False, "aero_damage": 5.0,
        "speed": 70.0, "throttle": 0.8,
    },
    "last_laps": {
        "in_pits": False, "session_laps_left": 2.0,
        "speed": 70.0, "throttle": 0.8,
    },
    "garage": {
        "in_pits": True, "pit_limiter_active": False,
        "speed": 0.0, "throttle": 0.0, "lap_distance": -24.0,
        "safety_car_active": True,
    },
}

for name, cfg in scenarios.items():
    s2 = SpotterV2()
    d = {
        "place": 5, "lap_number": 10, "session_laps_left": 20.0,
        "time_gap_car_ahead": 2.0, "time_gap_car_behind": 3.0,
        "fuel_in_tank": 50.0, "estimated_laps_remaining": 15.0,
        "tyre_wear": [30,30,28,25], "tyre_temp": [78,80,85,86],
        "aero_damage": 0.0, "suspension_wear": [0,0,0,0],
        "brake_wear": [15,15,12,12], "drs_active": False,
        "pit_limiter_active": False, "pit_state": 0,
        "safety_car_active": False,
        "sector": 0, "flag": 0,
        **cfg,
    }
    alerts, triggers = s2.evaluate(d)
    cats = {a.category for a in alerts}
    trigs = set(triggers)
    print(f'[{name:20s}] alerts={cats or "{none}"}  triggers={trigs or "{none}"}')
    if not cats and not trigs:
        print(f'  >>> FALLO: No se generaron alertas para {name}')
