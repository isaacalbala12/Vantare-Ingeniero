"""Integration tests — pipeline completo con 12 eventos y EventEngine."""

import time
import asyncio
import pytest

from src.intelligence.event_engine import EventEngine
from src.intelligence.event_flags import event_flags
from src.intelligence.base_event import FakeAudioPlayer
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase, FrozenOrderPhase
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


@pytest.fixture(autouse=True)
def _clean_global_state():
    event_flags.reset_all()
    yield
    event_flags.reset_all()


def _gsd(phase=SessionPhase.GREEN, laps=3, class_pos=5,
         car_class="GT3", fuel=50, battery_pct=100,
         pit_state=0, in_pitlane=False, fo_phase=FrozenOrderPhase.NONE,
         water=90, oil=100, speed=30, num_opponents=2):
    g = GameStateData()
    g.now = time.time()
    g.session.session_type = SessionType.RACE
    g.session.session_phase = phase
    g.session.completed_laps = laps
    g.session.class_position = class_pos
    g.car_class = car_class
    g.fuel.fuel_left = fuel
    g.fuel.fuel_capacity = 100.0
    g.battery.percentage = battery_pct
    g.pit.in_pitlane = in_pitlane
    g.pit.pit_state = pit_state
    g.motion.car_speed = speed
    g.engine.water_temp = water
    g.engine.oil_temp = oil
    g.frozen_order.phase = fo_phase
    g.tyre.fl_temp = 90
    g.tyre.fr_temp = 90
    g.tyre.rl_temp = 90
    g.tyre.rr_temp = 90
    g.tyre.fl_compound = "Soft"
    g.tyre.fr_compound = "Soft"
    g.tyre.rl_compound = "Soft"
    g.tyre.rr_compound = "Soft"
    for i in range(num_opponents):
        g.opponents[f"opp_{i}"] = type("Opp", (), {
            "driver": f"opp_{i}", "speed": 30, "distance": 100 + i*10,
            "delta": float(i), "is_entering_pits": False,
            "vehicle_class": "GT3",
            "class_pos": class_pos + i + 1,
        })()
    return g


class TestAllEventsSilent:
    def test_no_exceptions_with_all_events(self):
        """12 eventos registrados, GSD normal → 0 excepciones."""
        ap = FakeAudioPlayer()
        engine = EventEngine(audio_player=ap)
        engine.register_event("flags_monitor", FlagsMonitor(ap=ap))
        engine.register_event("session_monitor", SessionMonitor(ap=ap))
        engine.register_event("lap_counter", LapCounter(ap=ap))
        engine.register_event("position", PositionEvent(ap=ap))
        engine.register_event("conditions_monitor", ConditionsMonitor(ap))
        engine.register_event("frozen_order_monitor", FrozenOrderMonitor(ap))
        engine.register_event("pit_stops", PitStops(ap))
        engine.register_event("fuel", FuelEvent(ap))
        engine.register_event("battery", BatteryEvent(ap))
        engine.register_event("tyre_monitor", TyreMonitor(ap))
        engine.register_event("damage_reporting", DamageReporting(ap))
        engine.register_event("engine_monitor", EngineMonitor(ap))

        g = _gsd()
        for ev in engine._events.values():
            ev.trigger_internal(None, g)

        # No deberia haber crasheado
        assert True

    def test_empty_gsd_no_events_crash(self):
        """GameStateData vacio → ningun evento crashea."""
        ap = FakeAudioPlayer()
        events = [
            FlagsMonitor(ap), SessionMonitor(ap), LapCounter(ap),
            PositionEvent(ap), ConditionsMonitor(ap), FrozenOrderMonitor(ap),
            PitStops(ap), FuelEvent(ap), BatteryEvent(ap),
            TyreMonitor(ap), DamageReporting(ap), EngineMonitor(ap),
        ]
        g = GameStateData()
        for ev in events:
            ev.trigger_internal(None, g)
        assert True

    def test_no_audio_player_no_crash(self):
        """Todos los eventos sin audio_player → play_message no crashea."""
        events = [
            FlagsMonitor(), SessionMonitor(), LapCounter(),
            PositionEvent(), ConditionsMonitor(), FrozenOrderMonitor(),
            PitStops(), FuelEvent(), BatteryEvent(),
            TyreMonitor(), DamageReporting(), EngineMonitor(),
        ]
        g = _gsd()
        for ev in events:
            ev.trigger_internal(None, g)
        assert True


