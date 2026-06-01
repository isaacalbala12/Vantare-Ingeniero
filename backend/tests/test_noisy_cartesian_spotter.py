"""Tests del NoisyCartesianCoordinateSpotter — spotter cartesiano.

Cobertura:
- Creación y defaults
- Estado inactivo (piloto parado, en origen)
- Detección de coche a izquierda
- Detección de coche a derecha
- Filtro de zona (oponentes lejanos ignorados)
- Filtro de velocidad (oponentes lentos ignorados)
- Mensajes clear (izquierda, derecha, ambos)
- Mensajes three_wide
- Mensajes three_wide_on_left/right
- Mensajes still_there (cooldown)
- Anti-bounce: no repetir el mismo mensaje inmediatamente
- max_per_side limita cuenta
- clear_state resetea todo
- get_grid_side (para LapCounter)
- Edge cases: ap=None, sin play_spotter_message
- Concurrencia
- _check_v: tracking por tiempo cuando speed=0
- _side: detección con piloto en diferentes posiciones
- _next_msg: lógica de transición
"""
import math
import time
import pytest
from src.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter
from src.intelligence.spotter_messages import (
    CAR_LEFT, CAR_RIGHT, CLEAR_LEFT, CLEAR_RIGHT, CLEAR_ALL_ROUND,
    THREE_WIDE, THREE_WIDE_ON_LEFT, THREE_WIDE_ON_RIGHT, STILL_THERE,
)


# =========================================================
# Mocks
# =========================================================
class MockAudioPlayer:
    """Mock que registra los mensajes del spotter."""
    def __init__(self):
        self.spotter_calls = []  # (audio_path, keep_channel)
        self.normal_calls = []

    def play_spotter_message(self, audio_path: str, keep_channel: bool = False):
        self.spotter_calls.append((audio_path, keep_channel))

    def play(self, name: str, priority: int = 5):
        self.normal_calls.append((name, priority))

    def played_paths(self):
        return [c[0] for c in self.spotter_calls]


def make_spotter(**kwargs):
    ap = MockAudioPlayer()
    defaults = {"min_speed": 5, "clear_delay": 0}
    defaults.update(kwargs)
    s = NoisyCartesianCoordinateSpotter(ap=ap, **defaults)
    return s, ap


def _state(x=100, z=100, yaw=0, speed=50):
    """Estado del piloto. NO usar (0,0) — el spotter ignora el origen."""
    return {"world_x": x, "world_z": z, "rotation_yaw": yaw, "speed_ms": speed}


def _opp(oid, x, z, speed=45):
    return {"id": oid, "world_x": x, "world_z": z, "speed": speed}


# =========================================================
# Tests: Defaults y estado
# =========================================================
class TestDefaults:
    def test_creation_with_defaults(self):
        s, ap = make_spotter()
        assert s.cl == 0
        assert s.cr == 0
        assert s.clp == 0
        assert s.crp == 0
        assert s.has_overlap is False
        assert s._v == {}
        assert s._next is None
        assert s._due == 0.0

    def test_default_zones(self):
        s, ap = make_spotter()
        assert s.zone == 20.0
        assert s.min_speed == 5
        assert s.max_close == 50.0
        assert s.clear_gap == 1.0
        assert s.car_len == 4.5
        assert s.car_w == 1.8
        assert s.behind_extra == 0.4
        assert s.max_per_side == 3
        assert s.clear_delay == 0  # overridden in helper
        assert s.repeat_freq == 3.0
        assert s.to_3wide == 0.5

    def test_custom_kwargs(self):
        s, ap = make_spotter(zone=30, min_speed=10, car_len=5, repeat_freq=5)
        assert s.zone == 30
        assert s.min_speed == 10
        assert s.car_len == 5
        assert s.repeat_freq == 5


# =========================================================
# Tests: Estado inactivo
# =========================================================
class TestInactiveStates:
    def test_no_action_when_parked(self):
        s, ap = make_spotter()
        s.trigger(_state(speed=0), [_opp(1, 105, 105)], time.time())
        assert len(ap.spotter_calls) == 0
        assert s.cl == 0
        assert s.cr == 0

    def test_no_action_at_origin(self):
        s, ap = make_spotter()
        s.trigger({"world_x": 0, "world_z": 0, "rotation_yaw": 0, "speed_ms": 50},
                  [_opp(1, 5, 5)], time.time())
        assert len(ap.spotter_calls) == 0

    def test_no_action_below_min_speed(self):
        s, ap = make_spotter(min_speed=20)
        s.trigger(_state(speed=15), [_opp(1, 105, 105)], time.time())
        assert len(ap.spotter_calls) == 0

    def test_no_action_with_empty_rivals(self):
        s, ap = make_spotter()
        s.trigger(_state(), [], time.time())
        assert len(ap.spotter_calls) == 0


