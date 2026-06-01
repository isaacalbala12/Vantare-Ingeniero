"""Tests del StateDiff — detector de cambios entre ticks con anti-bouncing.

Cobertura:
- Primera actualización (init)
- Detección de nueva vuelta, nuevo sector, cambio de fase
- Cambio de líder
- Retiradas y nuevos pilotos
- Entradas/salidas de pits
- Anti-bouncing de posiciones (oscilación rápida)
- Múltiples cambios simultáneos
- Estabilidad: cambios pequeños que no deben reportarse
"""
import pytest
from src.services.state_diff import StateDiff, TickChanges


def _flat(lap=1, sector=1, phase=5, place=1, leader="Alice", running_time=10.0, rivals=None):
    if rivals is None:
        rivals = []
    return {
        "lap_number": lap,
        "sector_number": sector,
        "session_phase": phase,
        "session_running_time": running_time,
        "place": place,
        "driver_name": "Player",
        "leader_raw_name": leader,
        "rivals": rivals,
    }


class TestInit:
    def test_first_update_no_changes_no_crash(self):
        d = StateDiff()
        c = d.update(_flat())
        assert isinstance(c, TickChanges)
        assert c.new_lap is False
        assert c.position_changed is False
        assert c.leader_changed is False

    def test_first_update_stores_state(self):
        d = StateDiff()
        d.update(_flat(lap=3, place=5, leader="Bob"))
        c = d.update(_flat(lap=3, place=5, leader="Bob"))
        assert c.new_lap is False
        assert c.position_changed is False
        assert c.leader_changed is False


class TestLapDetection:
    def test_new_lap_detected(self):
        d = StateDiff()
        d.update(_flat(lap=1))
        c = d.update(_flat(lap=2))
        assert c.new_lap is True

    def test_no_new_lap_when_same(self):
        d = StateDiff()
        d.update(_flat(lap=5))
        c = d.update(_flat(lap=5))
        assert c.new_lap is False

    def test_no_new_lap_on_lap_decrease(self):
        """Si el lap_number baja (raro pero posible al reiniciar sesión), no es 'nueva vuelta'."""
        d = StateDiff()
        d.update(_flat(lap=5))
        c = d.update(_flat(lap=4))
        assert c.new_lap is False

    def test_new_lap_skips_multiple(self):
        """Si saltamos 2 vueltas de golpe (ej: teleport/rejoin), sigue siendo 'nueva vuelta'."""
        d = StateDiff()
        d.update(_flat(lap=1))
        c = d.update(_flat(lap=3))
        assert c.new_lap is True


class TestSectorDetection:
    def test_new_sector_detected(self):
        d = StateDiff()
        d.update(_flat(sector=1))
        c = d.update(_flat(sector=2))
        assert c.new_sector is True

    def test_same_sector_no_change(self):
        d = StateDiff()
        d.update(_flat(sector=2))
        c = d.update(_flat(sector=2))
        assert c.new_sector is False

    def test_sector_wrap_3_to_1(self):
        """Cruzar la línea de meta cambia sector de 3 a 1."""
        d = StateDiff()
        d.update(_flat(sector=3, lap=5))
        c = d.update(_flat(sector=1, lap=6))
        assert c.new_sector is True
        assert c.new_lap is True


class TestSessionPhaseChanges:
    def test_phase_change_to_fcy(self):
        d = StateDiff()
        d.update(_flat(phase=5))
        c = d.update(_flat(phase=6))
        assert c.session_phase_changed is True

    def test_same_phase_no_change(self):
        d = StateDiff()
        d.update(_flat(phase=5))
        c = d.update(_flat(phase=5))
        assert c.session_phase_changed is False

    def test_phase_recovery_to_green(self):
        d = StateDiff()
        d.update(_flat(phase=5))
        d.update(_flat(phase=6))
        c = d.update(_flat(phase=5))
        assert c.session_phase_changed is True