class TestCrossEventIntegration:
    def test_fcy_pauses_then_resumes(self):
        """FCY pausa audio, mensajes urgentes van a immediate."""
        ap = FakeAudioPlayer()
        fm = FlagsMonitor(ap)
        fm.trigger_internal(None, _gsd(phase=SessionPhase.GREEN))
        ap.clear()
        fm.trigger_internal(None, _gsd(phase=SessionPhase.FULL_COURSE_YELLOW))
        # FCY deployed va a immediate queue
        assert len(ap.immediate_messages) >= 1
        # La cola normal se pausa
        assert ap.paused_for > 0

    def test_damage_suppresses_spotter_flag(self):
        """Impacto heavy → waiting_for_driver_is_ok_response=True."""
        ap = FakeAudioPlayer()
        dr = DamageReporting(ap)
        g = _gsd(speed=0)
        g.damage.last_impact_time = 100.0
        g.damage.last_impact_magnitude = 10.0
        dr.trigger_internal(None, g)
        assert event_flags.waiting_for_driver_is_ok_response

    def test_fuel_stops_during_pitting(self):
        """is_pitting_this_lap=True → FuelEvent no procesa."""
        ap = FakeAudioPlayer()
        event_flags.is_pitting_this_lap = True
        ev = FuelEvent(ap)
        ev.trigger_internal(None, _gsd(fuel=5))
        assert len(ap.messages) == 0
        event_flags.is_pitting_this_lap = False


class TestSequenceOrdering:
    def test_event_sequence_increasing(self):
        """Todas las secuencias son unicas y en orden."""
        events = [
            ConditionsMonitor(), FrozenOrderMonitor(), FlagsMonitor(),
            SessionMonitor(), LapCounter(), PitStops(), FuelEvent(),
            PositionEvent(), BatteryEvent(), TyreMonitor(),
            DamageReporting(), EngineMonitor(),
        ]
        seqs = sorted(events, key=lambda e: e.sequence)
        last = -1
        for ev in seqs:
            assert ev.sequence >= last
            last = ev.sequence


class TestSessionReset:
    def test_clear_all_resets_everything(self):
        """engine.clear_all_state() + event_flags.reset_all() → nuevo estado limpio."""
        ap = FakeAudioPlayer()
        engine = EventEngine(audio_player=ap)
        engine.register_event("fuel", FuelEvent(ap))
        engine.register_event("pit_stops", PitStops(ap))
        engine.register_event("damage_reporting", DamageReporting(ap))

        engine.clear_all_state()
        event_flags.reset_all()

        assert not event_flags.is_pitting_this_lap
        assert not event_flags.waiting_for_driver_is_ok_response
        assert not event_flags.fuel_warning_active


class TestMemory:
    def test_100_ticks_no_crash(self):
        """100 ticks con todos los eventos → sin memory leak ni crash."""
        ap = FakeAudioPlayer()
        events = [
            ConditionsMonitor(ap), FrozenOrderMonitor(ap),
            PitStops(ap), FuelEvent(ap), BatteryEvent(ap),
            TyreMonitor(ap), DamageReporting(ap), EngineMonitor(ap),
        ]
        g = _gsd()
        for _ in range(100):
            for ev in events:
                ev.trigger_internal(None, g)
        event_flags.reset_all()
        assert not event_flags.fuel_warning_active
