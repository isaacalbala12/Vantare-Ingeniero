from __future__ import annotations

import json
import logging
from pathlib import Path

from src.intelligence.phrase_picker import pick_variant, spotter_phrase_for_cache

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

_SPOTTER_JSON_KEYS = (
    "clear_left",
    "clear_right",
    "clear_all_round",
    "hold_line",
    "still_there",
    "closing_fast",
    "in_the_middle",
    "engage_limiter",
    "disengage_limiter",
    "fuel_critical",
)


def default_spotter_phrases() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "data" / "spotter_phrases_es.json"
    phrases = dict(PREFETCH_PHRASES)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            std = data.get("standard", {})
            for key in _SPOTTER_JSON_KEYS:
                raw = std.get(key)
                if not raw:
                    continue
                if "|" in raw:
                    phrases[key] = spotter_phrase_for_cache(key, profile_id="standard", seed=0)
                else:
                    phrases.setdefault(key, raw)
        except Exception as exc:
            logger.warning("Could not merge spotter_phrases_es.json: %s", exc)
    return {k: v for k, v in phrases.items() if v and v.strip()}


class SpotterPhraseCache:
    def __init__(self, tts) -> None:
        self._tts = tts
        self._bytes: dict[str, bytes] = {}

    async def warm(self, phrases: dict[str, str] | None = None, *, voice: str | None = None) -> None:
        phrases = phrases or default_spotter_phrases()
        for key, text in phrases.items():
            if not text or not text.strip():
                continue
            warm_text = pick_variant(text.strip(), seed=0) if "|" in text else text.strip()
            if voice and hasattr(self._tts, "synthesize"):
                self._bytes[key] = await self._tts.synthesize(warm_text, voice=voice)
            else:
                self._bytes[key] = await self._tts.synthesize(warm_text)

    def get(self, key: str | None) -> bytes | None:
        if not key:
            return None
        return self._bytes.get(key)

    @property
    def size(self) -> int:
        return len(self._bytes)
