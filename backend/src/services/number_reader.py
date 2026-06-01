"""Lectura de números y tiempos en voz alta. Interfaz extensible por idioma.

Precisiones disponibles:
    AUTO_LAPTIMES, AUTO_GAPS, SECONDS, TENTHS, HUNDREDTHS, MINUTES

Uso:
    reader = SpanishNumberReader()
    reader.read_integer(42)        # "cuarenta y dos"
    reader.read_time(90.5)         # "uno, treinta punto cinco" o "1:30.5"
"""

from typing import Optional


class NumberReader:
    """Base class para lectores de números. Extensible por idioma."""

    def read_integer(self, n: int) -> str:
        raise NotImplementedError

    def read_time(self, seconds: float, precision: str = "AUTO_LAPTIMES") -> str:
        raise NotImplementedError

    def read_gap(self, seconds: float) -> str:
        raise NotImplementedError


PRECISION_AUTO_LAPTIMES = "AUTO_LAPTIMES"
PRECISION_AUTO_GAPS = "AUTO_GAPS"
PRECISION_SECONDS = "SECONDS"
PRECISION_TENTHS = "TENTHS"
PRECISION_HUNDREDTHS = "HUNDREDTHS"
PRECISION_MINUTES = "MINUTES"


class SpanishNumberReader(NumberReader):
    """Números en castellano. Soporta 0-999, negativos, tiempos y gaps."""

    _UNITS = [
        "cero", "uno", "dos", "tres", "cuatro", "cinco",
        "seis", "siete", "ocho", "nueve",
    ]
    _TEENS = [
        "diez", "once", "doce", "trece", "catorce", "quince",
        "dieciséis", "diecisiete", "dieciocho", "diecinueve",
    ]
    _TENS = [
        "", "", "veinte", "treinta", "cuarenta", "cincuenta",
        "sesenta", "setenta", "ochenta", "noventa",
    ]
    _HUNDREDS = [
        "", "cien", "doscientos", "trescientos", "cuatrocientos",
        "quinientos", "seiscientos", "setecientos", "ochocientos",
        "novecientos",
    ]

    def read_integer(self, n: int) -> str:
        if n < 0:
            return f"menos {self.read_integer(-n)}"
        if n == 0:
            return "cero"
        if n < 10:
            return self._UNITS[n]
        if n < 20:
            return self._TEENS[n - 10]
        if n < 100:
            ten = n // 10
            unit = n % 10
            if unit == 0:
                return self._TENS[ten]
            if ten == 2:
                return f"veinti{self._UNITS[unit]}"
            return f"{self._TENS[ten]} y {self._UNITS[unit]}"
        if n < 1000:
            hundred = n // 100
            rest = n % 100
            base = self._HUNDREDS[hundred] if hundred < len(self._HUNDREDS) else str(hundred)
            if rest == 0:
                return base
            return f"{base} {self.read_integer(rest)}"
        return str(n)

    def read_time(self, seconds: float, precision: str = PRECISION_AUTO_LAPTIMES) -> str:
        if seconds < 0:
            return f"menos {self.read_time(-seconds, precision)}"

        mins = int(seconds // 60)
        secs = seconds % 60

        if precision == PRECISION_MINUTES:
            if mins == 1:
                return "un minuto"
            return f"{self.read_integer(mins)} minutos"

        if precision == PRECISION_TENTHS:
            tenths = round(secs * 10)
            return f"{self.read_integer(tenths)} décimas"

        if precision == PRECISION_SECONDS:
            return f"{self.read_integer(int(round(secs)))} segundos"

        if precision == PRECISION_HUNDREDTHS:
            hundredths = int(round(secs * 100))
            return f"{self.read_integer(hundredths)} centésimas"

        if precision == PRECISION_AUTO_GAPS:
            if mins > 0:
                return self.read_time(seconds, PRECISION_MINUTES)
            if secs >= 10:
                return f"{self.read_integer(int(secs))} segundos"
            tenths = int(round(secs * 10))
            return f"{self.read_integer(tenths)} décimas"

        # AUTO_LAPTIMES (default): "uno, treinta y dos, cuatrocientos cincuenta"
        ms = int(round((secs - int(secs)) * 1000))
        if mins > 0:
            if ms > 0:
                return f"{self.read_integer(mins)}, {self.read_time(secs, PRECISION_HUNDREDTHS)} {ms}"
            return f"{self.read_integer(mins)}, {self.read_time(secs, PRECISION_HUNDREDTHS)}"
        if secs >= 1:
            return f"{self.read_integer(int(secs))}, {self.read_integer(ms)}"
        return f"cero, {self.read_integer(ms)}"

    def read_gap(self, seconds: float) -> str:
        if seconds < 0:
            return f"menos {self.read_gap(-seconds)}"
        if seconds >= 60:
            mins = int(seconds // 60)
            secs = seconds % 60
            return f"{self.read_time(mins, PRECISION_MINUTES)} {self.read_gap(secs)}"
        if seconds >= 10:
            return f"{self.read_integer(int(round(seconds)))} segundos"
        tenths = int(round(seconds * 10))
        return f"{self.read_integer(tenths)} décimas"
