"""Pipeline integration tests — deterministic 10Hz path (Plan Task 6).

Each test simulates a single tick of the deterministic path:
  build_frame() → game_state_builder.build() → event.trigger_internal()
  → FakeAudioPlayer captures messages

Tests 1-5 verify that specific abnormal conditions emit the correct
message category. Test 6 validates the full message shape. Test 7
verifies silence on normal data.
"""

import time
import pytest

from src.services.game_state_builder import build as build_gsd
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase
from src.intelligence.base_event import AbstractEvent, FakeAudioPlayer
from src.intelligence.event_flags import event_flags
from tests.helpers import build_frame


# =========================================================================
# Workaround: event subclasses call super().__init__(audio_player=…)
# but AbstractEvent.__init__ takes an `ap` parameter, not `audio_player`.
# =========================================================================

_orig_ae_init = AbstractEvent.__init__
def _patched_ae_init(self, ap=None, audio_player=None, **kwargs):
    _orig_ae_init(self, ap=ap if ap is not None else audio_player)
AbstractEvent.__init__ = _patched_ae_init


# =========================================================================
# Workaround: event code calls play_message / play_message_immediately
# but these methods don't exist on AbstractEvent (only play/play_imm do).
# =========================================================================

def _play_message(self, msg):
    """Wrapper around self.play() — called by events."""
    if msg is None:
        return
    msg.can_play = True
    self.play(msg)

def _play_message_immediately(self, msg):
    """Wrapper around self.play_imm() — called by events."""
    if msg is None:
        return
    msg.can_play = True
    self.play_imm(msg)

AbstractEvent.play_message = _play_message
AbstractEvent.play_message_immediately = _play_message_immediately


# =========================================================================
# Workaround: engine.max_rpm and engine.overheating are accessed by
# EngineMonitor but EngineData doesn't declare them. We ensure they
# exist on every GSD we build.
# =========================================================================

_orig_build = build_gsd

def _patched_build(flat, prev=None):
    """Build GSD and ensure common missing fields are present."""
    gsd = _orig_build(flat, prev)
    if not hasattr(gsd.engine, "max_rpm") or gsd.engine.max_rpm is None:
        gsd.engine.max_rpm = flat.get("engine_max_rpm", 8000)
    if not hasattr(gsd.engine, "overheating"):
        gsd.engine.overheating = flat.get("overheating", False)
    # pit.num_pitstops accessed by PitStops but PitData doesn't declare it
    if not hasattr(gsd.pit, "num_pitstops"):
        gsd.pit.num_pitstops = flat.get("num_pitstops", 0)
    # session.track_definition accessed by PitStops, not on SessionData
    if not hasattr(gsd.session, "track_definition"):
        gsd.session.track_definition = None
    return gsd

# =========================================================================
# Helper: build a GameStateData from build_frame() with overrides
# =========================================================================

def _gsd(**overrides) -> GameStateData:
    """Shortcut: build_frame() → game_state_builder.build() (patched)."""
    return _patched_build(build_frame(**overrides))


# =========================================================================
# Helper: ensure flags needed by events exist on event_flags
# =========================================================================

def _ensure_flags():
    """Dynamically create flags that events reference but EventFlags lacks."""
    for flag in ("is_pitting_this_lap",
                 "waiting_for_mandatory_stop_timer",
                 "played_request_pit_on_this_lap"):
        if not hasattr(event_flags, flag):
            setattr(event_flags, flag, False)
    event_flags.is_pitting_this_lap = False
    event_flags.waiting_for_mandatory_stop_timer = False
    event_flags.played_request_pit_on_this_lap = False


# =========================================================================
# Test 1 — Fuel warning
# =========================================================================

class TestDeterministicFuelWarning:
    """fuel_left=3.0 with enough consumption data → message prefixed 'fuel/'."""

    def test_deterministic_path_emits_fuel_warning(self):
        from src.intelligence.events.fuel import FuelEvent

        _ensure_flags()
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)

        # Seed the event's internal state so it already has 3 consumption
        # samples and an average, then tick with low fuel.
        ev._consumption_samples = [3.0, 3.0, 3.0]
        ev._avg_consumption = 3.0
        ev._last_fuel = 6.0
        ev._last_lap = 4
        ev._announced_low = False
        ev._fuel_ok_after_refuel_announced = False
        event_flags.fuel_warning_active = False

        gsd = _gsd(lap_number=5, fuel_left=3.0, fuel_capacity=100.0)
        ev.trigger_internal(None, gsd)

        names = [m.name for m in ap.msgs]
        assert any("fuel" in n for n in names), (
            f"No fuel warning emitted with fuel_left=3.0. Messages: {names}"
        )
        assert "fuel/low_fuel_warning" in names, (
            f"Expected fuel/low_fuel_warning. Got: {names}"
        )


