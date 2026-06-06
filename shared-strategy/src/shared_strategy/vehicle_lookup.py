"""Tabla de dimensiones por vehículo LMU (ancho típico en metros)."""

from __future__ import annotations

_VEHICLE_WIDTHS: dict[str, float] = {
    # Hypercar / LMH
    "Ferrari 499P": 2.0,
    "Toyota GR010": 2.0,
    "Porsche 963": 2.0,
    "Cadillac V-Series.R": 2.0,
    "Peugeot 9X8": 2.0,
    "Vanwall Vandervell 680": 2.0,
    "Glickenhaus SCG 007": 2.0,
    "Alpine A424": 2.0,
    "BMW M Hybrid V8": 2.0,
    "Isotta Fraschini Tipo 6": 2.0,
    # LMP2
    "Oreca 07": 1.9,
    "Ligier JS P217": 1.9,
    # GT3
    "Ferrari 296 GT3": 2.05,
    "Porsche 911 GT3 R": 2.05,
    "Mercedes-AMG GT3": 2.05,
    "BMW M4 GT3": 2.05,
    "Lamborghini Huracan GT3 EVO2": 2.05,
    "McLaren 720S GT3 EVO": 2.05,
    "Aston Martin Vantage AMR GT3": 2.05,
    "Corvette C8.R GT3": 2.05,
    "Ford Mustang GT3": 2.05,
    "Lexus RC F GT3": 2.05,
}


def get_vehicle_width(vehicle_name: str, class_fallback: float = 2.0) -> float:
    if not vehicle_name:
        return class_fallback
    if vehicle_name in _VEHICLE_WIDTHS:
        return _VEHICLE_WIDTHS[vehicle_name]
    for key, width in _VEHICLE_WIDTHS.items():
        if key.lower() in vehicle_name.lower() or vehicle_name.lower() in key.lower():
            return width
    return class_fallback
