"""Factory for the standard Crew Chief event suite (shared by main + replay harness)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.intelligence.crewchief_events.modules import (
    BatteryEvent,
    DamageEvent,
    DriverSwapsEvent,
    EngineMonitorEvent,
    FlagsEvent,
    FrozenOrderEvent,
    FuelEvent,
    LapCounterEvent,
    LapTimesEvent,
    MulticlassEvent,
    OpponentMessagesEvent,
    OpponentsEvent,
    OvertakingAidsEvent,
    PearlsEvent,
    PenaltiesEvent,
    PitStopsEvent,
    PositionEvent,
    PushNowEvent,
    RaceTimeEvent,
    RainEvent,
    SessionEndEvent,
    StrategyEvent,
    TimingsEvent,
    TyreMonitorEvent,
    WatchedOpponentsEvent,
)
from src.intelligence.crewchief_events.suite import CrewChiefEventSuite

if TYPE_CHECKING:
    from src.intelligence.engine import IntelligenceEngine


def build_crewchief_suite(engine: IntelligenceEngine) -> CrewChiefEventSuite:
    penalties_module = PenaltiesEvent()
    engine.penalty_tracker = penalties_module.tracker
    return CrewChiefEventSuite(
        [
            FlagsEvent(),
            FrozenOrderEvent(),
            MulticlassEvent(),
            penalties_module,
            DamageEvent(),
            RainEvent(),
            PositionEvent(),
            LapTimesEvent(),
            LapCounterEvent(),
            RaceTimeEvent(),
            PushNowEvent(),
            FuelEvent(),
            PitStopsEvent(),
            TyreMonitorEvent(),
            EngineMonitorEvent(),
            BatteryEvent(),
            OvertakingAidsEvent(),
            TimingsEvent(),
            OpponentsEvent(),
            OpponentMessagesEvent(),
            WatchedOpponentsEvent(),
            StrategyEvent(),
            PearlsEvent(),
            DriverSwapsEvent(),
            SessionEndEvent(),
        ],
        engine=engine,
    )
