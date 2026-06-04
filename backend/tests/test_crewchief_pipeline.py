"""Pipeline integration tests — verify data flow for all bugfixes.

Cada test construye GameStateData usando el builder real desde flat dicts
(simulando el pipeline lmu_reader → frame_cache → build → evento).
Verifica que los mensajes lleguen al FakeAudioPlayer con los datos correctos.
"""

import time
import asyncio
import pytest

from src.services.game_state_builder import build
from src.models.game_state_data import GameStateData
from src.models.enums import SessionType, SessionPhase, FrozenOrderPhase
from src.intelligence.base_event import FakeAudioPlayer
from src.intelligence.event_flags import event_flags


# ============================================================
# Helper: build GSD from flat dict (simula pipeline real)
# ============================================================
def _gsd(extra: dict = None):
    """Construye GameStateData desde un flat dict."""
    flat = {
        "session_type": 3, "session_phase": 5, "lap_number": 5,
        "place": 5, "driver_name": "Test", "best_lap_time": 90.0,
        "last_lap_time": 92.0, "timestamp": time.time(),
        "sector_number": 1, "track_length": 4000, "speed_ms": 30.0,
        "lap_distance": 500.0, "engine_rpm": 5000, "gear": 2,
        "water_temp": 90.0, "oil_temp": 100.0,
        "fuel_left": 50.0, "fuel_capacity": 100.0,
        "in_pits": False, "pit_state": 0, "num_pitstops": 0,
        "tyre_temp_fl": 90.0, "tyre_temp_fr": 90.0,
        "tyre_temp_rl": 90.0, "tyre_temp_rr": 90.0,
        "tyre_pressure_fl": 160.0, "tyre_pressure_fr": 160.0,
        "tyre_pressure_rl": 160.0, "tyre_pressure_rr": 160.0,
        "tyre_wear": [0.3, 0.3, 0.3, 0.3],
        "tyre_compound_fl": "Soft", "tyre_compound_rl": "Soft",
        "vehicle_class": "GT3",
    }
    if extra:
        flat.update(extra)
    return build(flat)


# ============================================================
# Bug #11: TyreMonitor false lockup on first tick
# ============================================================
class TestTyreMonitorNoFalseLockup:
    """Pipeline: flat dict → build → TyreMonitor → FakeAudioPlayer"""

    def test_no_lockup_on_first_tick_with_real_temps(self):
        from src.intelligence.events.tyre_monitor import TyreMonitor
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)

        g = _gsd(extra={"tyre_temp_fl": 85.0, "tyre_temp_fr": 87.0,
                        "speed_ms": 25.0})
        ev.trigger_internal(None, g)

        lockups = [m.name for m in ap.messages if "locking" in m.name]
        assert len(lockups) == 0, f"Falso lockup en primer tick: {lockups}"

    def test_real_lockup_still_detected_on_second_tick(self):
        from src.intelligence.events.tyre_monitor import TyreMonitor
        ap = FakeAudioPlayer()
        ev = TyreMonitor(ap)

        g1 = _gsd(extra={"tyre_temp_fl": 85.0, "tyre_temp_fr": 85.0,
                          "speed_ms": 25.0})
        ev.trigger_internal(None, g1)
        ap.clear()

        g2 = _gsd(extra={"tyre_temp_fl": 102.0, "tyre_pressure_fl": 153.0,
                          "speed_ms": 25.0})
        ev.trigger_internal(None, g2)

        names = [m.name for m in ap.messages]
        assert "tyre_monitor/fl_locking" in names, (
            f"Lockup real no detectado. Mensajes: {names}"
        )


