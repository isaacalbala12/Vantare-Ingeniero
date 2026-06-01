import math
import random
import time
from typing import Callable, Optional


_SEED: Optional[int] = None


def set_random_seed(seed: int) -> None:
    global _SEED
    _SEED = seed
    random.seed(seed)


def random_int(min_val: int, max_val: int) -> int:
    return random.randint(min_val, max_val)


def random_double() -> float:
    return random.random()


def WholeAndFractionalPart(value: float, decimal_places: int = 2) -> tuple:
    factor = 10.0 ** decimal_places
    scaled = round(value * factor)
    whole = int(scaled // factor)
    fractional = int(scaled % factor)
    if fractional < 0:
        fractional = abs(fractional)
    return (whole, fractional)


def InterruptedSleep(
    duration: float,
    interrupt_check: Optional[Callable[[], bool]] = None,
    step: float = 0.1,
) -> bool:
    end = time.time() + duration
    while time.time() < end:
        if interrupt_check and interrupt_check():
            return True
        remaining = end - time.time()
        time.sleep(min(step, remaining))
    return False
