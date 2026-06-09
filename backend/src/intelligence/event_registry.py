"""Registro de eventos de comentario proactivo (mapeo CC → Vantare)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class EventDefinition:
    event_id: str
    cc_module: str
    verbosity_min: str  # CRITICAL, HIGH, MEDIUM, LOW
    priority: str
    preemptible: bool = True
    label: str = ""


# Subconjunto inicial (A0); fases A3+ amplían el registro.
EVENT_REGISTRY: Dict[str, EventDefinition] = {
    "position_change": EventDefinition(
        event_id="position_change",
        cc_module="Position",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Cambio de posición",
    ),
    "lap_complete": EventDefinition(
        event_id="lap_complete",
        cc_module="LapTimes",
        verbosity_min="LOW",
        priority="LOW",
        label="Vuelta completada",
    ),
    "fast_lap": EventDefinition(
        event_id="fast_lap",
        cc_module="LapTimes",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Vuelta rápida",
    ),
    "gap_update": EventDefinition(
        event_id="gap_update",
        cc_module="Timings",
        verbosity_min="MEDIUM",
        priority="MEDIUM",
        label="Actualización de gaps",
    ),
    "session_end": EventDefinition(
        event_id="session_end",
        cc_module="SessionEndMessages",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Fin de sesión",
    ),
    "race_start": EventDefinition(
        event_id="race_start",
        cc_module="SessionStartMonitor",
        verbosity_min="HIGH",
        priority="HIGH",
        preemptible=False,
        label="Salida de carrera",
    ),
    "push_now": EventDefinition(
        event_id="push_now",
        cc_module="PushNow",
        verbosity_min="HIGH",
        priority="HIGH",
        label="Push now",
    ),
    "commentary_batch": EventDefinition(
        event_id="commentary_batch",
        cc_module="CommentaryOrchestrator",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Lote de comentarios",
    ),
    "flags_yellow": EventDefinition(
        event_id="flags_yellow",
        cc_module="FlagsMonitor",
        verbosity_min="HIGH",
        priority="HIGH",
        label="Bandera amarilla",
    ),
    "penalties": EventDefinition(
        event_id="penalties",
        cc_module="Penalties",
        verbosity_min="HIGH",
        priority="HIGH",
        label="Penalizaciones",
    ),
    "opponents": EventDefinition(
        event_id="opponents",
        cc_module="Opponents",
        verbosity_min="LOW",
        priority="LOW",
        label="Rivales monitorizados",
    ),
    "pit_stops": EventDefinition(
        event_id="pit_stops",
        cc_module="PitStops",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Paradas",
    ),
    "fuel": EventDefinition(
        event_id="fuel",
        cc_module="Fuel",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Combustible",
    ),
    "tyre_monitor": EventDefinition(
        event_id="tyre_monitor",
        cc_module="TyreMonitor",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Neumáticos",
    ),
    "strategy": EventDefinition(
        event_id="strategy",
        cc_module="SectorAnalysis",
        verbosity_min="LOW",
        priority="LOW",
        label="Ataque/defensa",
    ),
    "driver_swaps": EventDefinition(
        event_id="driver_swaps",
        cc_module="DriverSwaps",
        verbosity_min="MEDIUM",
        priority="NORMAL",
        label="Cambio pilotos",
    ),
    "frozen_order": EventDefinition(
        event_id="frozen_order",
        cc_module="FrozenOrder",
        verbosity_min="HIGH",
        priority="HIGH",
        label="Orden congelado",
    ),
    "drs": EventDefinition(
        event_id="drs",
        cc_module="OvertakingAids",
        verbosity_min="LOW",
        priority="LOW",
        label="DRS",
    ),
}


def get_event(event_id: str) -> Optional[EventDefinition]:
    return EVENT_REGISTRY.get(event_id)