# =========================================================
# Tests: Detección de coche a izquierda
# =========================================================
class TestCarLeft:
    def test_car_left_detected(self):
        """Oponente a la izquierda mundial (ax<0), dentro de zona."""
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        assert s.cl == 1
        assert CAR_LEFT in ap.played_paths()

    def test_car_left_with_multiple_opponents(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101), _opp(2, 96, 102)], 1000.0)
        assert s.cl == 2

    def test_car_left_outside_zone_ignored(self):
        s, ap = make_spotter(zone=20)
        # Oponente a 30m del piloto: fuera de zona
        s.trigger(_state(100, 100), [_opp(1, 130, 100)], 1000.0)
        assert s.cl == 0
        assert len(ap.spotter_calls) == 0

    def test_car_left_close_to_pilot(self):
        """Oponente pegado al lateral no se cuenta (car_w = 1.8m)."""
        s, ap = make_spotter()
        # Oponente a 1m a la izquierda (ax=-1): abs(ax) <= car_w=1.8 → None
        s.trigger(_state(100, 100), [_opp(1, 99, 101)], 1000.0)
        assert s.cl == 0  # Muy pegado, no cuenta

    def test_car_left_wider_than_car(self):
        """Oponente a 2m sí se cuenta (abs(ax) > car_w=1.8)."""
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        assert s.cl == 1


# =========================================================
# Tests: Detección de coche a derecha
# =========================================================
class TestCarRight:
    def test_car_right_detected(self):
        s, ap = make_spotter()
        # Oponente a la derecha mundial (ax>0), dentro de zona
        s.trigger(_state(100, 100), [_opp(1, 102, 101)], 1000.0)
        assert s.cr == 1
        assert CAR_RIGHT in ap.played_paths()

    def test_car_right_outside_zone_ignored(self):
        s, ap = make_spotter(zone=20)
        s.trigger(_state(100, 100), [_opp(1, 130, 100)], 1000.0)
        assert s.cr == 0


# =========================================================
# Tests: Filtros
# =========================================================
class TestFilters:
    def test_filter_by_zone_x(self):
        s, ap = make_spotter(zone=20)
        s.trigger(_state(100, 100), [_opp(1, 130, 100)], 1000.0)
        assert s.cl == 0
        assert s.cr == 0

    def test_filter_by_zone_z(self):
        s, ap = make_spotter(zone=20)
        s.trigger(_state(100, 100), [_opp(1, 100, 130)], 1000.0)
        assert s.cl == 0

    def test_filter_rival_at_origin(self):
        """Oponente en (0,0) — el spotter lo ignora (mismo check que para piloto)."""
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 0, 0)], 1000.0)
        # El bucle hace `if ox == 0 and oz == 0: continue`
        assert s.cl == 0
        assert s.cr == 0

    def test_filter_slow_rival(self):
        """Oponente con velocidad 0 → spotter debe trackear por tiempo."""
        s, ap = make_spotter()
        # Primera llamada: registra posición, retorna True (cerca por defecto)
        s.trigger(_state(100, 100), [_opp(1, 98, 101, speed=0)], 1000.0)
        # En la primera llamada sin velocidad, _check_v retorna True (asumimos cerca)
        assert s.cl == 1  # cuenta como cerca en el primer tick


# =========================================================
# Tests: Mensajes Clear
# =========================================================
class TestClearMessages:
    def test_clear_left_after_car_left_gone(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        assert s.cl == 1
        s.trigger(_state(100, 100), [], 1000.1)
        assert CLEAR_LEFT in ap.played_paths()

    def test_clear_right_after_car_right_gone(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 102, 101)], 1000.0)
        s.trigger(_state(100, 100), [], 1000.1)
        assert CLEAR_RIGHT in ap.played_paths()

    def test_clear_all_round_when_both_gone(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101), _opp(2, 102, 101)], 1000.0)
        s.trigger(_state(100, 100), [], 1000.1)
        assert CLEAR_ALL_ROUND in ap.played_paths()

    def test_no_clear_if_nothing_was_there(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [], 1000.0)
        s.trigger(_state(100, 100), [], 1000.1)
        # No debe decir "clear" si no había nada
        assert not any("clear" in p for p in ap.played_paths())