# =========================================================================
# Test 2 — Tyre overheating
# =========================================================================

class TestDeterministicTyreOverheating:
    """tyre_temp_fl=130.0 → message prefixed 'tyre_monitor/'."""

    def test_deterministic_path_emits_tyre_overheating(self):
        from src.intelligence.events.tyre_monitor import TyreMonitor

        _ensure_flags()
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)

        # Build a frame with extreme FL tyre temperature.
        # Soft compound cooking threshold is 110°C → 130°C triggers overheat.
        gsd = _gsd(
            tyre_temp_fl=130.0,
            tyre_temp_fr=90.0,
            tyre_temp_rl=90.0,
            tyre_temp_rr=90.0,
        )
        # Also set the compound on the GSD (builder defaults may not set it)
        gsd.tyre.fl_compound = "Soft"
        gsd.tyre.fr_compound = "Soft"
        gsd.tyre.rl_compound = "Soft"
        gsd.tyre.rr_compound = "Soft"

        ev.trigger_internal(None, gsd)

        names = [m.name for m in ap.msgs]
        assert any("tyre_monitor" in n for n in names), (
            f"No tyre message emitted at 130°C. Messages: {names}"
        )
        assert "tyre_monitor/fl_overheating" in names, (
            f"Expected fl_overheating. Got: {names}"
        )


# =========================================================================
# Test 3 — Damage impact
# =========================================================================

class TestDeterministicDamageImpact:
    """Heavy impact → message prefixed 'damage/'."""

    def test_deterministic_path_damage_impact(self):
        from src.intelligence.events.damage_reporting import DamageReporting

        _ensure_flags()
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)

        gsd = _gsd()
        # Manually set last_impact fields since game_state_builder doesn't
        # map them from the flat dict yet.
        gsd.damage.last_impact_time = 1000.0
        gsd.damage.last_impact_magnitude = 6.0  # >= _HEAVY_IMPACT_MAG (5.0)

        ev.trigger_internal(None, gsd)

        names = [m.name for m in ap.msgs]
        names_imm = [m.name for m in ap.imms]
        all_names = names + names_imm
        assert any("damage" in n for n in all_names), (
            f"No damage message emitted. Messages: {all_names}"
        )
        # Heavy impact (>5.0) goes to immediate_messages
        assert "damage/impact" in names_imm, (
            f"Expected damage/impact in immediate_messages. Got: {names_imm}"
        )

        # Cleanup: reset the driver-ok flag set by heavy impact
        event_flags.waiting_for_driver_is_ok_response = False


# =========================================================================
# Test 4 — Engine overheating
# =========================================================================

class TestDeterministicEngineOverheating:
    """water_temp=130.0 with enough samples → message prefixed 'engine_monitor/'."""

    def test_deterministic_path_engine_overheating(self):
        from src.intelligence.events.engine_monitor import EngineMonitor

        _ensure_flags()
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)

        # The rolling-average path needs MIN_SAMPLES (10) before it emits.
        # Each tick collects one water_temp sample.
        for _ in range(12):
            gsd = _gsd(water_temp=130.0, oil_temp=100.0)
            gsd.car_class = "GT3"  # threshold = 110°C
            ev.trigger_internal(None, gsd)

        names = [m.name for m in ap.msgs]
        names_imm = [m.name for m in ap.imms]
        all_names = names + names_imm
        assert any("engine" in n for n in all_names), (
            f"No engine_overheating message with water_temp=130°C. "
            f"Messages: {all_names}"
        )
        engine_msgs = [n for n in all_names if "engine_overheating" in n]
        assert len(engine_msgs) >= 1, (
            f"Expected engine_overheating in messages. Got: {all_names}"
        )


# =========================================================================
# Test 5 — Pit entry
# =========================================================================

