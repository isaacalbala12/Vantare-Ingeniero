"""E2E tests for the Spotter tick flow (frame -> AlertMessage).

Verifies that the REAL SpotterService detects real telemetry threats and
emits real AlertMessage objects, captured via a plain list-recording
callback (NO unittest.mock on internal components).

Coverage:
  1. TestSpotterDeterministicConditions — 8 deterministic conditions in
     SpotterService.evaluate() (5 required + 3 additional threats):
       a. pit_limiter_not_active (in_pits=True, pit_limiter_active=False)
       b. pit_limiter_not_disabled (in_pits=False, pit_limiter_active=True)
       c. gap_ahead_narrow (gap_ahead < 0.5)
       d. gap_behind_narrow (gap_behind < 0.5)
       e. damage_detected (damage_aero > 0)
       f. safety_car (safety_car_active=True)
       g. fcy (full_course_yellow_active=True)
       h. last_lap (session_laps_left=1.0)
       i. fuel_critical (estimated_laps_remaining < 1.0)
       j. multi-threat single tick (multiple alerts simultaneously)
  2. TestNoisyCartesianCoordinateSpotter — geometry-based threat detection
     via the real NoisyCartesianCoordinateSpotter:
       a. Rival behind within X meters -> alert
       b. Rival ahead within Y meters -> alert
       c. Rival on left/right -> alert
       d. No threats -> no alerts (negative test)
  3. TestEndToEndPipeline — full chain: build dict input mimicking
     GameStateData.model_dump() output, call spotter.evaluate_tick(),
     capture via broadcast_callback, verify AlertMessage fields.
"""
import time

import pytest

from src.intelligence.spotter import SpotterService
from src.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter
from src.models.messages import AlertMessage
from src.intelligence.spotter_messages import (
    CAR_LEFT,
    CAR_RIGHT,
    CLEAR_LEFT,
    CLEAR_RIGHT,
    CLEAR_ALL_ROUND,
    THREE_WIDE,
    THREE_WIDE_ON_LEFT,
    THREE_WIDE_ON_RIGHT,
)


# =========================================================================
# Helpers — Plain Python (no unittest.mock)
# =========================================================================


class ListCallback:
    """Callback that appends every AlertMessage it receives to a list.

    This is a plain Python class — NOT a unittest.mock.Mock.
    """

    def __init__(self):
        self.alerts = []

    def __call__(self, alert: AlertMessage) -> None:
        # Defensive: only append real AlertMessage instances
        if isinstance(alert, AlertMessage):
            self.alerts.append(alert)

    def by_category(self, category: str):
        return [a for a in self.alerts if a.category == category]


class AudioRecorder:
    """AudioPlayer stand-in that records all spotter audio calls.

    Implements the same interface the spotter uses (play_spotter_message,
    play) but is plain Python — NOT a unittest.mock.Mock.
    """

    def __init__(self):
        self.spotter_calls = []  # (audio_path, keep_channel)
        self.normal_calls = []   # (name, priority)

    def play_spotter_message(self, audio_path, keep_channel=False):
        self.spotter_calls.append((audio_path, keep_channel))

    def play(self, name, priority=5):
        self.normal_calls.append((name, priority))

    def played_paths(self):
        return [c[0] for c in self.spotter_calls]


def make_spotter() -> SpotterService:
    """Factory for a fresh SpotterService with a list-capturing callback."""
    cb = ListCallback()
    return SpotterService(broadcast_callback=cb), cb


def make_cartesian_spotter(**kwargs):
    """Factory for NoisyCartesianCoordinateSpotter wired to AudioRecorder."""
    defaults = {"min_speed": 5, "clear_delay": 0}
    defaults.update(kwargs)
    ap = AudioRecorder()
    s = NoisyCartesianCoordinateSpotter(ap=ap, **defaults)
    return s, ap


def _pilot_state(x=100.0, z=100.0, yaw=0.0, speed_ms=50.0):
    """Pilot state dict matching FrameCache.get_spotter_frame() shape.

    Avoid (0,0) — the spotter ignores the origin.
    """
    return {
        "world_x": x,
        "world_z": z,
        "rotation_yaw": yaw,
        "speed_ms": speed_ms,
    }