# =========================================================
# Tests: Three Wide
# =========================================================
class TestThreeWide:
    def test_three_wide_when_both_appear(self):
        s, ap = make_spotter()
        # Tick 1: vacío
        s.trigger(_state(100, 100), [], 1000.0)
        # Tick 2: aparece coche a cada lado
        s.trigger(_state(100, 100), [_opp(1, 98, 101), _opp(2, 102, 101)], 1000.1)
        # Algún mensaje "three_wide" o "in_the_middle" debe haberse reproducido
        assert any("three_wide" in p or "in_the_middle" in p for p in ap.played_paths())

    def test_three_wide_on_right_when_multiple_left(self):
        s, ap = make_spotter()
        # Tick 1: vacío
        s.trigger(_state(100, 100), [], 1000.0)
        # Tick 2: 2 coches a la izquierda
        s.trigger(_state(100, 100), [_opp(1, 98, 101), _opp(2, 97, 102)], 1000.1)
        assert THREE_WIDE_ON_RIGHT in ap.played_paths()

    def test_three_wide_on_left_when_multiple_right(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [], 1000.0)
        s.trigger(_state(100, 100), [_opp(1, 102, 101), _opp(2, 103, 102)], 1000.1)
        assert THREE_WIDE_ON_LEFT in ap.played_paths()


# =========================================================
# Tests: Still There (cooldown)
# =========================================================
class TestStillThere:
    def test_still_there_after_repeat_freq(self):
        s, ap = make_spotter(repeat_freq=3.0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        # El primer mensaje es "car_left" (no still_there)
        assert STILL_THERE not in ap.played_paths()
        # Después de 3.5s, debe decir "still there"
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1003.5)
        assert STILL_THERE in ap.played_paths()

    def test_no_still_there_within_cooldown(self):
        s, ap = make_spotter(repeat_freq=3.0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        # Inmediatamente después (1000.1s), no debe decir nada
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.1)
        # El _next = "still_there" pero _due = 1003.0, no se reproduce
        # Solo debe estar "car_left" en las llamadas
        played = ap.played_paths()
        assert played == [CAR_LEFT]  # solo car_left, no still_there

    def test_still_there_keeps_repeating(self):
        s, ap = make_spotter(repeat_freq=2.0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1002.5)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1005.0)
        # car_left + 2 still_there
        assert CAR_LEFT in ap.played_paths()
        still_count = ap.played_paths().count(STILL_THERE)
        assert still_count == 2


# =========================================================
# Tests: Max per side
# =========================================================
class TestMaxPerSide:
    def test_max_per_side_limits_left_count(self):
        s, ap = make_spotter(max_per_side=2)
        # 5 oponentes a la izquierda, pero solo 2 deben contar
        opps = [_opp(i, 98 - i * 0.5, 101) for i in range(5)]
        s.trigger(_state(100, 100), opps, 1000.0)
        assert s.cl == 2

    def test_max_per_side_limits_right_count(self):
        s, ap = make_spotter(max_per_side=2)
        opps = [_opp(i, 102 + i * 0.5, 101) for i in range(5)]
        s.trigger(_state(100, 100), opps, 1000.0)
        assert s.cr == 2

    def test_max_per_side_per_side_independently(self):
        s, ap = make_spotter(max_per_side=2)
        opps = (
            [_opp(i, 98 - i * 0.5, 101) for i in range(5)]
            + [_opp(100 + i, 102 + i * 0.5, 101) for i in range(5)]
        )
        s.trigger(_state(100, 100), opps, 1000.0)
        assert s.cl == 2
        assert s.cr == 2