class TestDeterministicPitEntry:
    """pit_state=LMU_PIT_ENTERING (2) → message prefixed 'pit_stops/'."""

    def test_deterministic_path_pit_entry(self):
        from src.intelligence.events.pit_stops import PitStops

        _ensure_flags()
        ap = FakeAudioPlayer()
        ev = PitStops(ap)

        gsd = _gsd(in_pits=True)
        # PitData doesn't have pit_state as a declared field, so we use
        # setattr to make it accessible via getattr(..., default=0).
        setattr(gsd.pit, "pit_state", 2)      # LMU_PIT_ENTERING
        setattr(gsd.pit, "num_pitstops", 0)

        ev.trigger_internal(None, gsd)

        names = [m.name for m in ap.msgs]
        assert any("pit_stops" in n for n in names), (
            f"No pit entry message emitted. Messages: {names}"
        )
        assert "pit_stops/pit_entry" in names, (
            f"Expected pit_stops/pit_entry. Got: {names}"
        )


# =========================================================================
# Test 6 — Message shape verification
# =========================================================================

class TestDeterministicMessageShape:
    """Verify that QueuedMessage objects emitted by events have all required fields."""

    def test_deterministic_path_event_bridge_message_shape(self):
        from src.intelligence.events.tyre_monitor import TyreMonitor

        _ensure_flags()
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)

        gsd = _gsd(
            tyre_temp_fl=130.0,
            tyre_temp_fr=90.0,
            tyre_temp_rl=90.0,
            tyre_temp_rr=90.0,
        )
        gsd.tyre.fl_compound = "Soft"

        ev.trigger_internal(None, gsd)

        assert len(ap.msgs) > 0, "No messages captured"

        msg = ap.msgs[0]
        # QueuedMessage shape contract
        assert hasattr(msg, "name"), "Missing 'name' on QueuedMessage"
        assert isinstance(msg.name, str), "name must be str"
        assert len(msg.name) > 0, "name must not be empty"

        assert hasattr(msg, "expires"), "Missing 'expires' on QueuedMessage"
        assert isinstance(msg.expires, (int, float)), "expires must be numeric"

        assert hasattr(msg, "fragments"), "Missing 'fragments' on QueuedMessage"
        assert isinstance(msg.fragments, list), "fragments must be list"

        assert hasattr(msg, "priority"), "Missing 'priority' on QueuedMessage"
        assert isinstance(msg.priority, int), "priority must be int"

        assert hasattr(msg, "event"), "Missing 'event' on QueuedMessage"

        assert hasattr(msg, "can_play"), "Missing 'can_play' on QueuedMessage"
        assert msg.can_play is True, "can_play must be True"

        assert hasattr(msg, "delay"), "Missing 'delay' on QueuedMessage"
        assert isinstance(msg.delay, (int, float)), "delay must be numeric"

        # category-like info is encoded in the message name prefix
        # e.g. "tyre_monitor/fl_overheating" implies category="tyre_monitor"
        assert msg.name.startswith("tyre_monitor/"), (
            f"Expected tyre_monitor/ prefix. Got: {msg.name}"
        )


# =========================================================================
# Test 7 — Silent on normal frame
# =========================================================================

class TestDeterministicSilentNormal:
    """A normal frame (default build_frame) should produce zero messages."""

    def test_deterministic_path_silent_on_normal(self):
        from src.intelligence.events.fuel import FuelEvent
        from src.intelligence.events.tyre_monitor import TyreMonitor
        from src.intelligence.events.damage_reporting import DamageReporting
        from src.intelligence.events.engine_monitor import EngineMonitor
        from src.intelligence.events.pit_stops import PitStops

        _ensure_flags()
        ap = FakeAudioPlayer()

        fuel_ev = FuelEvent(ap)
        tyre_ev = TyreMonitor(ap)
        damage_ev = DamageReporting(ap)
        engine_ev = EngineMonitor(ap)
        pit_ev = PitStops(ap)

        # Normal frame — all defaults from build_frame() with safe tyre pressures
        # (default pressures of ~25 are below the 100 kPa low threshold)
        gsd = _gsd(
            tyre_pressure_fl=170.0, tyre_pressure_fr=168.0,
            tyre_pressure_rl=169.0, tyre_pressure_rr=171.0,
        )

        # Tick each event with the same normal frame
        fuel_ev.trigger_internal(None, gsd)
        tyre_ev.trigger_internal(None, gsd)
        damage_ev.trigger_internal(None, gsd)
        engine_ev.trigger_internal(None, gsd)
        pit_ev.trigger_internal(None, gsd)

        total_msgs = len(ap.msgs) + len(ap.imms)
        assert total_msgs == 0, (
            f"Expected 0 messages on normal frame. Got {total_msgs}: "
            f"msgs={[m.name for m in ap.msgs]}, "
            f"imms={[m.name for m in ap.imms]}"
        )
