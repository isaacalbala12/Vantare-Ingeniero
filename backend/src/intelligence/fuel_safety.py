"""Comprueba si la autonomía de combustible es realmente crítica (no solo baja en abstracto)."""

from __future__ import annotations

# Valor por defecto del sidecar cuando no hay tope de vueltas en sesión.
_SESSION_LAPS_UNKNOWN = 999.0


def is_fuel_autonomy_critical(
    *,
    estimated_laps_remaining: float,
    critical_threshold: float,
    session_laps_left: float | None = None,
    pit_stops_needed: int | None = None,
    fuel_in_tank: float | None = None,
    fuel_needed_to_finish: float | None = None,
) -> bool:
    """
    True si la autonomía está por debajo del umbral Y no alcanza para terminar la carrera.

    Escenario típico que NO debe disparar: 2.5 vueltas en depósito, 2 vueltas de carrera,
    pit_stops_needed=0 (ahorro / cálculo dice que llegas).
    """
    if estimated_laps_remaining >= critical_threshold:
        return False

    if pit_stops_needed is not None and int(pit_stops_needed) == 0:
        return False

    if session_laps_left is not None:
        laps_left = float(session_laps_left)
        if 0 < laps_left < _SESSION_LAPS_UNKNOWN:
            if estimated_laps_remaining >= laps_left:
                return False

    if (
        fuel_needed_to_finish is not None
        and fuel_in_tank is not None
        and float(fuel_needed_to_finish) > 0
        and float(fuel_in_tank) >= float(fuel_needed_to_finish)
    ):
        return False

    return True


def fuel_critical_from_strategy(telemetry: dict, strategy: dict, *, threshold: float = 3.0) -> bool:
    fuel = strategy.get("fuel") or {}
    return is_fuel_autonomy_critical(
        estimated_laps_remaining=float(fuel.get("estimated_laps_remaining", 99.0)),
        critical_threshold=threshold,
        session_laps_left=_session_laps_left(telemetry),
        pit_stops_needed=fuel.get("pit_stops_needed"),
        fuel_in_tank=_fuel_in_tank(telemetry, fuel),
        fuel_needed_to_finish=fuel.get("fuel_needed_to_finish"),
    )


def fuel_critical_from_tick(tick: dict, *, threshold: float = 1.0) -> bool:
    return is_fuel_autonomy_critical(
        estimated_laps_remaining=float(
            tick.get("fuel_laps_remaining", tick.get("estimated_laps_remaining", 99.0))
        ),
        critical_threshold=threshold,
        session_laps_left=tick.get("session_laps_left"),
        pit_stops_needed=tick.get("pit_stops_needed"),
        fuel_in_tank=tick.get("fuel_in_tank"),
        fuel_needed_to_finish=tick.get("fuel_needed_to_finish"),
    )


def _session_laps_left(telemetry: dict) -> float | None:
    if "session_laps_left" not in telemetry:
        return None
    return float(telemetry["session_laps_left"])


def _fuel_in_tank(telemetry: dict, fuel: dict) -> float | None:
    if "fuel_in_tank" in telemetry:
        return float(telemetry["fuel_in_tank"])
    if "fuel_in_tank" in fuel:
        return float(fuel["fuel_in_tank"])
    return None
