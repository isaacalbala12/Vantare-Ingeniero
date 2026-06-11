"""Perlas de sabiduría predefinidas — baja latencia, sin LLM."""

from __future__ import annotations

import random
from enum import StrEnum


class PearlType(StrEnum):
    STANDARD = "standard"
    COMEBACK = "comeback"
    FAST_LAP = "fast_lap"
    OVERTAKE = "overtake"


_PEARLS_CLEAN: dict[PearlType, list[str]] = {
    PearlType.STANDARD: [
        "Sigue así, ritmo sólido.",
        "Buen trabajo, mantén el foco.",
        "Tranquilo, la carrera es larga.",
    ],
    PearlType.COMEBACK: [
        "Remontada en marcha, no sueltes.",
        "Estás recuperando posiciones, dale caña.",
        "Vuelta a vuelta, esto se da la vuelta.",
    ],
    PearlType.FAST_LAP: [
        "¡Vuelta rápida! Ese ritmo es oro.",
        "Personal best, eso es confianza.",
        "Vuelta espectacular, apunta ese sector.",
    ],
    PearlType.OVERTAKE: [
        "Adelantamiento limpio, bien hecho.",
        "Posición ganada, ahora hay que defender.",
        "Bien jugado, sigue presionando.",
    ],
}

_PEARLS_SWEARY: dict[PearlType, list[str]] = {
    PearlType.STANDARD: [
        "Así se conduce, jefe.",
        "Eso es ritmo de podio, no aflojes.",
    ],
    PearlType.COMEBACK: [
        "Remontada de las buenas, dale gas.",
        "Les estás metiendo miedo, sigue.",
    ],
    PearlType.FAST_LAP: [
        "¡Hostia, qué vuelta! Eso es volar.",
        "Vuelta de infarto, guarda ese setup.",
    ],
    PearlType.OVERTAKE: [
        "Le has enseñado los dientes, perfecto.",
        "Adelantamiento de manual, colega.",
    ],
}


class PearlsService:
    MAX_PER_RACE = 2

    def __init__(self) -> None:
        self._count = 0
        self._index: dict[PearlType, int] = {t: 0 for t in PearlType}

    def reset_race(self) -> None:
        self._count = 0
        self._index = {t: 0 for t in PearlType}

    def on_event(
        self,
        event_type: PearlType,
        sweary: bool = False,
        *,
        max_per_race: int | None = None,
        pearl_frequency: float = 1.0,
        roll: float | None = None,
    ) -> str | None:
        freq = max(0.0, min(1.0, float(pearl_frequency)))
        if freq <= 0.0:
            return None
        if freq < 1.0:
            sample = roll if roll is not None else random.random()
            if sample > freq:
                return None
        limit = max_per_race if max_per_race is not None else self.MAX_PER_RACE
        if self._count >= limit:
            return None
        pool = _PEARLS_SWEARY if sweary else _PEARLS_CLEAN
        messages = pool.get(event_type) or pool[PearlType.STANDARD]
        if not messages:
            return None
        idx = self._index[event_type] % len(messages)
        self._index[event_type] += 1
        self._count += 1
        return messages[idx]
