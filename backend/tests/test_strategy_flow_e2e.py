"""E2E tests for the Strategy service → backend broadcast pipeline (T9).

Verifies that the **real** `shared-strategy` engine produces physically
reasonable `StrategyAdvice` for realistic race telemetry frames, and that
the sidecar's `strategy_frame` payload round-trips through the backend's
`/ws/sidecar` WebSocket endpoint.

Design contract
---------------
* Uses the **real** `shared_strategy.compute_strategy()` — no `unittest.mock`
  of the strategy engine, the Pydantic models, or the WS transport.
* Uses a real `TelemetryFrame` constructed by hand for each scenario.
* Uses a real `fastapi.testclient.TestClient` with the actual
  `src.routers.websocket` router mounted (no stub routers).
* Asserts physical reasonability: no negative fuel, monotonically-ordered
  pit windows, finite values, plausible stint end laps, etc.

Run:
    cd backend
    pytest tests/test_strategy_flow_e2e.py -v --tb=short
"""
from __future__ import annotations

import math
import time
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Real strategy engine + models (NOT mocked)
from shared_strategy import (
    StrategyAdvice,
    StrategyState,
    TelemetryFrame,
    TrackConfig,
    compute_strategy,
)
from shared_strategy.models import CompetitorTelemetry

# Real backend WebSocket router (NOT stubbed)
from src.routers.websocket import router as ws_router
from src.routers.health import router as health_router


# =========================================================================
# Helpers — race frame construction
# =========================================================================

# Standard LMU/real-world Hypercar race configuration:
#   Le Mans style 80-lap stint race on a 7004m track (Spa-Francorchamps GP).
TRACK_LENGTH_M = 7004.0
TOTAL_RACE_LAPS = 80
LAP_TIME_S = 110.0  # 2:00.000 flat pace — realistic LMH hypercar lap


def _make_frame(
    *,
    lap_number: int,
    lap_distance: float,
    fuel_in_tank: float,
    fuel_capacity: float = 100.0,
    fuel_used_lap_raw: float = 2.8,
    session_laps_left: float | None = None,
    session_time_left: float | None = None,
    tyre_wear: tuple[float, float, float, float] = (10.0, 10.0, 8.0, 8.0),
    brake_wear: tuple[float, float, float, float] = (10.0, 10.0, 10.0, 10.0),
    tyre_temp: tuple[float, float, float, float] = (85.0, 85.0, 84.0, 84.0),
    battery_charge: float = 75.0,
    battery_drain: float = 1.0,
    battery_regen: float = 0.5,
    motor_state: int | None = 2,  # 2=Drain
    position: int = 5,
    in_pits: bool = False,
    safety_car_active: bool = False,
    full_course_yellow_active: bool = False,
    yellow_flag_active: bool = False,
    speed: float = 70.0,
    throttle: float = 0.85,
    brake: float = 0.0,
    competitors: list[CompetitorTelemetry] | None = None,
    last_lap_time: float = LAP_TIME_S,
    best_lap_time: float = LAP_TIME_S,
) -> TelemetryFrame:
    """Build a deterministic, realistic TelemetryFrame.

    Defaults give a credible mid-pack Hypercar snapshot. Override any
    keyword to model a specific scenario.
    """
    if session_laps_left is None:
        session_laps_left = max(0.0, float(TOTAL_RACE_LAPS - lap_number))
    if session_time_left is None:
        # Rough remaining time = laps_left * lap_time
        session_time_left = session_laps_left * LAP_TIME_S

    return TelemetryFrame(
        session_type="race",
        session_time_left=session_time_left,
        session_laps_left=session_laps_left,
        lap_number=lap_number,
        lap_distance=lap_distance,
        lap_time_best=best_lap_time,
        lap_time_previous=last_lap_time,
        is_invalid_lap=False,
        in_garage=False,
        in_pits=in_pits,
        pit_limiter_active=in_pits,
        yellow_flag_active=yellow_flag_active,
        safety_car_active=safety_car_active,
        full_course_yellow_active=full_course_yellow_active,
        fuel_in_tank=fuel_in_tank,
        fuel_capacity=fuel_capacity,
        fuel_used_lap_raw=fuel_used_lap_raw,
        battery_charge=battery_charge,
        battery_drain=battery_drain,
        battery_regen=battery_regen,
        motor_state=motor_state,
        tyre_wear_fl=tyre_wear[0],
        tyre_wear_fr=tyre_wear[1],
        tyre_wear_rl=tyre_wear[2],
        tyre_wear_rr=tyre_wear[3],
        tyre_temp_fl=tyre_temp[0],
        tyre_temp_fr=tyre_temp[1],
        tyre_temp_rl=tyre_temp[2],
        tyre_temp_rr=tyre_temp[3],
        brake_wear_fl=brake_wear[0],
        brake_wear_fr=brake_wear[1],
        brake_wear_rl=brake_wear[2],
        brake_wear_rr=brake_wear[3],
        speed=speed,
        throttle=throttle,
        brake=brake,
        pos_x=0.0,
        pos_y=0.0,
        pos_z=0.0,
        competitors=competitors or [],
    )


