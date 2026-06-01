"""Lectura coloquial de la hora. Ej: "las tres y cuarto", "las diez menos diez".

Interfaz extensible: crear subclase de ColloquialTimeReader para otros idiomas.
"""

from typing import Optional


class ColloquialTimeReader:
    """Base class para lectores de hora coloquial. Extensible por idioma."""

    def to_colloquial(self, hour: int, minute: int) -> str:
        raise NotImplementedError


class SpanishColloquialTimeReader(ColloquialTimeReader):
    """Ej: (15, 0) -> "las tres en punto", (10, 30) -> "las diez y media"."""

    _MINUTES = {
        1: "uno", 2: "dos", 3: "tres", 4: "cuatro", 5: "cinco",
        6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez",
        11: "once", 12: "doce", 13: "trece", 14: "catorce", 15: "cuarto",
        16: "dieciseis", 17: "diecisiete", 18: "dieciocho", 19: "diecinueve",
        20: "veinte", 21: "veintiuno", 22: "veintidos", 23: "veintitres",
        24: "veinticuatro", 25: "veinticinco", 26: "veintiseis",
        27: "veintisiete", 28: "veintiocho", 29: "veintinueve",
        30: "media",
    }

    _HOURS = {
        0: "doce", 1: "una", 2: "dos", 3: "tres", 4: "cuatro",
        5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve",
        10: "diez", 11: "once", 12: "doce", 13: "una", 14: "dos",
        15: "tres", 16: "cuatro", 17: "cinco", 18: "seis", 19: "siete",
        20: "ocho", 21: "nueve", 22: "diez", 23: "once",
    }

    def to_colloquial(self, hour: int, minute: int) -> str:
        hour = hour % 24
        if hour == 0 and minute == 0:
            return "medianoche"
        if hour == 12 and minute == 0:
            return "mediodía"

        hour_str = self._HOURS.get(hour, str(hour))

        if minute == 0:
            article = "la" if hour in (1, 13) else "las"
            return f"{article} {hour_str} en punto"

        if minute == 15:
            article = "la" if hour in (1, 13) else "las"
            return f"{article} {hour_str} y cuarto"

        if minute == 30:
            article = "la" if hour in (1, 13) else "las"
            return f"{article} {hour_str} y media"

        if minute < 30:
            article = "la" if hour in (1, 13) else "las"
            minute_str = self._MINUTES.get(minute, str(minute))
            return f"{article} {hour_str} y {minute_str}"

        # minutos > 30: "las X menos Y"
        next_hour = (hour + 1) % 24
        next_str = self._HOURS.get(next_hour, str(next_hour))
        remaining = 60 - minute
        remaining_str = self._MINUTES.get(remaining, str(remaining))
        article = "la" if next_hour in (1, 13) else "las"
        return f"{article} {next_str} menos {remaining_str}"
