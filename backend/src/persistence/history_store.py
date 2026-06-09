"""
HistoryStore — Persiste el historial de consumo de combustible vuelta a vuelta.

Guarda en:
  data/consumption_history.json

Formato de cada registro:
  { "lap": int, "consumption": float (L), "fuelRemaining": float (L), "lapTime": float (s) }

Thread-safe mediante threading.Lock.
"""
import json
import os
import threading
from typing import List

# Ruta base para datos persistentes (relativa a backend/)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
SESSION_FILE = os.path.join(DATA_DIR, "consumption_history.json")


class HistoryStore:
    """Almacén de historial de consumo de combustible con persistencia a JSON."""

    def __init__(self, auto_load: bool = True) -> None:
        self._lock = threading.Lock()
        self._history: List[dict] = []
        if auto_load:
            self.load()

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def record_lap(
        self,
        lap: int,
        fuel_used: float,
        fuel_remaining: float,
        lap_time: float,
    ) -> None:
        """Registra el consumo de una vuelta completada."""
        record = {
            "lap": lap,
            "consumption": round(fuel_used, 3),
            "fuelRemaining": round(fuel_remaining, 2),
            "lapTime": round(lap_time, 2),
        }
        with self._lock:
            # Reemplazar si ya existe un registro para esta vuelta
            for i, existing in enumerate(self._history):
                if existing["lap"] == lap:
                    self._history[i] = record
                    break
            else:
                self._history.append(record)
        self.save()

    def get_history(self) -> List[dict]:
        """Devuelve una copia del historial completo ordenado por vuelta."""
        with self._lock:
            return sorted(self._history, key=lambda r: r["lap"])

    def clear(self) -> None:
        """Limpia el historial en memoria (no borra el archivo en disco)."""
        with self._lock:
            self._history.clear()

    # ------------------------------------------------------------------
    # Persistencia
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persiste el historial actual a disco como JSON."""
        with self._lock:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(SESSION_FILE, "w", encoding="utf-8") as f:
                json.dump(self._history, f, indent=2, ensure_ascii=False)

    def load(self) -> None:
        """Carga el historial desde disco (si existe)."""
        if not os.path.exists(SESSION_FILE):
            self._history = []
            return
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._history = data
            else:
                self._history = []
        except (json.JSONDecodeError, OSError):
            self._history = []