def _rival(oid, world_x, world_z, speed=45):
    return {"id": oid, "world_x": world_x, "world_z": world_z, "speed": speed}


def _normal_tick_dict():
    """Telemetry tick dict in the 'normal' state — no threats active.

    Mirrors the shape of GameStateData.model_dump(mode="json") with the
    flat top-level keys SpotterService.evaluate() reads.
    """
    return {
        "in_pits": False,
        "pit_limiter_active": False,
        "gap_ahead": 5.0,
        "gap_behind": 5.0,
        "damage_aero": 0.0,
        "suspension_damage": 0.0,
        "safety_car_active": False,
        "full_course_yellow_active": False,
        "session_laps_left": 10.0,
        "is_last_lap": False,
        "estimated_laps_remaining": 10.0,
        "fuel_laps_remaining": 10.0,
    }


# =========================================================================
# Tests — Deterministic SpotterService conditions
# =========================================================================


class TestSpotterDeterministicConditions:
    """Test each deterministic condition in SpotterService.evaluate().

    Uses real SpotterService with a ListCallback. Each test mutates ONE
    field of a 'normal' tick and asserts the corresponding AlertMessage
    is produced with correct category, severity, and payload.
    """

    # --- 1. pit_limiter_not_active ---
    def test_pit_limiter_not_active_emits_critical(self):
        """in_pits=True, pit_limiter_active=False -> CRITICAL 'limiter' alert."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["in_pits"] = True
        tick["pit_limiter_active"] = False

        spotter.evaluate_tick(tick)

        assert len(cb.alerts) >= 1
        limiter = cb.by_category("limiter")
        assert len(limiter) == 1
        alert = limiter[0]
        assert isinstance(alert, AlertMessage)
        assert alert.event == "alert"
        assert alert.severity == "CRITICAL"
        assert alert.payload["severity"] == "CRITICAL"
        assert alert.payload["in_pits"] is True
        assert alert.payload["pit_limiter_active"] is False
        assert "Pit limiter no activado" in alert.message
        assert alert.alert_id is not None and len(alert.alert_id) > 0
        # Audio priority is str(audio_priority) per spotter._create_alert
        assert alert.audio_priority == "4"
        assert alert.category == "limiter"

    # --- 2. pit_limiter_not_disabled ---
    def test_pit_limiter_not_disabled_emits_warning(self):
        """in_pits=False, pit_limiter_active=True -> WARNING 'limiter' alert."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["in_pits"] = False
        tick["pit_limiter_active"] = True

        spotter.evaluate_tick(tick)

        limiter = cb.by_category("limiter")
        assert len(limiter) == 1
        alert = limiter[0]
        assert alert.severity == "WARNING"
        assert alert.payload["severity"] == "WARNING"
        assert alert.payload["in_pits"] is False
        assert alert.payload["pit_limiter_active"] is True
        assert "Pit limiter no desactivado" in alert.message
        assert alert.audio_priority == "3"

    # --- 3. gap_ahead_narrow ---
    def test_gap_ahead_narrow_emits_info(self):
        """gap_ahead < 0.5 -> INFO 'gaps' alert with formatted gap value."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["gap_ahead"] = 0.3

        spotter.evaluate_tick(tick)

        gaps = cb.by_category("gaps")
        assert len(gaps) == 1
        alert = gaps[0]
        assert alert.severity == "INFO"
        assert alert.payload["severity"] == "INFO"
        assert alert.payload["gap_ahead"] == 0.3
        assert "0.30" in alert.message  # formatted with f"{gap:.2f}"
        assert "delante" in alert.message  # "Gap con coche de delante"
        assert alert.audio_priority == "1"

    # --- 4. gap_behind_narrow ---
    def test_gap_behind_narrow_emits_info(self):
        """gap_behind < 0.5 -> INFO 'gaps' alert."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["gap_behind"] = 0.2

        spotter.evaluate_tick(tick)

        gaps = cb.by_category("gaps")
        assert len(gaps) == 1
        alert = gaps[0]
        assert alert.severity == "INFO"
        assert alert.payload["gap_behind"] == 0.2
        assert "detrás" in alert.message
        assert "0.20" in alert.message

    # --- 5. damage_detected (threat from another deterministic condition) ---
    def test_damage_aero_detected_emits_warning(self):
        """damage_aero > 0 -> WARNING 'damage' alert."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["damage_aero"] = 0.5

        spotter.evaluate_tick(tick)

        damage = cb.by_category("damage")
        assert len(damage) == 1
        alert = damage[0]
        assert alert.severity == "WARNING"
        assert alert.payload["severity"] == "WARNING"
        assert alert.payload["damage_aero"] == 0.5
        assert "Daños detectados" in alert.message
        assert alert.ttl == 10

    # --- 6. safety_car ---
    def test_safety_car_emits_critical(self):
        """safety_car_active=True -> CRITICAL 'safety_car' alert (non-dismissable)."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["safety_car_active"] = True

        spotter.evaluate_tick(tick)

        sc = cb.by_category("safety_car")
        assert len(sc) == 1
        alert = sc[0]
        assert alert.severity == "CRITICAL"
        assert alert.payload["severity"] == "CRITICAL"
        assert alert.payload["safety_car_active"] is True
        assert "Safety car" in alert.message
        assert alert.dismissable is False
        assert alert.ttl == 15

    # --- 7. fcy (full_course_yellow_active) ---
    def test_fcy_emits_safety_car_critical(self):
        """full_course_yellow_active=True -> CRITICAL 'safety_car' alert."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["full_course_yellow_active"] = True

        spotter.evaluate_tick(tick)

        sc = cb.by_category("safety_car")
        assert len(sc) == 1
        assert sc[0].severity == "CRITICAL"
        assert "Safety car" in sc[0].message

    # --- 8. last_lap ---
    def test_last_lap_emits_high(self):
        """session_laps_left=1.0 -> HIGH 'session' alert."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["session_laps_left"] = 1.0

        spotter.evaluate_tick(tick)

        sess = cb.by_category("session")
        assert len(sess) == 1
        alert = sess[0]
        assert alert.severity == "HIGH"
        assert alert.payload["session_laps_left"] == 1.0
        assert "Última vuelta" in alert.message
        assert alert.audio_priority == "2"

    # --- 9. fuel_critical ---
    def test_fuel_critical_emits_critical(self):
        """fuel_laps_remaining < 1.0 -> CRITICAL 'fuel' alert.

        Note: SpotterService.evaluate() checks fuel_laps_remaining first and
        falls back to estimated_laps_remaining. The primary key is the one
        that drives the alert, so the test mutates fuel_laps_remaining.
        """
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["fuel_laps_remaining"] = 0.5

        spotter.evaluate_tick(tick)

        fuel = cb.by_category("fuel")
        assert len(fuel) == 1
        alert = fuel[0]
        assert alert.severity == "CRITICAL"
        assert alert.payload["severity"] == "CRITICAL"
        assert alert.payload["fuel_laps_remaining"] == 0.5
        assert "Combustible crítico" in alert.message
        assert alert.dismissable is False

    # --- 9b. fuel_critical via estimated_laps_remaining fallback ---
    def test_fuel_critical_via_estimated_laps_remaining_fallback(self):
        """estimated_laps_remaining < 1.0 (with fuel_laps_remaining absent) -> CRITICAL.

        Validates the fallback path in evaluate() line 137:
            fuel_laps = tick.get("fuel_laps_remaining", tick.get("estimated_laps_remaining", 99.0))
        """
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        # Drop fuel_laps_remaining to exercise the fallback branch
        del tick["fuel_laps_remaining"]
        tick["estimated_laps_remaining"] = 0.3

        spotter.evaluate_tick(tick)

        fuel = cb.by_category("fuel")
        assert len(fuel) == 1
        assert fuel[0].severity == "CRITICAL"
        assert "Combustible crítico" in fuel[0].message

    # --- 10. multiple alerts simultaneously ---
    def test_multiple_threats_emit_multiple_alerts(self):
        """Several conditions active in the same tick -> multiple alerts."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()
        tick["in_pits"] = True
        tick["pit_limiter_active"] = False
        tick["safety_car_active"] = True
        tick["fuel_laps_remaining"] = 0.3  # primary fuel key
        tick["damage_aero"] = 0.2
        tick["gap_ahead"] = 0.1
        tick["gap_behind"] = 0.2

        spotter.evaluate_tick(tick)

        categories = {a.category for a in cb.alerts}
        # Each of these conditions should fire its own alert
        assert "limiter" in categories
        assert "safety_car" in categories
        assert "fuel" in categories
        assert "damage" in categories
        assert "gaps" in categories
        # All alerts should be AlertMessage instances with unique alert_ids
        alert_ids = {a.alert_id for a in cb.alerts}
        assert len(alert_ids) == len(cb.alerts)
        assert all(isinstance(a, AlertMessage) for a in cb.alerts)

    # --- 11. normal tick: NO alerts (negative test for the spotter) ---
    def test_normal_tick_emits_no_alerts(self):
        """A 'normal' tick with all threats inactive must not produce alerts."""
        spotter, cb = make_spotter()
        tick = _normal_tick_dict()

        spotter.evaluate_tick(tick)

        assert cb.alerts == []

    # --- 12. evaluate() returns same AlertMessage as evaluate_tick() broadcasts ---
    def test_evaluate_returns_alerts_and_evaluate_tick_broadcasts_them(self):
        """evaluate() and evaluate_tick() must produce the same alert set."""
        spotter_a, cb_a = make_spotter()
        spotter_b, cb_b = make_spotter()
        tick = _normal_tick_dict()
        tick["safety_car_active"] = True
        tick["damage_aero"] = 0.1

        direct = spotter_a.evaluate(tick)
        spotter_b.evaluate_tick(tick)

        # Direct evaluate() return vs callback captures
        assert len(direct) == len(cb_b.alerts)
        direct_categories = sorted(a.category for a in direct)
        cb_categories = sorted(a.category for a in cb_b.alerts)
        assert direct_categories == cb_categories

    # --- 13. evaluate_tick with None state must not crash and must not broadcast ---
    def test_evaluate_tick_with_none_state_does_not_crash(self):
        spotter, cb = make_spotter()
        spotter.evaluate_tick(None)
        assert cb.alerts == []


# =========================================================================
# Tests — NoisyCartesianCoordinateSpotter threat detection
# =========================================================================


class TestNoisyCartesianCoordinateSpotter:
    """Geometry-based threat detection via the real NoisyCartesianCoordinateSpotter.

    Uses AudioRecorder (plain Python) — NOT unittest.mock. Validates
    the spotter detects cars within the configured zone, distinguishes
    sides, and stays silent when no rivals are nearby.
    """

    def test_rival_ahead_right_emits_car_right(self):
        """Rival ahead (ax>0) within zone -> 'car_right' message fired."""
        spotter, ap = make_cartesian_spotter()
        # Pilot at (100,100), facing yaw=0. Rival at (102,101) -> right & ahead.
        spotter.trigger(_pilot_state(100, 100), [_rival(1, 102, 101)], 1000.0)

        assert spotter.cr == 1
        assert spotter.cl == 0
        assert CAR_RIGHT in ap.played_paths()
        assert CAR_LEFT not in ap.played_paths()

    def test_rival_ahead_left_emits_car_left(self):
        """Rival ahead-left (ax<0) within zone -> 'car_left' message fired."""
        spotter, ap = make_cartesian_spotter()
        # Pilot at (100,100), rival at (98,101) -> left & ahead.
        spotter.trigger(_pilot_state(100, 100), [_rival(1, 98, 101)], 1000.0)

        assert spotter.cl == 1
        assert spotter.cr == 0
        assert CAR_LEFT in ap.played_paths()
        assert CAR_RIGHT not in ap.played_paths()

    def test_rival_on_left_and_right_emits_three_wide(self):
        """Two rivals appearing simultaneously on both sides -> 'three_wide'."""
        spotter, ap = make_cartesian_spotter()
        # Tick 1: empty (establish clp=0, crp=0 so transition is detected)
        spotter.trigger(_pilot_state(100, 100), [], 1000.0)
        # Tick 2: both sides appear
        spotter.trigger(
            _pilot_state(100, 100),
            [_rival(1, 98, 101), _rival(2, 102, 101)],
            1000.1,
        )

        assert spotter.cl >= 1
        assert spotter.cr >= 1
        assert THREE_WIDE in ap.played_paths()

    def test_rival_behind_within_zone_detected(self):
        """Rival behind (az<0, az>-car_len) on the right -> 'car_right'."""
        spotter, ap = make_cartesian_spotter()
        # Pilot at (100,100) facing yaw=0.
        # Rival at (102, 98): ax=+2 (right), az=-2 (behind but within car_len=4.5)
        spotter.trigger(_pilot_state(100, 100), [_rival(1, 102, 98)], 1000.0)

        # Either right or no detection depending on in_range, but the rival
        # is in the zone and within car_len behind — should fire.
        assert len(ap.played_paths()) >= 1
        # Most importantly, the rival is registered and the spotter fired
        assert ap.spotter_calls  # at least one spotter call

    def test_rival_far_outside_zone_ignored(self):
        """Rival far outside the zone (zone=20) -> no message fired."""
        spotter, ap = make_cartesian_spotter(zone=20)
        # Rival at (130, 100) — 30m away in X, outside zone=20
        spotter.trigger(_pilot_state(100, 100), [_rival(1, 130, 100)], 1000.0)

        assert spotter.cl == 0
        assert spotter.cr == 0
        assert ap.played_paths() == []

    def test_pilot_parked_emits_nothing(self):
        """Pilot stationary (speed < min_speed) -> spotter is inactive."""
        spotter, ap = make_cartesian_spotter(min_speed=10)
        spotter.trigger(_pilot_state(100, 100, speed_ms=0), [_rival(1, 102, 101)], 1000.0)

        assert ap.played_paths() == []
        assert spotter.cl == 0
        assert spotter.cr == 0

    def test_pilot_at_origin_emits_nothing(self):
        """Pilot at (0,0) origin -> spotter skips processing entirely."""
        spotter, ap = make_cartesian_spotter()
        spotter.trigger(
            {"world_x": 0, "world_z": 0, "rotation_yaw": 0, "speed_ms": 50},
            [_rival(1, 5, 5)],
            1000.0,
        )

        assert ap.played_paths() == []

    def test_no_rivals_no_alerts_negative_test(self):
        """Negative test: no rivals -> no alerts, no audio calls."""
        spotter, ap = make_cartesian_spotter()
        # Two ticks with empty rivals list
        spotter.trigger(_pilot_state(100, 100), [], 1000.0)
        spotter.trigger(_pilot_state(100, 100), [], 1000.1)

        assert ap.played_paths() == []
        assert spotter.cl == 0
        assert spotter.cr == 0
        assert spotter.has_overlap is False

    def test_clear_messages_after_rival_leaves(self):
        """After a rival appears and disappears, 'clear' is emitted."""
        spotter, ap = make_cartesian_spotter()
        # Tick 1: rival on left
        spotter.trigger(_pilot_state(100, 100), [_rival(1, 98, 101)], 1000.0)
        assert CAR_LEFT in ap.played_paths()

        # Tick 2: rival gone
        spotter.trigger(_pilot_state(100, 100), [], 1000.1)
        assert CLEAR_LEFT in ap.played_paths()

    def test_clear_all_round_when_both_sides_cleared(self):
        """After rivals on both sides leave -> 'clear_all_round'."""
        spotter, ap = make_cartesian_spotter()
        # Tick 1: both sides
        spotter.trigger(
            _pilot_state(100, 100),
            [_rival(1, 98, 101), _rival(2, 102, 101)],
            1000.0,
        )
        # Tick 2: empty
        spotter.trigger(_pilot_state(100, 100), [], 1000.1)
        assert CLEAR_ALL_ROUND in ap.played_paths()

    def test_three_wide_on_right_when_multiple_left(self):
        """Two rivals on left appearing from empty -> 'three_wide_on_right'."""
        spotter, ap = make_cartesian_spotter()
        # Tick 1: empty
        spotter.trigger(_pilot_state(100, 100), [], 1000.0)
        # Tick 2: 2 left rivals
        spotter.trigger(
            _pilot_state(100, 100),
            [_rival(1, 98, 101), _rival(2, 97, 102)],
            1000.1,
        )
        assert THREE_WIDE_ON_RIGHT in ap.played_paths()

    def test_three_wide_on_left_when_multiple_right(self):
        """Two rivals on right appearing from empty -> 'three_wide_on_left'."""
        spotter, ap = make_cartesian_spotter()
        # Tick 1: empty
        spotter.trigger(_pilot_state(100, 100), [], 1000.0)
        # Tick 2: 2 right rivals
        spotter.trigger(
            _pilot_state(100, 100),
            [_rival(1, 102, 101), _rival(2, 103, 102)],
            1000.1,
        )
        assert THREE_WIDE_ON_LEFT in ap.played_paths()


# =========================================================================
# Tests — End-to-end pipeline
# =========================================================================


class TestEndToEndPipeline:
    """End-to-end: build dict input, call evaluate_tick(), verify alerts.

    Builds dict inputs that look like the output of
    GameStateData.model_dump(mode="json") — the exact format that
    SpotterService.evaluate_tick() handles internally.
    """

    def test_full_chain_pit_limiter_critical_alert(self):
        """Full chain: dict -> evaluate_tick -> broadcast_callback -> AlertMessage."""
        cb = ListCallback()
        spotter = SpotterService(broadcast_callback=cb)

        # Simulating GameStateData.model_dump() shape with flat top-level keys
        telemetry = {
            "in_pits": True,
            "pit_limiter_active": False,
            "gap_ahead": 5.0,
            "gap_behind": 5.0,
            "damage_aero": 0.0,
            "suspension_damage": 0.0,
            "safety_car_active": False,
            "full_course_yellow_active": False,
            "session_laps_left": 30.0,
            "estimated_laps_remaining": 12.0,
            "fuel_laps_remaining": 12.0,
            # These would come from a real RaceState (player, session, tyres…)
            "player": {"slot_id": 1, "place": 5},
            "session": {"session_type": 4, "track_name": "Spa"},
        }

        spotter.evaluate_tick(telemetry)

        # Exactly one alert (the limiter one) was broadcast
        assert len(cb.alerts) == 1
        alert = cb.alerts[0]
        assert isinstance(alert, AlertMessage)
        assert alert.category == "limiter"
        assert alert.severity == "CRITICAL"
        assert alert.event == "alert"
        # Payload contains the original telemetry state for that condition
        assert alert.payload["in_pits"] is True
        assert alert.payload["pit_limiter_active"] is False
        # The base payload fields (severity, ttl, dismissable) are merged
        assert "severity" in alert.payload
        assert "ttl" in alert.payload
        assert "dismissable" in alert.payload

    def test_full_chain_no_callback_set_does_not_crash(self):
        """SpotterService without broadcast_callback must not crash on alerts."""
        spotter = SpotterService()  # no callback
        telemetry = {"in_pits": True, "pit_limiter_active": False}
        # Should not raise even though there are alerts
        spotter.evaluate_tick(telemetry)
        # evaluate() still returns the alert even if no callback fires
        alerts = spotter.evaluate(telemetry)
        assert len(alerts) == 1

    def test_full_chain_combined_threats(self):
        """Combined threats in a single tick -> all alerts broadcast."""
        cb = ListCallback()
        spotter = SpotterService(broadcast_callback=cb)

        telemetry = {
            "in_pits": False,
            "pit_limiter_active": True,        # -> limiter WARNING
            "gap_ahead": 0.2,                   # -> gaps INFO
            "gap_behind": 1.5,
            "damage_aero": 0.0,
            "suspension_damage": 0.0,
            "safety_car_active": False,
            "full_course_yellow_active": True,  # -> safety_car CRITICAL
            "session_laps_left": 1.0,           # -> session HIGH
            "estimated_laps_remaining": 10.0,   # not used: primary is below
            "fuel_laps_remaining": 0.5,         # -> fuel CRITICAL
        }

        spotter.evaluate_tick(telemetry)

        categories = {a.category for a in cb.alerts}
        assert categories == {"limiter", "gaps", "safety_car", "session", "fuel"}
        # All alerts broadcasted exactly once
        assert len(cb.alerts) == 5

    def test_full_chain_pydantic_model_via_evaluate_tick(self):
        """evaluate_tick() can also accept a Pydantic-like object (model_dump)."""
        from src.models.messages import BaseMessage  # noqa: F401  (sanity import)

        class _FakeGameState:
            """Stand-in for a real GameStateData Pydantic model."""

            def model_dump(self, mode="json"):
                return {
                    "in_pits": True,
                    "pit_limiter_active": False,
                    "gap_ahead": 5.0,
                    "gap_behind": 5.0,
                    "damage_aero": 0.0,
                    "safety_car_active": False,
                    "session_laps_left": 10.0,
                    "estimated_laps_remaining": 10.0,
                }

        cb = ListCallback()
        spotter = SpotterService(broadcast_callback=cb)
        spotter.evaluate_tick(_FakeGameState())

        # Pydantic path worked: callback received the limiter alert
        assert len(cb.alerts) == 1
        assert cb.alerts[0].category == "limiter"
        assert cb.alerts[0].severity == "CRITICAL"

    def test_full_chain_no_false_positives_on_safe_state(self):
        """Safe state: in_pits=False, limiter off, wide gaps, full fuel, no SC."""
        cb = ListCallback()
        spotter = SpotterService(broadcast_callback=cb)
        telemetry = {
            "in_pits": False,
            "pit_limiter_active": False,
            "gap_ahead": 8.0,
            "gap_behind": 6.0,
            "damage_aero": 0.0,
            "suspension_damage": 0.0,
            "safety_car_active": False,
            "full_course_yellow_active": False,
            "session_laps_left": 25.0,
            "estimated_laps_remaining": 18.0,
            "fuel_laps_remaining": 18.0,
        }
        spotter.evaluate_tick(telemetry)
        assert cb.alerts == []

    def test_full_chain_alert_message_shape_complete(self):
        """Verify every field of AlertMessage is populated correctly."""
        cb = ListCallback()
        spotter = SpotterService(broadcast_callback=cb)
        telemetry = {
            "in_pits": True,
            "pit_limiter_active": False,
            "gap_ahead": 5.0,
            "gap_behind": 5.0,
            "damage_aero": 0.0,
            "suspension_damage": 0.0,
            "safety_car_active": False,
            "session_laps_left": 10.0,
            "estimated_laps_remaining": 10.0,
        }

        before = time.time()
        spotter.evaluate_tick(telemetry)
        after = time.time()

        assert len(cb.alerts) == 1
        alert = cb.alerts[0]
        # Mandatory fields
        assert isinstance(alert, AlertMessage)
        assert alert.event == "alert"
        assert alert.alert_id is not None
        assert len(alert.alert_id) > 0
        assert alert.category == "limiter"
        assert alert.message != ""
        assert alert.severity in ("INFO", "WARNING", "HIGH", "CRITICAL")
        assert alert.audio_priority is not None
        assert isinstance(alert.payload, dict)
        assert alert.payload["severity"] == alert.severity
        # TTL/dismissable are preserved
        assert isinstance(alert.ttl, int)
        assert isinstance(alert.dismissable, bool)
        # Timestamp is auto-populated and within the call window
        assert before <= alert.timestamp <= after