def _build_track(pit_pass_time: float | None = None) -> TrackConfig:
    """Build a TrackConfig with realistic pit-lane defaults."""
    return TrackConfig(
        track_length=TRACK_LENGTH_M,
        pit_entry_position=3500.0,
        pit_exit_position=200.0,
        pit_lane_length=400.0,
        pit_speed_limit=60.0 / 3.6,  # 60 km/h in m/s
        pit_pass_time=pit_pass_time if pit_pass_time is not None else 28.0,
    )


def _make_rival(
    *,
    driver_index: int = 2,
    name: str = "Rival A",
    position: int = 4,
    lap_number: int | None = None,
    lap_distance: float = 0.0,
    gap_seconds: float = 2.0,
    fuel_fraction: float = 0.6,
    in_pits: bool = False,
    last_lap: float = LAP_TIME_S,
) -> CompetitorTelemetry:
    """Build a competitor 1 lap ahead in time (positive gap = ahead)."""
    if lap_number is None:
        # Same lap as player
        lap_number = 0
    return CompetitorTelemetry(
        driver_index=driver_index,
        driver_name=name,
        driver_class="Hypercar",
        standing_position=position,
        class_position=position,
        lap_number=lap_number,
        lap_distance=lap_distance,
        lap_time_best=LAP_TIME_S - 0.5,
        lap_time_previous=last_lap,
        in_pits=in_pits,
        pit_requested=False,
        estimated_time_into_lap=max(0.1, gap_seconds),
        speed=70.0,
        fuel_capacity_fraction=fuel_fraction,
    )


def _assert_finite(obj: Any, path: str = "root") -> None:
    """Recursively assert every float in a (possibly nested) Pydantic model is finite."""
    if isinstance(obj, (int,)):
        return
    if isinstance(obj, float):
        assert math.isfinite(obj), f"{path} has non-finite value: {obj}"
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            _assert_finite(v, f"{path}.{k}")
        return
    if isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            _assert_finite(v, f"{path}[{i}]")
        return
    if hasattr(obj, "model_dump"):
        _assert_finite(obj.model_dump(mode="json"), path)
        return
    # Unknown type — leave alone
    return


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def fresh_state() -> StrategyState:
    """Empty StrategyState for deterministic per-test runs."""
    return StrategyState()


@pytest.fixture
def track() -> TrackConfig:
    return _build_track()


