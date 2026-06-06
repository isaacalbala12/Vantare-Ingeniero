"""Persistencia de perfiles de configuración completos."""

from __future__ import annotations

import json
import os
import re
import threading
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")
PROFILES_DIR = os.path.join(DATA_DIR, "profiles")

_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _validate_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned or not _NAME_RE.match(cleaned):
        raise ValueError("Nombre de perfil inválido (use letras, números, _ o -)")
    return cleaned


def _profile_path(name: str) -> str:
    return os.path.join(PROFILES_DIR, f"{name}.json")


class ProfileStore:
    """Almacén thread-safe de perfiles JSON en disco."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        os.makedirs(PROFILES_DIR, exist_ok=True)

    def save_profile(self, name: str, config: dict[str, Any]) -> None:
        profile_name = _validate_name(name)
        if not isinstance(config, dict):
            raise ValueError("config debe ser un objeto JSON")
        payload = {"name": profile_name, "config": config}
        with self._lock:
            os.makedirs(PROFILES_DIR, exist_ok=True)
            with open(_profile_path(profile_name), "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

    def load_profile(self, name: str) -> dict[str, Any]:
        profile_name = _validate_name(name)
        path = _profile_path(profile_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Perfil no encontrado: {profile_name}")
        with self._lock:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict) or "config" not in data:
            raise ValueError("Perfil corrupto")
        return data["config"]

    def list_profiles(self) -> list[str]:
        with self._lock:
            if not os.path.isdir(PROFILES_DIR):
                return []
            names = []
            for entry in os.listdir(PROFILES_DIR):
                if entry.endswith(".json"):
                    names.append(entry[:-5])
            return sorted(names)

    def delete_profile(self, name: str) -> None:
        profile_name = _validate_name(name)
        path = _profile_path(profile_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Perfil no encontrado: {profile_name}")
        with self._lock:
            os.remove(path)
