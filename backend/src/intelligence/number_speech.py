"""English number-to-speech helpers for gap, fuel, and lap time."""

from __future__ import annotations

_ZERO_TO_NINETEEN = (
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen",
)

_TENS = (
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy",
    "eighty", "ninety",
)


def _int_to_words(n: int) -> str:
    if n < 0:
        return "minus " + _int_to_words(abs(n))
    if n < 20:
        return _ZERO_TO_NINETEEN[n]
    if n < 100:
        t = _TENS[n // 10]
        r = n % 10
        return t if r == 0 else f"{t} {_ZERO_TO_NINETEEN[r]}"
    if n < 1000:
        hundreds = n // 100
        rest = n % 100
        prefix = f"{_ZERO_TO_NINETEEN[hundreds]} hundred"
        return prefix if rest == 0 else f"{prefix} {_int_to_words(rest)}"
    return str(n)


def _decimal_to_words(frac_part: str) -> str:
    return " ".join(_ZERO_TO_NINETEEN[int(d)] for d in frac_part)


def _float_to_words(value: float) -> str:
    if float(value).is_integer():
        return _int_to_words(int(value))
    whole = int(value)
    frac_part = f"{value:.3f}".split(".")[1].rstrip("0")
    if not frac_part:
        return _int_to_words(whole)
    return f"{_int_to_words(whole)} point {_decimal_to_words(frac_part)}"


def format_gap_en(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    if float(seconds).is_integer():
        s = int(seconds)
        return f"{_int_to_words(s)} second" + ("s" if s != 1 else "")
    spoken = _float_to_words(seconds)
    return f"{spoken} seconds"


def format_fuel_litres_en(litres: float) -> str:
    if float(litres).is_integer():
        l = int(litres)
        return f"{_int_to_words(l)} litre" + ("s" if l != 1 else "")
    spoken = _float_to_words(litres)
    return f"{spoken} litres"


def format_lap_time_en(seconds: float) -> str:
    if seconds <= 0:
        return "zero"
    minutes = int(seconds // 60)
    secs = seconds - minutes * 60
    parts: list[str] = []
    if minutes > 0:
        parts.append(f"{_int_to_words(minutes)} minute" + ("s" if minutes != 1 else ""))
    if float(secs).is_integer():
        s = int(secs)
        if s > 0 or not parts:
            parts.append(_int_to_words(s) + (" seconds" if s != 1 else " second"))
    else:
        spoken = _float_to_words(secs)
        parts.append(f"{spoken} seconds")
    return " ".join(parts)