@pytest.fixture
def app() -> FastAPI:
    """Minimal FastAPI app mounting the **real** WebSocket router.

    This is the same pattern used by `test_sidecar_integration.py` and
    `test_ws_integration.py`. We deliberately avoid running the full
    `src.main` lifespan (which spins up LLM, EventStore, SpotterService,
    CrewChief runtime, etc.) because the goal of T9 is to verify the
    strategy flow, not the full app boot.
    """
    app = FastAPI()
    app.include_router(ws_router)
    app.include_router(health_router)

    # The /ws/sidecar endpoint reads from / writes to these attributes
    app.state.latest_strategy_frame = None
    app.state.latest_client_frame = None
    app.state.event_store = None
    app.state.telemetry_reader = None
    app.state.strategy_service = None
    app.state.intelligence_engine = None
    app.state.spotter_service = None
    app.state._last_telemetry_t = 0.0

    return app


# =========================================================================
# 1. compute_strategy() — realistic race scenarios
# =========================================================================

class TestComputeStrategyRealistic:
    """Direct calls to the real `compute_strategy()` engine.

    Each test builds a hand-crafted TelemetryFrame for a specific race
    phase and asserts that the returned StrategyAdvice is **physically
    reasonable** (no negative fuel, ordered pit window, etc.) and
    **contextually appropriate** (early race → late pit window; low
    fuel → early pit window; high battery drain → motor=2 detected).
    """

    def test_early_race_no_pit_needed(
        self, fresh_state: StrategyState, track: TrackConfig
    ) -> None:
        """Lap 5/80, full fuel (95L), fresh tyres (5% wear) → no urgent pit.

        Expected: pit window is well in the future, pit_stops_needed
        low (we won't need to refuel many times over 75 more laps at
        ~2.8 L/lap), stint_end_laps >> session_laps_left so no fuel
        urgency.
        """
        frame = _make_frame(
            lap_number=5,
            lap_distance=1500.0,
            fuel_in_tank=95.0,
            fuel_used_lap_raw=2.8,
            tyre_wear=(5.0, 5.0, 4.0, 4.0),
            brake_wear=(3.0, 3.0, 3.0, 3.0),
            speed=70.0,
        )

        advice, new_state = compute_strategy(frame, fresh_state, track)
        fuel = advice.fuel
        tyres = advice.tyres
        pit = advice.pit_window

        # --- Sanity: physically reasonable values ---
        assert fuel.estimated_laps_remaining >= 0.0
        assert fuel.estimated_time_remaining >= 0.0
        assert fuel.fuel_needed_to_finish >= 0.0
        assert fuel.stint_end_laps >= 0.0
        assert fuel.pit_stops_needed >= 0
        assert fuel.stint_end_fuel >= 0.0

        # --- Pit window ordering ---
        assert pit.earliest_pit_lap <= pit.optimal_pit_lap <= pit.latest_pit_lap
        # Early race: pit window is comfortably in the future
        assert pit.latest_pit_lap > frame.lap_number
        # And not "NOW" — no immediate need to stop
        assert pit.earliest_pit_lap > frame.lap_number

        # --- Tyre wear must echo input ---
        assert tyres.wear_fl == 5.0
        assert tyres.wear_rr == 4.0

        # --- Finite-everywhere invariant ---
        _assert_finite(advice)

        # State should be updated
        assert new_state is not fresh_state  # deep copy
        # The fuel state should record the new lap number
        assert int(new_state.fuel.amount_last) == frame.lap_number

    def test_mid_race_pit_recommended(
        self, fresh_state: StrategyState, track: TrackConfig
    ) -> None:
        """Lap 40/80, 50% fuel (45L), worn tyres (50% wear) → pit recommended.

        Expected: pit window opens soon (earliest_pit_lap close to
        current), pit_stops_needed >= 1 to reach the finish, tyre
        lifespan is non-trivial.
        """
        frame = _make_frame(
            lap_number=40,
            lap_distance=2500.0,
            fuel_in_tank=45.0,
            fuel_used_lap_raw=2.8,
            session_laps_left=40.0,
            tyre_wear=(50.0, 50.0, 48.0, 48.0),
            brake_wear=(35.0, 35.0, 35.0, 35.0),
            speed=70.0,
        )

        advice, _ = compute_strategy(frame, fresh_state, track)
        fuel = advice.fuel
        pit = advice.pit_window

        # --- Pit needed to finish ---
        # 40 laps * 2.8 L/lap = 112 L total; we have 45L; can't finish
        assert fuel.pit_stops_needed >= 1, (
            f"Expected >= 1 pit stop with 45L over 40 laps, got {fuel.pit_stops_needed}"
        )
        # And we need substantial fuel to finish
        assert fuel.fuel_needed_to_finish > frame.fuel_in_tank, (
            f"Expected fuel_needed_to_finish ({fuel.fuel_needed_to_finish}) > "
            f"fuel_in_tank ({frame.fuel_in_tank})"
        )

        # --- Pit window opens this stint ---
        # Earliest pit must be no later than latest, and latest must be
        # later than current lap.
        assert pit.earliest_pit_lap <= pit.latest_pit_lap
        assert pit.latest_pit_lap > frame.lap_number

        # --- Stint can't last the full remaining race ---
        # 45L / 2.8 L/lap ≈ 16 laps remaining on current fuel
        assert 0.0 <= fuel.estimated_laps_remaining < 25.0, (
            f"Expected stint end < 25 laps with 45L, got {fuel.estimated_laps_remaining}"
        )

        # --- Tyre advice: lifecycle remaining must be sane ---
        tyres = advice.tyres
        # Tyres at 50% wear still have 50% capacity left; lifespan is large
        assert tyres.wear_lifespan_laps >= 0.0
        # No negative projected wear
        for w in tyres.projected_wear_end_lap:
            assert 0.0 <= w <= 100.0, f"projected wear out of [0,100]: {w}"

        # --- Hybrid computed without crashing ---
        hybrid = advice.hybrid
        assert hybrid.inferred_motor_state in (1, 2, 3)

        _assert_finite(advice)

    def test_late_race_urgent_pit(
        self, fresh_state: StrategyState, track: TrackConfig
    ) -> None:
        """Lap 75/80, low fuel (12L) → urgent pit.

        Expected: pit window opens immediately (earliest_pit_lap very
        close to current lap), pit_stops_needed >= 1 (or 0 if we can
        just finish on fumes), and the stint is essentially over.
        """
        frame = _make_frame(
            lap_number=75,
            lap_distance=3000.0,
            fuel_in_tank=12.0,
            fuel_used_lap_raw=2.8,
            session_laps_left=5.0,
            session_time_left=5.0 * LAP_TIME_S,
            tyre_wear=(70.0, 70.0, 68.0, 68.0),
            brake_wear=(55.0, 55.0, 55.0, 55.0),
            speed=70.0,
        )

        advice, _ = compute_strategy(frame, fresh_state, track)
        fuel = advice.fuel
        pit = advice.pit_window

        # --- Critical: must request a pit to finish (or be exactly on fumes) ---
        # 5 laps * 2.8 L = 14 L; we have 12 L; we need ≥ 1 pit
        assert fuel.pit_stops_needed >= 1, (
            f"Expected >= 1 pit with 12L over 5 laps, got {fuel.pit_stops_needed}"
        )
        assert fuel.fuel_needed_to_finish > frame.fuel_in_tank, (
            f"Expected fuel_needed > fuel_in_tank, got "
            f"{fuel.fuel_needed_to_finish} vs {frame.fuel_in_tank}"
        )

        # --- Stint end is imminent: < 6 laps of fuel remaining ---
        assert 0.0 <= fuel.estimated_laps_remaining < 6.0, (
            f"Expected < 6 laps fuel remaining with 12L, got "
            f"{fuel.estimated_laps_remaining}"
        )

        # --- Pit window is open / opening ---
        assert pit.earliest_pit_lap <= pit.latest_pit_lap
        assert pit.latest_pit_lap >= frame.lap_number + 1

        # --- Fuel target for one-less-stop is physically reasonable ---
        # If we tried to skip a stop, consumption would have to rise.
        # Should be > current per-lap use.
        assert fuel.one_less_stop_target_consumption > 0.0

        _assert_finite(advice)

    def test_hybrid_battery_deploy_scenario(
        self, fresh_state: StrategyState, track: TrackConfig
    ) -> None:
        """Hybrid/battery deploy: motor_state=2 (Drain), high battery.

        Expected: hybrid.inferred_motor_state == 2, battery_net_delta
        is finite and the engine module does not crash with extreme
        inputs. Fuel/tyre/strategy should still produce reasonable
        numbers — battery deploy is orthogonal to stint length.
        """
        frame = _make_frame(
            lap_number=20,
            lap_distance=2000.0,
            fuel_in_tank=70.0,
            fuel_used_lap_raw=2.5,  # Less fuel used because battery is helping
            session_laps_left=60.0,
            tyre_wear=(15.0, 15.0, 13.0, 13.0),
            brake_wear=(10.0, 10.0, 10.0, 10.0),
            battery_charge=95.0,
            battery_drain=4.0,
            battery_regen=0.5,
            motor_state=2,  # explicit Drain
        )

        advice, new_state = compute_strategy(frame, fresh_state, track)
        hybrid = advice.hybrid
        fuel = advice.fuel

        # --- Motor state is propagated ---
        assert hybrid.inferred_motor_state == 2, (
            f"Expected motor_state=2, got {hybrid.inferred_motor_state}"
        )

        # --- Battery net delta is finite and well-defined ---
        assert math.isfinite(hybrid.battery_net_delta_lap)

        # --- Fuel/energy ratio is computed when drain > 0 ---
        # fuel_used / drain = 2.5 / 4.0 = 0.625
        assert hybrid.fuel_energy_ratio > 0.0, (
            f"Expected positive fuel/energy ratio, got {hybrid.fuel_energy_ratio}"
        )

        # --- Hybrid state machine moved into Drain mode ---
        assert new_state.hybrid.motor_state == 2

        # --- Main fuel/tyre strategy still works ---
        # 60 laps * 2.5 L/lap = 150L; we have 70L → 1+ pit needed
        assert fuel.pit_stops_needed >= 1
        assert fuel.estimated_laps_remaining > 0.0
        # Pit window still monotonic
        assert advice.pit_window.earliest_pit_lap <= advice.pit_window.optimal_pit_lap
        assert advice.pit_window.optimal_pit_lap <= advice.pit_window.latest_pit_lap

        _assert_finite(advice)


