import pytest
from shared_strategy.models import TelemetryFrame, CompetitorTelemetry

class MockTelemetryFrameBuilder:
    def __init__(self):
        self.frame = TelemetryFrame(
            session_type="race",
            session_time_left=3600.0,
            session_laps_left=30.0,
            lap_number=1,
            lap_distance=0.0,
            lap_time_best=90.0,
            lap_time_previous=90.0,
            is_invalid_lap=False,
            in_garage=False,
            in_pits=False,
            pit_limiter_active=False,
            yellow_flag_active=False,
            safety_car_active=False,
            full_course_yellow_active=False,
            fuel_in_tank=100.0,
            fuel_capacity=100.0,
            fuel_used_lap_raw=0.0,
            battery_charge=100.0,
            battery_drain=0.0,
            battery_regen=0.0,
            tyre_wear_fl=0.0, tyre_wear_fr=0.0,
            tyre_wear_rl=0.0, tyre_wear_rr=0.0,
            tyre_temp_fl=80.0, tyre_temp_fr=80.0,
            tyre_temp_rl=80.0, tyre_temp_rr=80.0,
            brake_wear_fl=0.0, brake_wear_fr=0.0,
            brake_wear_rl=0.0, brake_wear_rr=0.0,
            speed=50.0, throttle=1.0, brake=0.0,
            pos_x=0.0, pos_y=0.0, pos_z=0.0,
            competitors=[]
        )

    def with_lap_distance(self, distance: float):
        self.frame.lap_distance = distance
        return self

    def with_fuel(self, fuel: float):
        self.frame.fuel_in_tank = fuel
        return self

    def with_tyre_wear(self, wear: float):
        self.frame.tyre_wear_fl = wear
        self.frame.tyre_wear_fr = wear
        self.frame.tyre_wear_rl = wear
        self.frame.tyre_wear_rr = wear
        return self

    def with_fcy(self, active: bool):
        self.frame.full_course_yellow_active = active
        return self

    def with_lap_number(self, num: int):
        self.frame.lap_number = num
        return self

    def with_competitor(self, comp: CompetitorTelemetry):
        self.frame.competitors.append(comp)
        return self

    def build(self) -> TelemetryFrame:
        return self.frame.model_copy(deep=True)

@pytest.fixture
def telemetry_builder():
    return MockTelemetryFrameBuilder()
