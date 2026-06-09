"""Persistencia CC-style fuel usage por juego/coche/pista (max 5 muestras)."""

from __future__ import annotations

import json
import os
import random
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
FUEL_USAGE_FILE = os.path.join(DATA_DIR, "fuel_usage.json")
MAX_SAMPLES = 5
SAVE_PROBABILITY = 0.1


class FuelUsageStore:
    def __init__(self, auto_load: bool = True) -> None:
        self._data: dict[str, list[dict[str, Any]]] = {}
        if auto_load:
            self.load()

    @staticmethod
    def _key(game: str, car: str, track: str) -> str:
        return f"{game}|{car}|{track}"

    def record_sample(self, game: str, car: str, track: str, consumption_l: float) -> None:
        if consumption_l <= 0 or random.random() > SAVE_PROBABILITY:
            return
        key = self._key(game, car, track)
        rows = self._data.setdefault(key, [])
        rows.append({"consumption_l": round(consumption_l, 3)})
        if len(rows) > MAX_SAMPLES:
            del rows[0]

    def get_samples(self, game: str, car: str, track: str) -> list[dict[str, Any]]:
        return list(self._data.get(self._key(game, car, track), []))

    def save(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(FUEL_USAGE_FILE, "w", encoding="utf-8") as handle:
            json.dump(self._data, handle, indent=2)

    def load(self) -> None:
        if not os.path.exists(FUEL_USAGE_FILE):
            return
        with open(FUEL_USAGE_FILE, encoding="utf-8") as handle:
            self._data = json.load(handle)