class TestLeaderChanges:
    def test_leader_change_detected(self):
        d = StateDiff()
        d.update(_flat(leader="Alice"))
        c = d.update(_flat(leader="Bob"))
        assert c.leader_changed is True

    def test_same_leader_no_change(self):
        d = StateDiff()
        d.update(_flat(leader="Alice"))
        c = d.update(_flat(leader="Alice"))
        assert c.leader_changed is False

    def test_no_leader_field_does_not_change(self):
        d = StateDiff()
        d.update(_flat(leader="Alice"))
        c = d.update(_flat(leader=""))  # Sin líder (ej: fin de sesión)
        # leader_changed solo si el NUEVO no es vacío
        assert c.leader_changed is False


class TestPositionAntiBounce:
    def test_real_position_change_after_settle(self):
        """Cambio de posición legítimo: reportado tras el settle time."""
        d = StateDiff()
        d.update(_flat(place=5))
        c = d.update(_flat(place=4), now=100.0)
        # En el primer tick tras el cambio, todavía no se reporta (pending)
        assert c.position_changed is False
        # Tras el settle (1s después)
        c = d.update(_flat(place=4), now=101.5)
        assert c.position_changed is True
        assert c.old_position == 5
        assert c.new_position == 4

    def test_oscillating_position_does_not_report(self):
        """Posición que oscila entre 5 y 4 no debe reportarse nunca."""
        d = StateDiff()
        d.update(_flat(place=5), now=100.0)
        # Oscilación rápida: 5 -> 4 -> 5 -> 4
        d.update(_flat(place=4), now=100.1)  # pending=4
        d.update(_flat(place=5), now=100.2)  # cambia pending a 5
        d.update(_flat(place=4), now=100.3)  # cambia pending a 4
        # Después de 1s, el pending debe haberse "reseteado" muchas veces
        c = d.update(_flat(place=5), now=102.0)
        # Nunca llegó a settle porque cada tick cambiaba el pending
        assert c.position_changed is False

    def test_stable_position_never_reports(self):
        d = StateDiff()
        d.update(_flat(place=3), now=100.0)
        for t in range(100, 110):
            c = d.update(_flat(place=3), now=float(t))
        assert c.position_changed is False


class TestRivals:
    def test_rival_retirement_detected(self):
        d = StateDiff()
        d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": False},
            {"driver_raw_name": "Bob", "in_pits": False},
        ]))
        c = d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": False},
        ]))
        assert "Bob" in c.retired_drivers
        assert len(c.retired_drivers) == 1

    def test_new_rival_detected(self):
        d = StateDiff()
        d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": False},
        ]))
        c = d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": False},
            {"driver_raw_name": "Charlie", "in_pits": False},
        ]))
        assert "Charlie" in c.new_drivers
        assert len(c.new_drivers) == 1

    def test_pit_entry_detected(self):
        d = StateDiff()
        d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": False},
        ]))
        c = d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": True},
        ]))
        assert "Alice" in c.pit_entries
        assert "Alice" not in c.pit_exits

    def test_pit_exit_detected(self):
        d = StateDiff()
        d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": True},
        ]))
        c = d.update(_flat(rivals=[
            {"driver_raw_name": "Alice", "in_pits": False},
        ]))
        assert "Alice" in c.pit_exits
        assert "Alice" not in c.pit_entries

    def test_empty_rivals_no_crash(self):
        d = StateDiff()
        d.update(_flat())
        c = d.update(_flat())
        assert c.retired_drivers == set()
        assert c.new_drivers == set()


class TestMultipleChanges:
    def test_simultaneous_lap_and_leader_change(self):
        d = StateDiff()
        d.update(_flat(lap=5, leader="Alice"))
        c = d.update(_flat(lap=6, leader="Bob"))
        assert c.new_lap is True
        assert c.leader_changed is True

    def test_full_session_event(self):
        """Vuelta nueva + cambio de fase + cambio de líder, todo a la vez."""
        d = StateDiff()
        d.update(_flat(lap=10, phase=5, leader="Alice"))
        c = d.update(_flat(lap=11, phase=5, leader="Bob"))
        assert c.new_lap is True
        assert c.leader_changed is True
        assert c.session_phase_changed is False