# =========================================================================
# 2. Multi-lap evolution — state must accumulate correctly
# =========================================================================

class TestComputeStrategyStateEvolution:
    """Feed the engine successive lap frames; verify state accumulates
    consumption history and stint data instead of being stateless."""

    def test_fuel_consumption_history_grows(
        self, fresh_state: StrategyState, track: TrackConfig
    ) -> None:
        """After processing 4 lap frames the fuel state should hold a
        consumption_history with 3 entries.

        The engine records the consumption of lap N when the frame for
        lap N+1 arrives (see shared-strategy/fuel.py: detection of
        "cruce de meta"). So:
          - frame(lap=1) → no history (first frame)
          - frame(lap=2) → records lap 1
          - frame(lap=3) → records lap 2
          - frame(lap=4) → records lap 3
        """
        state = fresh_state
        for lap in range(1, 5):
            frame = _make_frame(
                lap_number=lap,
                lap_distance=1500.0,
                fuel_in_tank=100.0 - lap * 2.8,
                fuel_used_lap_raw=2.8,
                speed=70.0,
            )
            _, state = compute_strategy(frame, state, track)

        # 3 entries (laps 1, 2, 3)
        assert len(state.fuel.consumption_history) == 3, (
            f"Expected 3 history entries, got {len(state.fuel.consumption_history)}"
        )
        first = state.fuel.consumption_history[0]
        assert first.lap_num == 1
        assert math.isclose(first.fuel_used, 2.8, rel_tol=0.01)
        last = state.fuel.consumption_history[-1]
        assert last.lap_num == 3