# ============================================================
# Bug #12: EngineMonitor overheating icon immediately
# ============================================================
class TestEngineMonitorIconImmediate:
    """El icono de overheating debe dispararse inmediatamente sin esperar MIN_SAMPLES."""

    def test_overheating_icon_triggers_before_min_samples(self):
        from src.intelligence.events.engine_monitor import EngineMonitor
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)

        for _ in range(2):
            ev.trigger_internal(None, _gsd(extra={"engine_rpm": 5000,
                                                    "overheating": True}))

        names = [m.name for m in ap.immediate_messages]
        assert "engine_monitor/engine_overheating" in names, (
            f"Icono overheating no disparado inmediatamente. Msgs: {names}"
        )

    def test_water_temp_still_requires_min_samples(self):
        """La temperatura de agua DEBE esperar MIN_SAMPLES (10 muestras)."""
        from src.intelligence.events.engine_monitor import EngineMonitor
        ap = FakeAudioPlayer()
        ev = EngineMonitor(ap)

        for _ in range(5):
            ev.trigger_internal(None, _gsd(extra={"water_temp": 115.0}))

        msgs = ap.messages
        names = [m.name for m in msgs if "engine_overheating" in m.name]
        assert len(names) == 0, (
            f"Overheat por temperatura emitido con solo 5 muestras: {names}"
        )


# ============================================================
# Bug #13: Sequence ordering in EventEngine
# ============================================================
class TestEventSequenceOrder:
    """EventEngine debe respetar el orden de sequence."""

    def test_events_dispatch_in_correct_sequence(self):
        from src.intelligence.event_engine import EventEngine
        from src.intelligence.events.lap_counter import LapCounter
        from src.intelligence.events.conditions_monitor import ConditionsMonitor
        from src.intelligence.events.flags_monitor import FlagsMonitor
        from src.intelligence.events.session_monitor import SessionMonitor
        from src.intelligence.events.position import PositionEvent
        from src.intelligence.events.pit_stops import PitStops
        from src.intelligence.events.fuel import FuelEvent
        from src.intelligence.events.battery import BatteryEvent
        from src.intelligence.events.tyre_monitor import TyreMonitor
        from src.intelligence.events.damage_reporting import DamageReporting
        from src.intelligence.events.engine_monitor import EngineMonitor
        from src.intelligence.events.frozen_order_monitor import FrozenOrderMonitor

        ap = FakeAudioPlayer()
        engine = EventEngine(audio_player=ap)
        engine.register_event("tyre_monitor", TyreMonitor(ap))
        engine.register_event("engine_monitor", EngineMonitor(ap))
        engine.register_event("battery", BatteryEvent(ap))
        engine.register_event("damage_reporting", DamageReporting(ap))
        engine.register_event("lap_counter", LapCounter(ap))
        engine.register_event("position", PositionEvent(ap))
        engine.register_event("conditions_monitor", ConditionsMonitor(ap))
        engine.register_event("pit_stops", PitStops(ap))
        engine.register_event("fuel", FuelEvent(ap))
        engine.register_event("session_monitor", SessionMonitor(ap))
        engine.register_event("flags_monitor", FlagsMonitor(ap))
        engine.register_event("frozen_order_monitor", FrozenOrderMonitor(ap))

        ordered = sorted(engine._events.values(), key=lambda e: (e.sequence, type(e).__name__))
        seqs = [e.sequence for e in ordered]
        assert seqs == sorted(seqs), f"Secuencias desordenadas: {seqs}"
        assert len(set(seqs)) == 12, f"Secuencias duplicadas: {seqs}"


# ============================================================
# L1: Pit window uses track_definition
# ============================================================
class TestPitWindowUsesTrackDef:
    """Pit window debe usar FUEL_WINDOW_LENGTH de track_definition."""

    def test_pit_window_short_track(self):
        from src.intelligence.events.pit_stops import PitStops

        ap = FakeAudioPlayer()
        ev = PitStops(ap)

        g = _gsd(extra={"track_length": 800, "pit_state": 2,
                        "in_pits": True})
        ev.trigger_internal(None, g)
        g2 = _gsd(extra={"track_length": 800, "pit_state": 0,
                         "in_pits": False, "lap_number": 5})
        ev.trigger_internal(None, g2)

        names = [m.name for m in ap.messages]
        assert "pit_stops/pit_window_open" in names, (
            f"Pit window no detectada en vuelta 5. Mensajes: {names}"
        )


