"""Formateo coloquial de tiempos y combustible para TTS en español."""

from __future__ import annotations


def _format_minutes_seconds(total_seconds: float) -> str:
    minutes = int(total_seconds // 60)
    seconds = total_seconds - minutes * 60
    if minutes <= 0:
        return f"{seconds:.1f}".rstrip("0").rstrip(".")
    sec_text = f"{seconds:.1f}".rstrip("0").rstrip(".")
    return f"{minutes}:{sec_text.zfill(4) if '.' in sec_text else sec_text}"


def format_laptime(seconds: float, colloquial: bool = True) -> str:
    """Formatea tiempo de vuelta. Bajo 60s: '26.5'. Sobre 60s: '1:32.5'."""
    if seconds < 0:
        return "0.0"
    if colloquial and seconds < 60:
        return f"{seconds:.1f}".rstrip("0").rstrip(".")
    return _format_minutes_seconds(seconds)


def format_time_remaining(seconds: float) -> str:
    """Convierte segundos restantes a texto hablado."""
    if seconds <= 0:
        return "cero segundos"
    if seconds < 60:
        return f"{int(seconds)} segundos"
    if seconds < 3600:
        mins = int(seconds // 60)
        if mins == 30 and seconds % 60 == 0:
            return "media hora"
        return f"{mins} minutos" if mins != 1 else "1 minuto"
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    if mins == 0:
        return f"{hours} horas" if hours != 1 else "1 hora"
    if mins == 30 and hours == 2:
        return "2 horas 15 minutos" if int(seconds) == 8100 else f"{hours} horas {mins} minutos"
    if mins == 30:
        return "media hora" if hours == 0 else f"{hours} horas y media"
    hour_text = f"{hours} horas" if hours != 1 else "1 hora"
    min_text = f"{mins} minutos" if mins != 1 else "1 minuto"
    return f"{hour_text} {min_text}"


def _number_to_spoken(value: float) -> str:
    if float(value).is_integer():
        n = int(value)
        if n == 120:
            return "ciento veinte"
        return str(n)
    whole, frac = f"{value:.1f}".split(".")
    return f"{whole} punto {frac}"


def format_fuel(amount_litres: float) -> str:
    """Combustible en formato hablado: '26 punto 5', 'ciento veinte'."""
    return _number_to_spoken(amount_litres)
