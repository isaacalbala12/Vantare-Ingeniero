"""EventManager — orchestrates all 15 RaceEvent instances via AudioQueueManager.

Evaluates all events at 0.5Hz (triggered from IntelligenceEngine.evaluate_cycle),
adapts AlertMessage outputs to QueuedMessage via EventAdapter, and feeds them
into the AudioQueueManager's dual queue system.
"""

import logging
from typing import Dict, Any, List, Optional

from src.intelligence.events.base_event import RaceEvent
from src.intelligence.events.fuel import FuelEvent
from src.intelligence.events.position import PositionEvent
from src.intelligence.events.lap_times import LapTimesEvent
from src.intelligence.events.race_time import RaceTimeEvent
from src.intelligence.events.pit_stops import PitStopsEvent
from src.intelligence.events.penalties import PenaltiesEvent
from src.intelligence.events.flags import FlagsEvent
from src.intelligence.events.damage import DamageEvent
from src.intelligence.events.engine import EngineEvent
from src.intelligence.events.conditions import ConditionsEvent
from src.intelligence.events.multiclass import MulticlassEvent
from src.intelligence.events.session_end import SessionEndEvent
from src.intelligence.events.tyres import TyreEvent
from src.intelligence.events.lap_counter import LapCounterEvent
from src.intelligence.events.common_actions import CommonActionsEvent
from src.services.audio_queue import AudioQueueManager
from src.intelligence.session_adapter import normalize_session_type, normalize_session_phase
from src.intelligence.event_adapter import EventAdapter
from src.intelligence.verbosity import VerbosityEngine

logger = logging.getLogger("vantare.event_manager")


class EventManager:
    def __init__(self, audio_queue: AudioQueueManager) -> None:
        self.audio_queue = audio_queue
        self.adapter = EventAdapter(audio_queue)
        self.verbosity_engine = VerbosityEngine()

        self.events: List[RaceEvent] = [
            FuelEvent(),
            PositionEvent(),
            LapTimesEvent(),
            RaceTimeEvent(),
            PitStopsEvent(),
            PenaltiesEvent(),
            FlagsEvent(),
            DamageEvent(),
            EngineEvent(),
            ConditionsEvent(),
            MulticlassEvent(),
            SessionEndEvent(),
            TyreEvent(),
            LapCounterEvent(),
            CommonActionsEvent(),
        ]

        for event in self.events:
            self.adapter.adapt_event(event)

        self._previous_state: Dict[str, Any] = {}

    def trigger_all(self, current_state: Dict[str, Any]) -> None:
        session_type = normalize_session_type(current_state.get("session_type"))
        session_phase = normalize_session_phase(current_state.get("session_phase", ""))

        telemetry_dict = {k: v for k, v in current_state.items()
                         if k in ("speed", "gap_ahead", "gap_behind")}
        self.audio_queue.set_verbosity(self.verbosity_engine.evaluate(telemetry_dict))
        self.audio_queue.update_state(current_state)

        for event in self.events:
            if event.is_applicable(session_type, session_phase):
                try:
                    event.reset_tick()
                    alerts = event.evaluate(current_state)
                    self.adapter.process_event_output(event, alerts)
                except Exception as e:
                    logger.error("Event %s failed: %s", event.__class__.__name__, e, exc_info=True)

        self._previous_state = current_state.copy()

    def on_session_change(self) -> None:
        """Reset all event states and previous_state on new session."""
        self._previous_state = {}
        for event in self.events:
            event.reset_session()

    def set_broadcast_callback(self, callback) -> None:
        """Set broadcast callback on all events (for spotter express path)."""
        for event in self.events:
            if hasattr(event, 'broadcast_callback'):
                event.broadcast_callback = callback
