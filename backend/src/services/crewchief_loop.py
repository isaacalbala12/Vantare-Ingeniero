"""CrewChiefV4 runtime loop — integra EventEngine, AudioPlayer, y Cartesian Spotter.

Llamado desde telemetry_sender_loop (WebSocket) a 10Hz (cada otro tick del loop de 20Hz).
Cubre los 4 issues medios de la auditoria:
  1. event_flags.reset_all() en transiciones de sesion
  2. audio_player.set_validator() cableado
  3. Cartesian spotter integrado
  4. EventEngine cableado al runtime
"""

import asyncio
import time
import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from src.services.lmu_reader import LMUReader
from src.services.frame_cache import FrameCache
from src.services.game_state_builder import build, populate_derived
from src.services.state_diff import StateDiff
from src.intelligence.event_engine import EventEngine
from src.intelligence.event_flags import event_flags
from src.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter
from src.intelligence.events.flags_monitor import FlagsMonitor
from src.intelligence.events.session_monitor import SessionMonitor
from src.intelligence.events.lap_counter import LapCounter
from src.intelligence.events.position import PositionEvent
from src.intelligence.events.conditions_monitor import ConditionsMonitor
from src.intelligence.events.frozen_order_monitor import FrozenOrderMonitor
from src.intelligence.events.pit_stops import PitStops
from src.intelligence.events.fuel import FuelEvent
from src.intelligence.events.battery import BatteryEvent
from src.intelligence.events.tyre_monitor import TyreMonitor
from src.intelligence.events.damage_reporting import DamageReporting
from src.intelligence.events.engine_monitor import EngineMonitor
from src.intelligence.events.multiclass_warnings import MulticlassWarnings
from src.intelligence.events.overtaking_aids_monitor import OvertakingAidsMonitor
from src.intelligence.events.opponents import Opponents
from src.intelligence.events.timings import Timings
from src.intelligence.events.driver_swaps import DriverSwaps
from src.intelligence.events.race_time import RaceTime
from src.intelligence.events.penalties import Penalties
from src.config.global_behaviour import global_settings
from src.config.settings import settings as app_settings

logger = logging.getLogger("vantare.crewchief")

# Frequency: 10Hz (every 100ms) — half of the 20Hz telemetry loop
CREWCHIEF_HZ = 10
CREWCHIEF_INTERVAL = 1.0 / CREWCHIEF_HZ

# Maximum empty frames before attempting shared-memory reinit
MAX_EMPTY_FRAMES = 50  # ~5 seconds at 10Hz