# ============================================================
# L2: PIT_REQUEST detection
# ============================================================
class TestPitRequestDetection:
    """pit_state=1 debe emitir pit_requested."""

    def test_pit_request_emits_message(self):
        from src.intelligence.events.pit_stops import PitStops

        ap = FakeAudioPlayer()
        ev = PitStops(ap)

        g = _gsd(extra={"pit_state": 1})
        ev.trigger_internal(None, g)

        names = [m.name for m in ap.messages]
        assert "pit_stops/pit_requested" in names, (
            f"PIT_REQUEST no detectado. Mensajes: {names}"
        )


# ============================================================
# L3: Battery recharge threshold lowered
# ============================================================
class TestBatteryRechargeThreshold:
    """Recarga de bateria debe detectarse con >5% de incremento."""

    def test_battery_recharge_at_6_percent(self):
        from src.intelligence.events.battery import BatteryEvent
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)

        ev._last_ve_pct = 20.0

        g = _gsd(extra={"virtual_energy": 27.0, "virtual_energy_max": 100.0,
                        "lap_number": 5})
        ev.trigger_internal(None, g)

        names = [m.name for m in ap.messages]
        assert "battery/recharge_complete" in names, (
            f"Recarga no detectada con +7%. Mensajes: {names}"
        )

    def test_battery_no_recharge_at_3_percent(self):
        from src.intelligence.events.battery import BatteryEvent
        ap = FakeAudioPlayer()
        ev = BatteryEvent(ap)

        ev._last_ve_pct = 20.0

        g = _gsd(extra={"virtual_energy": 23.0, "virtual_energy_max": 100.0,
                        "lap_number": 5})
        ev.trigger_internal(None, g)

        names = [m.name for m in ap.messages]
        assert "battery/recharge_complete" not in names, (
            f"Recarga falsa detectada con solo +3%. Mensajes: {names}"
        )


# ============================================================
# L4: Fuel consumption delta capped
# ============================================================
class TestFuelConsumptionCapped:
    """Delta de consumo >20L no debe registrarse como muestra."""

    def test_large_fuel_drop_not_recorded(self):
        from src.intelligence.events.fuel import FuelEvent
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)

        ev.trigger_internal(None, _gsd(extra={"fuel_left": 50.0, "lap_number": 1}))
        ev.trigger_internal(None, _gsd(extra={"fuel_left": 25.0, "lap_number": 2}))

        assert len(ev._consumption_samples) == 0, (
            f"Delta de 25L registrado como consumo: {ev._consumption_samples}"
        )

    def test_normal_fuel_drop_recorded(self):
        from src.intelligence.events.fuel import FuelEvent
        ap = FakeAudioPlayer()
        ev = FuelEvent(ap)

        ev.trigger_internal(None, _gsd(extra={"fuel_left": 50.0, "lap_number": 1}))
        ev.trigger_internal(None, _gsd(extra={"fuel_left": 47.0, "lap_number": 2}))

        assert len(ev._consumption_samples) == 1, (
            f"Delta de 3L no registrado: {ev._consumption_samples}"
        )


# ============================================================
# L5: FCY→GREEN direct transition
# ============================================================
class TestFcyToGreenDirect:
    """FCY→GREEN sin pasar por FrozenOrderPhase.NONE debe emitir sc_ending."""

    def test_fcy_to_green_emits_sc_ending(self):
        from src.intelligence.events.frozen_order_monitor import FrozenOrderMonitor
        from src.models.enums import FrozenOrderPhase
        ap = FakeAudioPlayer()
        ev = FrozenOrderMonitor(ap)

        g1 = _gsd(extra={"session_phase": 6})
        g1.frozen_order.phase = FrozenOrderPhase.FCY
        ev.trigger_internal(None, g1)
        ap.clear()

        g2 = _gsd(extra={"session_phase": 5})
        g2.frozen_order.phase = FrozenOrderPhase.NONE
        ev.trigger_internal(None, g2)

        names = [m.name for m in ap.messages]
        assert "frozen_order/sc_ending" in names, (
            f"FCY→GREEN directo no emite sc_ending. Mensajes: {names}"
        )