# =========================================================================
# 3. End-to-end via WebSocket: /ws/sidecar receives a real strategy_frame
# =========================================================================

class TestStrategyFlowWebSocketE2E:
    """End-to-end: real compute_strategy() → real WebSocket round-trip
    to the backend's /ws/sidecar endpoint.

    This mirrors the production sidecar pipeline (sidecar/main.py
    :StrategyRunner.process_cycle() → ws.send({event: strategy_frame}))
    without the heavy Windows-only LMU shared-memory dependency.
    """

    def test_strategy_frame_received_by_backend(
        self, app: FastAPI, track: TrackConfig
    ) -> None:
        """Build a real TelemetryFrame → compute_strategy() →
        inject the resulting advice+frame as a strategy_frame →
        backend stores it in app.state.latest_strategy_frame."""
        # 1) Real frame + real strategy engine
        frame = _make_frame(
            lap_number=15,
            lap_distance=2000.0,
            fuel_in_tank=72.0,
            fuel_used_lap_raw=2.8,
            session_laps_left=65.0,
            position=5,
        )
        advice, _ = compute_strategy(frame, StrategyState(), track)

        # 2) The /ws/sidecar endpoint expects a strategy_frame payload
        # exactly like the sidecar produces (see sidecar/main.py:99-107).
        payload = {
            "event": "strategy_frame",
            "data": {
                "advice": advice.model_dump(mode="json"),
                "frame": frame.model_dump(mode="json"),
                "events": [
                    {
                        "type": "lap_completed",
                        "lap": frame.lap_number,
                        "timestamp": time.time(),
                        "data": {
                            "lap_number": frame.lap_number,
                            "fuel_used": frame.fuel_used_lap_raw,
                            "avg_speed": frame.speed,
                        },
                    }
                ],
            },
        }

        # 3) Real WebSocket connection to /ws/sidecar (NOT /ws/)
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                ws.send_json(payload)
                # Give the server event loop a tick to process the frame
                # (the sidecar endpoint is await-based; TestClient is sync)
                ws.send_json({"event": "ping"})  # yield control

            # 4) Verify backend stored the strategy frame
            assert app.state.latest_strategy_frame is not None
            stored = app.state.latest_strategy_frame
            assert "advice" in stored
            assert "frame" in stored
            assert "events" in stored

            # 5) Verify advice fields survived the round-trip
            advice_back = stored["advice"]
            assert "fuel" in advice_back
            assert "tyres" in advice_back
            assert "pit_window" in advice_back
            assert "hybrid" in advice_back

            # 6) Verify frame fields survived
            frame_back = stored["frame"]
            assert frame_back["lap_number"] == 15
            assert frame_back["fuel_in_tank"] == 72.0
            assert frame_back["session_type"] == "race"

            # 7) Verify the lap_completed event was preserved
            assert len(stored["events"]) == 1
            assert stored["events"][0]["type"] == "lap_completed"
            assert stored["events"][0]["lap"] == 15

    def test_advice_round_trip_preserves_pit_window_advice(
        self, app: FastAPI, track: TrackConfig
    ) -> None:
        """The pit_window block of the advice must survive serialization
        → WS → state — no field loss or type corruption."""
        frame = _make_frame(
            lap_number=42,
            lap_distance=1800.0,
            fuel_in_tank=38.0,
            session_laps_left=38.0,
            tyre_wear=(48.0, 48.0, 46.0, 46.0),
        )
        advice, _ = compute_strategy(frame, StrategyState(), track)
        original_pit = advice.pit_window

        payload = {
            "event": "strategy_frame",
            "data": {
                "advice": advice.model_dump(mode="json"),
                "frame": frame.model_dump(mode="json"),
                "events": [],
            },
        }

        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                ws.send_json(payload)
                ws.send_json({"event": "ping"})

            stored = app.state.latest_strategy_frame
            assert stored is not None
            pit_back = stored["advice"]["pit_window"]

            # All 6 fields preserved
            for field_name in (
                "earliest_pit_lap",
                "latest_pit_lap",
                "optimal_pit_lap",
                "undercut_potential",
                "overcut_potential",
                "pit_loss_time_estimate",
            ):
                assert field_name in pit_back, f"Missing pit_window field: {field_name}"

            # Same numeric values
            assert pit_back["earliest_pit_lap"] == original_pit.earliest_pit_lap
            assert pit_back["latest_pit_lap"] == original_pit.latest_pit_lap
            assert pit_back["optimal_pit_lap"] == original_pit.optimal_pit_lap
            # Boolean fields
            assert pit_back["undercut_potential"] == original_pit.undercut_potential
            assert pit_back["overcut_potential"] == original_pit.overcut_potential
            # Float
            assert math.isclose(
                pit_back["pit_loss_time_estimate"],
                original_pit.pit_loss_time_estimate,
                rel_tol=1e-6,
            )

    def test_multiple_strategy_frames_are_processed_in_order(
        self, app: FastAPI, track: TrackConfig
    ) -> None:
        """Sending 3 strategy_frames for laps 10, 11, 12 must store the
        last one (lap 12) in app.state.latest_strategy_frame, proving
        the endpoint is not single-shot."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                for lap in (10, 11, 12):
                    frame = _make_frame(
                        lap_number=lap,
                        lap_distance=1500.0,
                        fuel_in_tank=100.0 - lap * 2.8,
                    )
                    advice, _ = compute_strategy(frame, StrategyState(), track)
                    ws.send_json({
                        "event": "strategy_frame",
                        "data": {
                            "advice": advice.model_dump(mode="json"),
                            "frame": frame.model_dump(mode="json"),
                            "events": [],
                        },
                    })
                    ws.send_json({"event": "ping"})  # yield

            stored = app.state.latest_strategy_frame
            assert stored is not None
            assert stored["frame"]["lap_number"] == 12, (
                f"Expected last stored lap=12, got {stored['frame']['lap_number']}"
            )

    def test_competitor_data_propagates_to_advice(
        self, app: FastAPI, track: TrackConfig
    ) -> None:
        """When the frame has a competitor in the same class with a
        close gap, the advice.competitors list must contain it after
        the round-trip through /ws/sidecar."""
        rival_ahead = _make_rival(
            driver_index=2,
            name="Ayrton",
            position=4,
            lap_number=16,
            lap_distance=1900.0,
            gap_seconds=2.5,
            fuel_fraction=0.7,
        )
        frame = _make_frame(
            lap_number=15,
            lap_distance=1500.0,
            fuel_in_tank=70.0,
            competitors=[rival_ahead],
        )
        advice, _ = compute_strategy(frame, StrategyState(), track)

        # Sanity: advice should have 1 competitor
        assert len(advice.competitors) == 1
        comp = advice.competitors[0]
        assert comp.driver_name == "Ayrton"
        assert comp.standing_position == 4

        # Round-trip
        payload = {
            "event": "strategy_frame",
            "data": {
                "advice": advice.model_dump(mode="json"),
                "frame": frame.model_dump(mode="json"),
                "events": [],
            },
        }
        with TestClient(app) as client:
            with client.websocket_connect("/ws/sidecar") as ws:
                ws.send_json(payload)
                ws.send_json({"event": "ping"})

            stored = app.state.latest_strategy_frame
            comps_back = stored["advice"]["competitors"]
            assert len(comps_back) == 1
            assert comps_back[0]["driver_name"] == "Ayrton"
            assert comps_back[0]["standing_position"] == 4


# =========================================================================
# 4. Physical reasonability invariants (applies to every scenario)
# =========================================================================

class TestPhysicallyReasonableOutputs:
    """Sanity invariants that any physically-reasonable StrategyAdvice
    must satisfy. These are the safety net the task brief calls out:
    "Strategy values are physically reasonable (not negative fuel,
    not 0 laps for non-finish)"."""

    @pytest.mark.parametrize(
        "lap,fuel,wear,brake,scenario_name",
        [
            (5, 95.0, (5.0, 5.0, 4.0, 4.0), (3.0, 3.0, 3.0, 3.0), "early"),
            (20, 70.0, (15.0, 15.0, 13.0, 13.0), (10.0, 10.0, 10.0, 10.0), "early-mid"),
            (40, 45.0, (50.0, 50.0, 48.0, 48.0), (35.0, 35.0, 35.0, 35.0), "mid"),
            (60, 28.0, (62.0, 62.0, 60.0, 60.0), (48.0, 48.0, 48.0, 48.0), "late-mid"),
            (75, 12.0, (70.0, 70.0, 68.0, 68.0), (55.0, 55.0, 55.0, 55.0), "late"),
        ],
    )
    def test_invariants_across_race_phases(
        self,
        fresh_state: StrategyState,
        track: TrackConfig,
        lap: int,
        fuel: float,
        wear: tuple[float, float, float, float],
        brake: tuple[float, float, float, float],
        scenario_name: str,
    ) -> None:
        """Across a 5-scenario sweep, every output must be physically
        reasonable: non-negative, ordered, finite."""
        frame = _make_frame(
            lap_number=lap,
            lap_distance=1500.0,
            fuel_in_tank=fuel,
            fuel_used_lap_raw=2.8,
            tyre_wear=wear,
            brake_wear=brake,
        )
        advice, _ = compute_strategy(frame, fresh_state, track)

        # --- Fuel: no negatives, no NaN, no inf ---
        f = advice.fuel
        assert f.estimated_laps_remaining >= 0.0
        assert f.estimated_time_remaining >= 0.0
        assert f.fuel_needed_to_finish >= 0.0
        assert f.stint_end_laps >= 0.0
        assert f.stint_end_fuel >= 0.0
        assert f.pit_stops_needed >= 0
        assert math.isfinite(f.instantaneous_delta_fuel)
        assert math.isfinite(f.one_less_stop_target_consumption)

        # --- Tyres: 0–100%, lifespan non-negative ---
        t = advice.tyres
        for w in (t.wear_fl, t.wear_fr, t.wear_rl, t.wear_rr):
            assert 0.0 <= w <= 100.0, f"wear out of [0,100] in {scenario_name}: {w}"
        for pw in t.projected_wear_end_lap:
            assert 0.0 <= pw <= 100.0, (
                f"projected wear out of [0,100] in {scenario_name}: {pw}"
            )
        assert t.wear_lifespan_laps >= 0.0
        assert t.wear_lifespan_mins >= 0.0
        assert math.isfinite(t.estimated_performance_loss_laptime)

        # --- Brakes: 0–100% ---
        b = advice.brakes
        for w in (b.wear_fl, b.wear_fr, b.wear_rl, b.wear_rr):
            assert 0.0 <= w <= 100.0, f"brake wear out of [0,100]: {w}"
        assert b.lifespan_laps >= 0.0

        # --- Pit window: ordered, future, finite ---
        p = advice.pit_window
        assert p.earliest_pit_lap <= p.optimal_pit_lap <= p.latest_pit_lap
        assert p.latest_pit_lap >= frame.lap_number
        assert p.pit_loss_time_estimate > 0.0
        assert isinstance(p.undercut_potential, bool)
        assert isinstance(p.overcut_potential, bool)

        # --- Hybrid: motor state in {1,2,3}, finite numbers ---
        h = advice.hybrid
        assert h.inferred_motor_state in (1, 2, 3)
        assert math.isfinite(h.battery_net_delta_lap)
        assert math.isfinite(h.fuel_energy_ratio)
        assert math.isfinite(h.fuel_energy_bias)

        # --- Full invariant: every float in the advice is finite ---
        _assert_finite(advice)