class CrewChiefRuntime:
    """Singleton runtime para el sistema CrewChiefV4.

    Encapsula todo el pipeline: lector shared memory → frame cache →
    game state builder → event engine → audio player.
    """

    def __init__(self, audio_player=None):
        self.reader = LMUReader()
        self.cache = FrameCache(self.reader)
        self.state_diff = StateDiff()
        self.spotter = NoisyCartesianCoordinateSpotter(
            ap=audio_player,
            repeat_freq=app_settings.SPOTTER_REPEAT_FREQUENCY,
            min_speed=app_settings.SPOTTER_MIN_SPEED,
            max_close=app_settings.SPOTTER_MAX_CLOSING_SPEED,
            clear_gap=app_settings.SPOTTER_GAP_FOR_CLEAR,
            clear_delay=app_settings.SPOTTER_CLEAR_DELAY / 1000.0,
            zone=getattr(app_settings, "SPOTTER_ZONE", 20.0),
        )
        self.engine = EventEngine(audio_player=audio_player)
        self.audio_player = audio_player

        # Wire audio player validator
        if self.audio_player:
            self.audio_player.set_validator(self._validate_message)

        # Register the 4 base events
        self.engine.register_event("flags_monitor", FlagsMonitor(ap=audio_player))
        self.engine.register_event("session_monitor", SessionMonitor(ap=audio_player))
        self.engine.register_event("lap_counter", LapCounter(ap=audio_player))
        self.engine.register_event("position", PositionEvent(ap=audio_player))
        self.engine.register_event("conditions_monitor", ConditionsMonitor(ap=audio_player))
        self.engine.register_event("frozen_order_monitor", FrozenOrderMonitor(ap=audio_player))
        self.engine.register_event("pit_stops", PitStops(ap=audio_player))
        self.engine.register_event("fuel", FuelEvent(ap=audio_player))
        self.engine.register_event("battery", BatteryEvent(ap=audio_player))
        self.engine.register_event("tyre_monitor", TyreMonitor(ap=audio_player))
        self.engine.register_event("damage_reporting", DamageReporting(ap=audio_player))
        self.engine.register_event("engine_monitor", EngineMonitor(ap=audio_player))
        self.engine.register_event("multiclass_warnings", MulticlassWarnings(ap=audio_player))
        self.engine.register_event("overtaking_aids_monitor", OvertakingAidsMonitor(ap=audio_player))
        self.engine.register_event("opponents", Opponents(ap=audio_player))
        self.engine.register_event("timings", Timings(ap=audio_player))
        self.engine.register_event("driver_swaps", DriverSwaps(ap=audio_player))
        self.engine.register_event("race_time", RaceTime(ap=audio_player))
        self.engine.register_event("penalties", Penalties(ap=audio_player))

        # State tracking
        self._prev_gsd: Optional[object] = None
        self._consecutive_empty: int = 0
        self._last_session_phase: int = -1
        self._last_session_type: int = -1
        self._tick_count: int = 0
        self._prev_fcy_active: bool = False
        self._spotter_fcy_exit_time: float = 0.0

        # Spotter FCY tracking
        self._prev_fcy_active: bool = False
        self._spotter_fcy_exit_time: float = 0.0

        # Thread pool for non-blocking GSD build
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="crewchief")

    def _validate_message(self, msg, gsd) -> bool:
        """Global validator callback for AudioPlayer.

        Delegates to the message's abstract_event.is_message_still_valid().
        """
        if gsd is None:
            return False
        if hasattr(msg, 'abstract_event') and msg.abstract_event:
            try:
                return msg.abstract_event.is_message_still_valid(
                    msg.name, gsd, msg.validation
                )
            except Exception as e:
                logger.error("Validator failed for '%s': %s", getattr(msg, 'name', '?'), e)
                return False
        return True  # No event attached → accept

    def detect_session_transition(self, flat: dict) -> bool:
        """Detect session restart (type or phase change to/from UNAVAILABLE)."""
        st = flat.get("session_type", -1)
        sp = flat.get("session_phase", -1)

        session_changed = (
            st != self._last_session_type and self._last_session_type >= 0
        )
        # New session: was unavailable, now available
        new_session = (
            self._last_session_phase in (0, -1) and sp > 0
        )

        # Abrupt end: was racing, now unavailable
        abrupt_end = (
            self._last_session_phase in (5, 6, 7) and sp == 0
        )

        self._last_session_type = st
        self._last_session_phase = sp

        return session_changed or new_session

    def handle_new_session(self):
        """Reset all state for a new session."""
        logger.info("New session detected — resetting CrewChief state")
        self.engine.clear_all_state()
        event_flags.reset_all()
        if self.audio_player:
            self.audio_player.purge_queues()
        self.spotter.clear_state()
        global_settings.complaints_count_in_this_session = 0
        self._prev_gsd = None
        self._consecutive_empty = 0

    def handle_abrupt_end(self):
        """Handle game crash / ALT+F4 — purge queues gracefully."""
        logger.info("Abrupt session end detected — purging queues")
        if self.audio_player:
            self.audio_player.purge_queues()
        self.engine.clear_all_state()

    async def tick(self) -> None:
        """Execute one CrewChiefV4 tick.

        Called from telemetry_sender_loop every other iteration (10Hz).
        """
        self._tick_count += 1

        try:
            # 1. Read ONE frame (shared memory + REST merge)
            flat = self.cache.read_full()

            # 2. Check frame validity
            if not flat.get("session_running_time", 0):
                self._consecutive_empty += 1
                if self._consecutive_empty >= MAX_EMPTY_FRAMES:
                    logger.warning("No data for %ds — attempting reinit", MAX_EMPTY_FRAMES // 10)
                    self.reader.reinitialize()
                    self._consecutive_empty = 0
                return
            self._consecutive_empty = 0

            # 3. Detect session transitions
            if self.detect_session_transition(flat):
                self.handle_new_session()

            # 4. Build GameStateData
            gsd = build(flat, self._prev_gsd)

            # 5. Detect state changes
            changes = self.state_diff.update(flat)

            # 6. Populate derived data (just_gone_green_time, etc.)
            populate_derived(gsd, changes, self._prev_gsd)

            # 7. Run Cartesian spotter (inline, same frame)
            if not event_flags.waiting_for_driver_is_ok_response:
                sf = self.cache.get_spotter_frame()
                fcy_now = sf["session_phase"] == 6  # FullCourseYellow
                fcy_enabled = getattr(
                    global_settings, "fcy_stop_spotter", True
                )

                fcy_entered = fcy_now and not self._prev_fcy_active
                fcy_exited = not fcy_now and self._prev_fcy_active
                self._prev_fcy_active = fcy_now

                if fcy_now and fcy_enabled:
                    # FCY activo + setting activado → suprimir spotter
                    if fcy_entered:
                        # Resetear estado al entrar para no acumular "still there"
                        self.spotter.clear_state()
                        self._spotter_fcy_exit_time = 0.0
                elif not fcy_now and self._spotter_fcy_exit_time > 0:
                    # Salida de FCY: comprobar si pasó el grace period
                    if time.time() >= self._spotter_fcy_exit_time:
                        self._spotter_fcy_exit_time = 0.0
                        self.spotter.trigger(sf, sf["rivals"], time.time())
                    # si no, seguir en pausa (no llamar a trigger)
                else:
                    # Operación normal (o FCY con setting desactivado)
                    self._spotter_fcy_exit_time = 0.0
                    self.spotter.trigger(sf, sf["rivals"], time.time())

            # 8. Dispatch events via EventEngine
            await self.engine.tick_async(self._prev_gsd, gsd)

            # 9. Process audio queue (validates against current GSD)
            if self.audio_player:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self._executor,
                    self.audio_player.process_queues,
                    time.time(),
                    gsd,
                )

            self._prev_gsd = gsd

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("CrewChief tick error: %s", e, exc_info=True)

    def close(self):
        """Clean up resources."""
        self._executor.shutdown(wait=False)
        if self.audio_player:
            self.audio_player.close()
        logger.info("CrewChiefRuntime closed")


# Singleton
_crewchief: Optional[CrewChiefRuntime] = None


def init_crewchief(audio_player=None) -> CrewChiefRuntime:
    """Initialize or return the existing CrewChief runtime singleton."""
    global _crewchief
    if _crewchief is None:
        _crewchief = CrewChiefRuntime(audio_player=audio_player)
        logger.info("CrewChiefV4 runtime initialized with 16 events")
    return _crewchief


def get_crewchief() -> Optional[CrewChiefRuntime]:
    """Return the existing CrewChief runtime, or None."""
    return _crewchief