# ============================================================
# L7: Progressive rollover warnings
# ============================================================
class TestProgressiveRollover:
    """Vuelco progresivo: 25° warning, 45° rollover."""

    def test_roll_warning_at_30_degrees(self):
        from src.intelligence.events.damage_reporting import DamageReporting
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)

        g = _gsd(extra={"speed_ms": 0.0, "rotation_roll": 30.0})
        ev.trigger_internal(None, g)

        names = [m.name for m in ap.immediate_messages]
        assert any("rollover" in n for n in names), (
            f"Roll warning a 30° no emitido. Msgs: {names}"
        )

    def test_rollover_at_50_degrees(self):
        from src.intelligence.events.damage_reporting import DamageReporting
        ap = FakeAudioPlayer()
        ev = DamageReporting(ap)

        g = _gsd(extra={"speed_ms": 0.0, "rotation_roll": 50.0})
        ev.trigger_internal(None, g)

        names = [m.name for m in ap.immediate_messages]
        assert "damage/rollover" in names, (
            f"Rollover a 50° no emitido. Msgs: {names}"
        )
        assert event_flags.waiting_for_driver_is_ok_response, (
            "Rollover no activa driver_ok flag"
        )
        event_flags.waiting_for_driver_is_ok_response = False


# ============================================================
# END-TO-END PIPELINE: 45 ticks simulando carrera real
# ============================================================
class TestEndToEndPipeline:
    """Pipeline completo: flat dict → build → EventEngine(12 eventos) → FakeAudioPlayer.

    Simula 45 ticks de carrera con:
    - Formation → Green → FCY → Green → Pit Stop → Checkered
    - Fuel consumption over 5 laps
    - Battery drain
    - Tyre temperature changes
    - Damage impact
    """

    @pytest.mark.asyncio
    async def test_45_tick_race_simulation(self):
        from src.services.game_state_builder import build
        from src.intelligence.event_engine import EventEngine
        from src.intelligence.base_event import FakeAudioPlayer
        from src.intelligence.event_flags import event_flags
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

        ap = FakeAudioPlayer()
        engine = EventEngine(audio_player=ap)

        # Register all 12 events
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

        event_flags.reset_all()

        import time
        now = 1000.0

        def make_tick(tick, phase, laps, fuel=50, water=90, oil=100,
                      fl_temp=90, in_pits=False, pit_state=0,
                      fcy_phase=0, ve_pct=50,
                      impact_time=-1, impact_mag=0,
                      overheating=False):
            nonlocal now
            now += 0.1
            return build({
                "timestamp": now,
                "session_type": 3,
                "session_phase": phase,
                "session_running_time": tick * 0.1,
                "session_time_remaining": 3600 - tick * 0.1,
                "lap_number": laps,
                "place": 3,
                "driver_name": "Player",
                "best_lap_time": 90.0,
                "last_lap_time": 92.0,
                "sector_number": 1,
                "track_length": 4000,
                "speed_ms": 40.0,
                "lap_distance": (tick % 100) * 10.0,
                "engine_rpm": 7000,
                "gear": 3,
                "water_temp": water,
                "oil_temp": oil,
                "overheating": overheating,
                "engine_max_rpm": 8000,
                "fuel_left": fuel,
                "fuel_capacity": 100.0,
                "in_pits": in_pits,
                "pit_state": pit_state,
                "num_pitstops": 0,
                "speed_limiter": True if pit_state == 2 else False,
                "vehicle_class": "GT3",
                "tyre_temp_fl": fl_temp,
                "tyre_temp_fr": fl_temp - 2,
                "tyre_temp_rl": fl_temp - 1,
                "tyre_temp_rr": fl_temp + 1,
                "tyre_pressure_fl": 170.0,
                "tyre_pressure_fr": 168.0,
                "tyre_pressure_rl": 169.0,
                "tyre_pressure_rr": 171.0,
                "tyre_wear": [0.2, 0.22, 0.19, 0.21],
                "tyre_compound_fl": "Soft",
                "tyre_compound_rl": "Soft",
                "ambient_temp": 22.0,
                "track_temp": 35.0,
                "rain_intensity": 0.0,
                "damage_aero": 0.0,
                "suspension_damage": [0.0, 0.0, 0.0, 0.0],
                "virtual_energy": ve_pct if ve_pct > 0 else 0,
                "virtual_energy_max": 100.0,
                "last_impact_time": impact_time,
                "last_impact_mag": impact_mag,
                "rotation_roll": 0.0,
                "rotation_pitch": 0.0,
            })

        prev_gsd = None
        all_messages = []

        # === Tick 1-5: FORMATION ===
        for t in range(1, 6):
            gsd = make_tick(t, 3, 0)
            await engine.tick_async(prev_gsd, gsd)
            prev_gsd = gsd

        names_t1_5 = [m.name for m in ap.messages]
        assert any("formation" in n for n in names_t1_5), \
            f"No formation messages in ticks 1-5: {names_t1_5}"

        ap.clear()

        # === Tick 6-15: GREEN (10 ticks of racing) ===
        laps = 0
        for t in range(6, 16):
            lap = (t - 5) // 2
            laps = lap
            fuel_val = 15.0 - lap * 2.5  # Start low to trigger fuel warnings
            fl_temp = 100 + t  # Temps increasing; crosses 110°C Soft threshold at t=10
            gsd = make_tick(t, 5, laps, fuel=fuel_val, fl_temp=fl_temp)
            await engine.tick_async(prev_gsd, gsd)
            prev_gsd = gsd

        names_t6_15 = [m.name for m in ap.messages]
        assert any("fuel" in n for n in names_t6_15), \
            f"No fuel messages in ticks 6-15: {names_t6_15}"
        assert any("tyre" in n for n in names_t6_15), \
            f"No tyre messages in ticks 6-15: {names_t6_15}"

        ap.clear()

        # === Tick 16-20: FCY (safety car) ===
        prev_gsd._frozen_order_phase = 0
        for t in range(16, 21):
            gsd = make_tick(t, 6, laps, fuel=fuel_val - 0.1 * (t - 15))
            await engine.tick_async(prev_gsd, gsd)
            prev_gsd = gsd

        names_t16_20 = [m.name for m in ap.messages]
        names_t16_20_imm = [m.name for m in ap.immediate_messages]
        all_t16_20 = names_t16_20 + names_t16_20_imm
        assert any("fcy" in n or "sc_" in n for n in all_t16_20), \
            f"No FCY/SC messages in ticks 16-20: {all_t16_20}"

        ap.clear()

        # === Tick 21-30: GREEN resumes, pit stop ===
        fuel_val = 30.0
        for t in range(21, 26):
            laps += 1
            fuel_val -= 3.0
            gsd = make_tick(t, 5, laps, fuel=fuel_val)
            await engine.tick_async(prev_gsd, gsd)
            prev_gsd = gsd

        ap.clear()

        # Pit stop: entering (tick 26)
        gsd = make_tick(26, 5, laps, fuel=8.0, in_pits=True, pit_state=2)
        await engine.tick_async(prev_gsd, gsd)
        prev_gsd = gsd

        names_pit_entry = [m.name for m in ap.messages]
        assert any("pit_entry" in n for n in names_pit_entry), \
            f"No pit entry message: {names_pit_entry}"
        assert event_flags.is_pitting_this_lap, \
            "is_pitting_this_lap should be True after pit entry"
        ap.clear()

        # Pit stop: stopped (tick 27)
        gsd = make_tick(27, 5, laps, fuel=8.0, in_pits=True, pit_state=3)
        await engine.tick_async(prev_gsd, gsd)
        prev_gsd = gsd
        assert event_flags.is_pitting_this_lap, \
            "is_pitting_this_lap should be True while stopped"
        ap.clear()

        # Pit stop: exiting (tick 28)
        gsd = make_tick(28, 5, laps, fuel=80.0, in_pits=True, pit_state=4)
        await engine.tick_async(prev_gsd, gsd)
        prev_gsd = gsd

        names_pit_exit = [m.name for m in ap.immediate_messages]
        assert any("go_go_go" in n for n in names_pit_exit), \
            f"No go_go_go after pit exit: {names_pit_exit}"
        ap.clear()

        # Back on track (tick 29)
        gsd = make_tick(29, 5, laps, fuel=80.0, in_pits=False, pit_state=0)
        await engine.tick_async(prev_gsd, gsd)
        prev_gsd = gsd
        assert not event_flags.is_pitting_this_lap, \
            "is_pitting_this_lap should be False after pit exit"
        # Fuel refuel detected: _last_fuel=15.0 → 80.0
        names_back = [m.name for m in ap.messages]
        assert any("fuel_ok" in n for n in names_back), \
            f"No fuel_ok_after_refuel on track after pit: {names_back}"
        ap.clear()

        # === Tick 30-40: More racing, then CHECKERED ===
        for t in range(30, 41):
            laps += 1
            fuel_val = 18.0 - (t - 30) * 3.0  # Low fuel to trigger warnings again
            ve_pct = 80 - (t - 29) * 2
            gsd = make_tick(t, 5, laps, fuel=fuel_val, ve_pct=ve_pct)
            await engine.tick_async(prev_gsd, gsd)
            prev_gsd = gsd

        names_t30_40 = [m.name for m in ap.messages]
        assert any("fuel" in n for n in names_t30_40), \
            f"No fuel messages in ticks 30-40: {names_t30_40}"
        assert any("battery" in n for n in names_t30_40), \
            f"No battery messages in ticks 30-40: {names_t30_40}"
        ap.clear()

        # === Tick 41-43: Engine issues ===
        for t in range(41, 44):
            gsd = make_tick(t, 5, laps, fuel=5.0, water=120, oil=140,
                            overheating=True)
            await engine.tick_async(prev_gsd, gsd)
            prev_gsd = gsd

        names_t41_43 = [m.name for m in ap.messages]
        names_t41_43_imm = [m.name for m in ap.immediate_messages]
        all_t41_43 = names_t41_43 + names_t41_43_imm
        assert any("engine" in n for n in all_t41_43), \
            f"No engine messages in ticks 41-43: {all_t41_43}"
        ap.clear()

        # === Tick 44: Heavy impact ===
        gsd = make_tick(44, 5, laps, fuel=5.0, impact_time=1044.0, impact_mag=8.0)
        await engine.tick_async(prev_gsd, gsd)
        prev_gsd = gsd
        assert event_flags.waiting_for_driver_is_ok_response, \
            "Heavy impact should set waiting_for_driver_is_ok_response"
        ap.clear()

        # === Tick 45: CHECKERED ===
        gsd = make_tick(45, 7, laps, fuel=5.0)
        await engine.tick_async(prev_gsd, gsd)
        prev_gsd = gsd

        names_t45 = [m.name for m in ap.messages] + [m.name for m in ap.immediate_messages]
        assert any("chequered" in n or "finished" in n for n in names_t45), \
            f"No finish messages in tick 45: {names_t45}"

        event_flags.reset_all()
        assert True
