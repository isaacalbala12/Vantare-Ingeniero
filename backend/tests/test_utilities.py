import pytest
import time
from threading import Thread
from src.services.utilities import (
    random_int,
    random_double,
    WholeAndFractionalPart,
    InterruptedSleep,
    set_random_seed,
)


class TestRandom:
    def test_random_int_range(self):
        v = random_int(1, 6)
        assert 1 <= v <= 6

    def test_random_double_bounds(self):
        v = random_double()
        assert 0.0 <= v < 1.0

    def test_seed_reproducibility(self):
        set_random_seed(42)
        a = [random_int(1, 100) for _ in range(5)]
        set_random_seed(42)
        b = [random_int(1, 100) for _ in range(5)]
        assert a == b


class TestWholeAndFractionalPart:
    def test_simple_value(self):
        whole, frac = WholeAndFractionalPart(3.5, 1)
        assert whole == 3
        assert frac == 5

    def test_negative(self):
        w, f = WholeAndFractionalPart(-2.75, 2)
        assert w == -2
        assert f == 75

    def test_integer(self):
        w, f = WholeAndFractionalPart(42.0, 1)
        assert w == 42
        assert f == 0

    def test_default_decimal_places(self):
        w, f = WholeAndFractionalPart(1.234)
        assert w == 1
        assert f == 23


class TestInterruptedSleep:
    def test_sleep_full(self):
        start = time.time()
        InterruptedSleep(0.2)
        elapsed = time.time() - start
        assert elapsed >= 0.18

    def test_interrupted(self):
        flag = [False]
        def interrupt():
            return flag[0]

        def set_flag():
            time.sleep(0.05)
            flag[0] = True

        t = Thread(target=set_flag)
        t.start()
        start = time.time()
        InterruptedSleep(2.0, interrupt_check=interrupt)
        elapsed = time.time() - start
        assert elapsed < 0.5
        t.join()