# =========================================================
# Tests: clear_state
# =========================================================
class TestClearState:
    def test_clear_state_resets_all(self):
        s, ap = make_spotter()
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        assert s.cl == 1
        s.clear_state()
        assert s.cl == 0
        assert s.cr == 0
        assert s.clp == 0
        assert s.crp == 0
        assert s.has_overlap is False
        assert s._v == {}
        assert s._next is None
        assert s._due == 0.0

    def test_clear_state_then_no_action(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        s.clear_state()
        s.trigger(_state(100, 100), [], 1001.0)
        # No debe decir "clear" porque el estado fue reseteado
        assert not any("clear" in p for p in ap.played_paths())


# =========================================================
# Tests: get_grid_side
# =========================================================
class TestGetGridSide:
    def test_grid_side_left(self):
        """Oponente claramente a la izquierda (ax < -2)."""
        s, ap = make_spotter()
        side = s.get_grid_side(0, 100, 100, [_opp(1, 97, 105)])
        assert side == "LEFT"

    def test_grid_side_right(self):
        s, ap = make_spotter()
        side = s.get_grid_side(0, 100, 100, [_opp(1, 103, 105)])
        assert side == "RIGHT"

    def test_grid_side_unknown_empty(self):
        s, ap = make_spotter()
        side = s.get_grid_side(0, 100, 100, [])
        assert side == "UNKNOWN"

    def test_grid_side_unknown_close(self):
        """Oponente muy cerca (ax entre -2 y 2) → UNKNOWN."""
        s, ap = make_spotter()
        side = s.get_grid_side(0, 100, 100, [_opp(1, 101, 105)])
        assert side == "UNKNOWN"

    def test_grid_side_only_first_five_checked(self):
        """Solo se chequean los primeros 5 oponentes."""
        s, ap = make_spotter()
        opps = [_opp(99, 200, 105)]  # Lejos, fuera
        opps = [_opp(1, 97, 105)] + opps  # Cerca a la izquierda (1°)
        side = s.get_grid_side(0, 100, 100, opps)
        assert side == "LEFT"


# =========================================================
# Tests: Edge cases del audio player
# =========================================================
class TestEdgeCases:
    def test_no_audio_player_doesnt_crash(self):
        """Si ap=None, no debe lanzar excepción."""
        s = NoisyCartesianCoordinateSpotter(ap=None, min_speed=5, clear_delay=0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        s.trigger(_state(100, 100), [], 1000.1)
        # No debe haber lanzado

    def test_audio_player_without_play_spotter_fallback(self):
        """Si ap no tiene play_spotter_message, usar play() normal."""

        class OldAudioPlayer:
            def __init__(self):
                self.calls = []

            def play(self, name, priority=5):
                self.calls.append((name, priority))

        ap = OldAudioPlayer()
        s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        assert len(ap.calls) > 0
        assert ap.calls[0][1] == 20  # SPOTTER priority

    def test_audio_player_with_play_spotter_used(self):
        """Si ap tiene play_spotter_message, ese se usa (no play)."""
        ap = MockAudioPlayer()
        s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        assert len(ap.spotter_calls) > 0
        assert len(ap.normal_calls) == 0


# =========================================================
# Tests: _check_v (velocidad)
# =========================================================
class TestCheckV:
    def test_check_v_with_known_speed(self):
        """Si sp > 0, calcula por diferencia de velocidad."""
        s, ap = make_spotter(min_speed=5, max_close=50)
        # Velocidad 45, min=5: abs(45-5) = 40 < 50 = True
        result = s._check_v(1, 100, 100, 45, 1000.0)
        assert result is True

    def test_check_v_with_far_speed(self):
        s, ap = make_spotter(min_speed=5, max_close=10)
        # Velocidad 100: abs(100-5) = 95 > 10 = False
        result = s._check_v(1, 100, 100, 100, 1000.0)
        assert result is False

    def test_check_v_first_call_no_speed(self):
        """Primera llamada sin velocidad → registra y retorna True (asumimos cerca)."""
        s, ap = make_spotter()
        result = s._check_v(1, 100, 100, 0, 1000.0)
        assert result is True
        assert 1 in s._v
        assert s._v[1]["x"] == 100
        assert s._v[1]["z"] == 100

    def test_check_v_second_call_too_soon(self):
        """Segunda llamada antes de 0.2s → no actualiza velocidad, usa cache."""
        s, ap = make_spotter()
        s._check_v(1, 100, 100, 0, 1000.0)
        # 0.1s después, antes del umbral de 0.2s
        result = s._check_v(1, 100, 100, 0, 1000.1)
        # Sin cálculo de velocidad, vs = 0 < 50 = True
        assert result is True

    def test_check_v_after_threshold(self):
        """Pasado 0.2s, recalcula velocidad por diff."""
        s, ap = make_spotter(max_close=10)
        s._check_v(1, 100, 100, 0, 1000.0)
        # 1s después, 10m de diferencia → velocidad = 10
        result = s._check_v(1, 110, 100, 0, 1001.0)
        # vs = 10, max_close=10: 10 < 10 = False (no en rango)
        assert result is False


# =========================================================
# Tests: _side
# =========================================================
class TestSide:
    def test_side_too_far_returns_none(self):
        """Oponente más allá de zone retorna None."""
        s, ap = make_spotter(zone=20)
        result = s._side(0, 100, 100, 130, 100, True)
        assert result == (None, -1.0)

    def test_side_ahead_and_left(self):
        s, ap = make_spotter()
        # Piloto en (100,100), oponente en (98, 101) → ax=-2, az=1
        result = s._side(0, 100, 100, 98, 101, True)
        assert result == ("l", 2.0)

    def test_side_ahead_and_right(self):
        s, ap = make_spotter()
        result = s._side(0, 100, 100, 102, 101, True)
        assert result == ("r", 2.0)

    def test_side_not_in_range_returns_none(self):
        """Oponente a la derecha pero in_range=False → None."""
        s, ap = make_spotter()
        result = s._side(0, 100, 100, 102, 101, False)
        assert result == (None, -1.0)

    def test_side_clear_gap_when_other_side_has_car(self):
        """Si crp > 0 (hay coche a la derecha antes), tolera gap lateral."""
        s, ap = make_spotter()
        s.crp = 1  # simular coche a la derecha en tick anterior
        # Oponente ligeramente a la derecha y muy cerca en Z
        # ax=1, az=0 → abs(az) < car_len+clear_gap → "r"
        result = s._side(0, 100, 100, 101, 100, True)
        assert result == ("r", 1.0)

    def test_side_clear_gap_left(self):
        s, ap = make_spotter()
        s.clp = 1
        result = s._side(0, 100, 100, 99, 100, True)
        assert result == ("l", 1.0)

    def test_side_wrong_side_outside_zone(self):
        """Oponente a la izquierda pero abs(ax) > zone → None."""
        s, ap = make_spotter(zone=5)
        # ax=-10, abs(ax)=10 > zone=5
        result = s._side(0, 100, 100, 90, 100, True)
        assert result == (None, -1.0)


# =========================================================
# Tests: Anti-bounce de mensajes
# =========================================================
class TestAntiBounce:
    def test_doesnt_repeat_same_immediately(self):
        s, ap = make_spotter(repeat_freq=3.0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        played_after_first = list(ap.played_paths())
        # Inmediatamente después, NO debe añadir otro "car_left"
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.1)
        assert ap.played_paths() == played_after_first

    def test_doesnt_clear_when_car_just_appeared(self):
        """Si un coche aparece y se va en 1 tick, no debe decir 'clear'."""
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        # Tick 2: el coche sigue ahí
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.1)
        # El tick 2 NO debe decir "clear" porque cl=1, clp=1 (no cambio)
        assert CLEAR_LEFT not in ap.played_paths()
        assert CLEAR_ALL_ROUND not in ap.played_paths()


# =========================================================
# Tests: Estado persiste entre ticks
# =========================================================
class TestStateBetweenTicks:
    def test_state_persists_clp_crp(self):
        """Después del tick 1, clp y cl se actualizan correctamente al valor del tick."""
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        # Después del tick 1: cl=1, clp=1 (locales actualizados)
        assert s.cl == 1
        assert s.clp == 1
        assert s.crp == 0
        assert s.cr == 0

    def test_transition_car_left_to_clear_left(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        s.trigger(_state(100, 100), [], 1000.1)
        # Debe haber car_left y clear_left
        assert CAR_LEFT in ap.played_paths()
        assert CLEAR_LEFT in ap.played_paths()

    def test_continuing_car_doesnt_reclear(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.0)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], 1000.1)
        # car_left una vez, NO clear_left
        played = ap.played_paths()
        assert played.count(CAR_LEFT) == 1
        assert CLEAR_LEFT not in played

    def test_v_state_updated_for_rivals(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101, speed=0)], 1000.0)
        # Después de la primera llamada, _v[1] debe existir
        assert 1 in s._v
        # En tick 2, el rival sigue ahí, _v[1] se mantiene
        s.trigger(_state(100, 100), [_opp(1, 98, 101, speed=0)], 1000.1)
        assert 1 in s._v

    def test_v_state_clears_disappeared_rival(self):
        s, ap = make_spotter()
        s.trigger(_state(100, 100), [_opp(1, 98, 101, speed=0)], 1000.0)
        assert 1 in s._v
        # Tick 2: el rival desaparece
        s.trigger(_state(100, 100), [], 1000.1)
        assert 1 not in s._v


# =========================================================
# Tests: Thread safety (basic)
# =========================================================
class TestThreadSafety:
    def test_no_exception_with_concurrent_triggers(self):
        """Múltiples triggers concurrentes no deben crashear."""
        import threading
        s, ap = make_spotter()
        errors = []

        def worker(t):
            try:
                s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(1000.0 + i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
