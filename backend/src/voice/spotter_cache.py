from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("vantare.spotter_cache")

# Alineado con frontend SPOTTER_PREFETCH_PHRASES + spotter_phrases_es.json
PREFETCH_PHRASES: dict[str, str] = {
    "proximity_left": "Coche a la izquierda",
    "proximity_right": "Coche a la derecha",
    "still_there_left": "Sigue coche por izquierda.",
    "still_there_right": "Sigue coche por derecha.",
    "hypercar_right": "Hypercar doblando por la derecha",
    "gt3_left": "GT3 adelantando por la izquierda",
    "clear_left": "Despejado izquierda",
    "clear_right": "Despejado derecha",
    "three_wide": "Tres coches de ancho",
    "hold_line_right": "Mantén la línea, coche por derecha.",
    "closing_fast_left": "¡Viene rápido por izquierda!",
    "limiter_enter": "Pit limiter no activado al entrar en boxes.",
    "limiter_exit": "Pit limiter no desactivado al salir de boxes.",
    "fuel_critical": "¡Combustible crítico! Menos de 1 vuelta restante.",
    "safety_car": "Safety car desplegado / FCY activo en pista.",
    "last_lap": "¡Última vuelta de la carrera!",
    "damage": "Daños detectados en el monoplaza.",
    "limiter_engage_legacy": "Activa el limiter de boxes.",
    "limiter_disengage_legacy": "Desactiva el limiter de boxes.",
}


def default_spotter_phrases() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "data" / "spotter_phrases_es.json"
    phrases = dict(PREFETCH_PHRASES)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            std = data.get("standard", {})
            if std.get("clear_left"):
                phrases.setdefault("clear_left", std["clear_left"])
            if std.get("clear_right"):
                phrases.setdefault("clear_right", std["clear_right"])
            if std.get("fuel_critical"):
                phrases.setdefault("fuel_critical", std["fuel_critical"])
        except Exception as exc:
            logger.warning("Could not merge spotter_phrases_es.json: %s", exc)
    return {k: v for k, v in phrases.items() if v and v.strip()}


class SpotterPhraseCache:
    def __init__(self, tts) -> None:
        self._tts = tts
        self._bytes: dict[str, bytes] = {}

    async def warm(self, phrases: dict[str, str] | None = None) -> None:
        phrases = phrases or default_spotter_phrases()
        for key, text in phrases.items():
            if not text or not text.strip():
                continue
            self._bytes[key] = await self._tts.synthesize(text.strip())

    def get(self, key: str | None) -> bytes | None:
        if not key:
            return None
        return self._bytes.get(key)

    @property
    def size(self) -> int:
        return len(self._bytes)
