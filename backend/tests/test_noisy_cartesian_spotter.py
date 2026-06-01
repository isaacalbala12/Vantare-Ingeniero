import time
import pytest
from src.intelligence.noisy_cartesian_spotter import NoisyCartesianCoordinateSpotter


class MockAudioPlayer:
    """Mock que registra los mensajes del spotter."""
    def __init__(self):
        self.spotter_calls = []  # (audio_path, keep_channel)
        self.normal_calls = []

    def play_spotter_message(self, audio_path: str, keep_channel: bool = False):
        self.spotter_calls.append((audio_path, keep_channel))

    def play(self, name: str, priority: int = 5):
        self.normal_calls.append((name, priority))


def make_setup():
    """Helper para crear spotter y mock audio player."""
    ap = MockAudioPlayer()
    # min_speed=5 para tests con velocidades bajas
    s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0)
    return s, ap


def _state(x=100, z=100, yaw=0, speed=50):
    """Estado del piloto. NO usar (0,0) porque el spotter lo ignora."""
    return {"world_x": x, "world_z": z, "rotation_yaw": yaw, "speed_ms": speed}


def _opp(oid, x, z, speed=45):
    return {"id": oid, "world_x": x, "world_z": z, "speed": speed}


class TestBasics:
    def test_creation(self):
        s, ap = make_setup()
        assert s.cl == 0
        assert s.cr == 0
        assert s._next is None

    def test_no_action_when_parked(self):
        s, ap = make_setup()
        s.trigger(_state(speed=0), [_opp(1, 105, 105)], time.time())
        assert len(ap.spotter_calls) == 0

    def test_no_action_at_origin(self):
        s, ap = make_setup()
        s.trigger({"world_x": 0, "world_z": 0, "rotation_yaw": 0, "speed_ms": 50},
                  [_opp(1, 5, 5)], time.time())
        assert len(ap.spotter_calls) == 0


class TestCarLeft:
    def test_car_left_detected(self):
        s, ap = make_setup()
        t = 1000.0
        # Piloto en (100, 100), oponente a la izquierda mundial
        # Oponente en (98, 101) → dx=-2, dz=1, ax=-2, az=1
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        assert s.cl == 1
        assert any("car_left" in c[0] for c in ap.spotter_calls)

    def test_car_left_within_zone(self):
        s, ap = make_setup()
        t = 1000.0
        # az debe ser > 0 (delante del piloto) para ser detectado como "left"
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        assert s.cl == 1

    def test_car_outside_zone_ignored(self):
        s, ap = make_setup()
        t = 1000.0
        # Piloto en (100, 100), oponente en (130, 100) → |dx|=30 > zone=20
        s.trigger(_state(100, 100), [_opp(1, 130, 100)], t)
        assert s.cl == 0


class TestCarRight:
    def test_car_right_detected(self):
        s, ap = make_setup()
        t = 1000.0
        # Piloto en (100, 100), oponente a la derecha mundial en (102, 101)
        # → dx=2, dz=1, ax=2 (yaw=0), az=1
        s.trigger(_state(100, 100), [_opp(1, 102, 101)], t)
        assert s.cr == 1
        assert any("car_right" in c[0] for c in ap.spotter_calls)


class TestClearMessages:
    def test_clear_left_after_car_left_gone(self):
        s, ap = make_setup()
        t = 1000.0
        # Tick 1: coche a la izquierda
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        assert s.cl == 1
        # Tick 2: coche se fue
        s.trigger(_state(100, 100), [], t + 0.1)
        assert any("clear_left" in c[0] for c in ap.spotter_calls)

    def test_clear_right_after_car_right_gone(self):
        s, ap = make_setup()
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 102, 101)], t)
        s.trigger(_state(100, 100), [], t + 0.1)
        assert any("clear_right" in c[0] for c in ap.spotter_calls)

    def test_clear_all_round_when_both_gone(self):
        s, ap = make_setup()
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101), _opp(2, 102, 101)], t)
        s.trigger(_state(100, 100), [], t + 0.1)
        assert any("clear_all_round" in c[0] for c in ap.spotter_calls)


class TestStillThere:
    def test_still_there_after_car_left(self):
        s, ap = make_setup()
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t + 3.5)
        assert any("still_there" in c[0] for c in ap.spotter_calls)


class TestRepeatSuppression:
    def test_no_repeat_within_cooldown(self):
        s, ap = make_setup()
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        first_calls = len(ap.spotter_calls)
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t + 0.1)
        # En este caso pasaron 0.1s, no debe añadir más
        # (el _next ya es "still_there" pero _due es t+3.0, no se reproduce)
        assert len(ap.spotter_calls) == first_calls


class TestMaxPerSide:
    def test_max_per_side_caps_count(self):
        ap = MockAudioPlayer()
        s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0, max_per_side=2)
        t = 1000.0
        # Oponentes con az>0 (delante) para que _side los cuente
        opps = [_opp(i, 98 - i * 0.5, 101) for i in range(5)]
        s.trigger(_state(100, 100), opps, t)
        assert s.cl == 2


class TestClearState:
    def test_clear_state_resets(self):
        s, ap = make_setup()
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        assert s.cl == 1
        s.clear_state()
        assert s.cl == 0
        assert s.cr == 0
        assert s._next is None
        assert s._v == {}


class TestGridSide:
    def test_grid_side_left(self):
        s, ap = make_setup()
        side = s.get_grid_side(0, 100, 100, [_opp(1, 97, 105)])
        assert side == "LEFT"

    def test_grid_side_right(self):
        s, ap = make_setup()
        side = s.get_grid_side(0, 100, 100, [_opp(1, 103, 105)])
        assert side == "RIGHT"

    def test_grid_side_unknown(self):
        s, ap = make_setup()
        side = s.get_grid_side(0, 100, 100, [])
        assert side == "UNKNOWN"


class TestEdgeCases:
    def test_no_audio_player_doesnt_crash(self):
        s = NoisyCartesianCoordinateSpotter(ap=None, min_speed=5, clear_delay=0)
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        s.trigger(_state(100, 100), [], t + 0.1)

    def test_audio_player_without_play_spotter_fallback(self):
        """Si ap no tiene play_spotter_message, usar play() normal."""
        class OldAudioPlayer:
            def __init__(self):
                self.calls = []
            def play(self, name, priority=5):
                self.calls.append((name, priority))
        ap = OldAudioPlayer()
        s = NoisyCartesianCoordinateSpotter(ap=ap, min_speed=5, clear_delay=0)
        t = 1000.0
        s.trigger(_state(100, 100), [_opp(1, 98, 101)], t)
        assert len(ap.calls) > 0
        assert ap.calls[0][1] == 20  # SPOTTER priority
