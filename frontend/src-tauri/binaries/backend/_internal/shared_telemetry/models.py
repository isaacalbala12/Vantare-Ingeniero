from pydantic import BaseModel, Field
from typing import List, Dict, Tuple

class TyreData(BaseModel):
    compound_name: List[str] = Field(..., description="Nombres de compuestos para las 4 ruedas (FL, FR, RL, RR)")
    wear: List[float] = Field(..., description="Desgaste porcentual por neumático (0.0 a 1.0, donde 1.0 es desgaste total)")
    pressures: List[float] = Field(..., description="Presión de inflado en kPa por neumático")
    temperatures_ico: List[Tuple[float, float, float]] = Field(
        ..., description="Temperaturas Inner-Center-Outer en Celsius por neumático (FL, FR, RL, RR)"
    )
    carcass_temperatures: List[float] = Field(..., description="Temperatura de carcasa en Celsius por neumático (FL, FR, RL, RR)")

class BrakeData(BaseModel):
    temperatures: List[float] = Field(..., description="Temperatura de discos en Celsius (FL, FR, RL, RR)")
    wear_thickness: List[float] = Field(..., description="Espesor de pastilla restante en metros (FL, FR, RL, RR)")
    bias_front: float = Field(..., description="Reparto de frenada delantero (porcentaje/fracción)")

class EngineData(BaseModel):
    gear: int = Field(..., description="Marcha engranada (-1: R, 0: N, 1+: marchas)")
    rpm: float = Field(..., description="Revoluciones por minuto actuales del motor")
    max_rpm: float = Field(..., description="Límite máximo de revoluciones del motor")
    water_temp: float = Field(..., description="Temperatura del refrigerante en Celsius")
    oil_temp: float = Field(..., description="Temperatura del aceite en Celsius")
    lift_and_coast_progress: float = Field(default=0.0, description="Progreso de Lift-and-Coast (0.0 a 1.0)")

class DriverInputs(BaseModel):
    throttle: float = Field(..., description="Posición de acelerador filtrada (0.0 a 1.0)")
    brake: float = Field(..., description="Posición de freno filtrada (0.0 a 1.0)")
    clutch: float = Field(..., description="Posición de embrague filtrada (0.0 a 1.0)")
    steering: float = Field(..., description="Ángulo de dirección física (fracción de giro)")

class LapData(BaseModel):
    lap_number: int = Field(..., description="Vuelta actual en progreso")
    lap_distance: float = Field(..., description="Distancia recorrida en la vuelta actual (metros)")
    track_progress: float = Field(..., description="Fracción de progreso de vuelta (0.0 a 1.0)")
    last_laptime: float = Field(..., description="Último tiempo de vuelta (segundos)")
    best_laptime: float = Field(..., description="Mejor tiempo de vuelta (segundos)")
    sector1: float = Field(default=0.0, description="Tiempo de sector 1 en segundos")
    sector2: float = Field(default=0.0, description="Tiempo de sector 2 (acumulado/total) en segundos")

class VehicleData(BaseModel):
    slot_id: int = Field(..., description="ID de slot de red único del simulador (mID)")
    driver_name: str = Field(..., description="Nombre del piloto")
    vehicle_name: str = Field(..., description="Nombre del coche / modelo en pista")
    class_name: str = Field(..., description="Categoría de coche (LMH, LMP2, GT3, etc.)")
    place: int = Field(..., description="Posición física actual en carrera")
    in_pits: bool = Field(..., description="¿Está actualmente en el pit lane?")
    lap_distance: float = Field(..., description="Distancia recorrida en la vuelta actual (metros)")
    track_progress: float = Field(..., description="Fracción de progreso de vuelta (0.0 a 1.0)")
    current_lap: int = Field(..., description="Vuelta actual en progreso")
    last_laptime: float = Field(..., description="Último tiempo de vuelta (segundos)")
    best_laptime: float = Field(..., description="Mejor tiempo de vuelta (segundos)")
    position_xyz: Tuple[float, float, float] = Field(..., description="Posición en coordenadas mundiales (X, Y, Z)")

class SessionData(BaseModel):
    session_type: int = Field(..., description="Tipo (0: Test, 1: Practice, 2: Qualy, 3: Warmup, 4: Race)")
    time_remaining: float = Field(..., description="Tiempo restante en la sesión (segundos)")
    track_temp: float = Field(..., description="Temperatura superficial de pista en Celsius")
    ambient_temp: float = Field(..., description="Temperatura ambiental en Celsius")
    wetness_average: float = Field(..., description="Humedad promedio de pista (0.0 a 1.0)")
    raininess: float = Field(..., description="Intensidad de lluvia actual (0.0 a 1.0)")
    track_name: str = Field(default="", description="Nombre del circuito actual")

class RaceState(BaseModel):
    session: SessionData = Field(..., description="Información de la sesión actual")
    player: VehicleData = Field(..., description="Información del jugador")
    tyres: TyreData = Field(..., description="Información de neumáticos del jugador")
    brakes: BrakeData = Field(..., description="Información de frenos del jugador")
    engine: EngineData = Field(..., description="Información del motor del jugador")
    inputs: DriverInputs = Field(..., description="Entradas del piloto jugador")
    opponents: Dict[int, VehicleData] = Field(default_factory=dict, description="Diccionario de rivales indexados por slot_id")
    timestamp: float = Field(..., description="Marca temporal del reloj del sistema (monotonic)")
