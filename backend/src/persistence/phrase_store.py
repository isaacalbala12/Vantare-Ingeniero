"""Persistencia de frases spotter/triggers con merge sobre defaults empaquetados."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("vantare.phrase_store")

_DATA = Path(__file__).resolve().parent.parent / "data"
VALID_PROFILES = frozenset({"standard", "formal", "aggressive"})
BANNED_PREFIXES = ("atención:", "alerta:", "mensaje:", "warning:")


def phrases_dir() -> Path:
    override = os.environ.get("VANTARE_PHRASES_DIR", "").strip()
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return Path(appdata) / "Vantare" / "phrases"


def user_phrases_path() -> Path:
    return phrases_dir() / "user_phrases.json"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("user_phrases.json debe ser un objeto JSON")
    return data


def _sanitize_template(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    lower = text.lstrip().lower()
    if any(lower.startswith(prefix) for prefix in BANNED_PREFIXES):
        raise ValueError(f"Prefijo robótico prohibido en frase: {text[:40]}")
    return text


def validate_user_phrases(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Payload debe ser un objeto JSON")

    out: dict[str, Any] = {}
    spotter_in = data.get("spotter")
    if spotter_in is not None:
        if not isinstance(spotter_in, dict):
            raise ValueError("spotter debe ser un objeto")
        spotter_out: dict[str, dict[str, str]] = {}
        for profile_id, keys in spotter_in.items():
            if profile_id not in VALID_PROFILES:
                raise ValueError(f"Perfil spotter inválido: {profile_id}")
            if not isinstance(keys, dict):
                raise ValueError(f"spotter.{profile_id} debe ser un objeto")
            profile_out: dict[str, str] = {}
            for key, template in keys.items():
                if not isinstance(key, str) or not key.strip():
                    raise ValueError("Claves spotter deben ser strings no vacíos")
                cleaned = _sanitize_template(template)
                if cleaned:
                    profile_out[key.strip()] = cleaned
            if profile_out:
                spotter_out[profile_id] = profile_out
        if spotter_out:
            out["spotter"] = spotter_out

    triggers_in = data.get("triggers")
    if triggers_in is not None:
        if not isinstance(triggers_in, dict):
            raise ValueError("triggers debe ser un objeto")
        triggers_out: dict[str, dict[str, str]] = {}
        for phrase_key, profiles in triggers_in.items():
            if not isinstance(phrase_key, str) or not phrase_key.strip():
                raise ValueError("Claves trigger deben ser strings no vacíos")
            if not isinstance(profiles, dict):
                raise ValueError(f"triggers.{phrase_key} debe ser un objeto")
            key_out: dict[str, str] = {}
            for profile_id, template in profiles.items():
                if profile_id not in VALID_PROFILES:
                    raise ValueError(f"Perfil trigger inválido: {profile_id}")
                cleaned = _sanitize_template(template)
                if cleaned:
                    key_out[profile_id] = cleaned
            if key_out:
                triggers_out[phrase_key.strip()] = key_out
        if triggers_out:
            out["triggers"] = triggers_out

    return out


def merge_user_overrides_raw(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Fusiona overrides; plantillas vacías eliminan la clave."""
    out = copy.deepcopy(existing)
    if "spotter" in incoming:
        incoming_spotter = incoming.get("spotter") or {}
        if not incoming_spotter:
            out.pop("spotter", None)
        else:
            out.setdefault("spotter", {})
            for profile_id, keys in incoming_spotter.items():
                if not isinstance(keys, dict):
                    continue
                out["spotter"].setdefault(profile_id, {})
                for key, template in keys.items():
                    if isinstance(template, str) and not template.strip():
                        out["spotter"][profile_id].pop(key, None)
                    elif isinstance(template, str):
                        out["spotter"][profile_id][key] = template.strip()
                if not out["spotter"].get(profile_id):
                    out["spotter"].pop(profile_id, None)
            if not out.get("spotter"):
                out.pop("spotter", None)
    if "triggers" in incoming:
        incoming_triggers = incoming.get("triggers") or {}
        if not incoming_triggers:
            out.pop("triggers", None)
        else:
            out.setdefault("triggers", {})
            for phrase_key, profiles in incoming_triggers.items():
                if not isinstance(profiles, dict):
                    continue
                out["triggers"].setdefault(phrase_key, {})
                for profile_id, template in profiles.items():
                    if isinstance(template, str) and not template.strip():
                        out["triggers"][phrase_key].pop(profile_id, None)
                    elif isinstance(template, str):
                        out["triggers"][phrase_key][profile_id] = template.strip()
                if not out["triggers"].get(phrase_key):
                    out["triggers"].pop(phrase_key, None)
            if not out.get("triggers"):
                out.pop("triggers", None)
    return out


def merge_user_overrides(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    return merge_user_overrides_raw(existing, incoming)


def merge_phrase_catalog(
    defaults: dict[str, Any],
    user: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    merged = {
        "spotter": copy.deepcopy(defaults.get("spotter") or {}),
        "triggers": copy.deepcopy(defaults.get("triggers") or {}),
    }
    for profile_id, keys in (user.get("spotter") or {}).items():
        if not isinstance(keys, dict):
            continue
        merged["spotter"].setdefault(profile_id, {})
        for key, template in keys.items():
            if isinstance(template, str) and template.strip():
                merged["spotter"][profile_id][key] = template.strip()
    for phrase_key, profiles in (user.get("triggers") or {}).items():
        if not isinstance(profiles, dict):
            continue
        merged["triggers"].setdefault(phrase_key, {})
        for profile_id, template in profiles.items():
            if isinstance(template, str) and template.strip():
                merged["triggers"][phrase_key][profile_id] = template.strip()
    return merged


class PhraseStore:
    """Defaults empaquetados + overrides en AppData (user_phrases.json)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.last_user_load_error: str | None = None

    def load_defaults(self, locale: str = "es") -> dict[str, dict[str, Any]]:
        if locale not in ("es", "en"):
            raise ValueError(f"Unsupported locale: {locale}")
        spotter_path = _DATA / f"spotter_phrases_{locale}.json"
        trigger_path = _DATA / f"trigger_phrases_{locale}.json"
        spotter = json.loads(spotter_path.read_text(encoding="utf-8")) if spotter_path.is_file() else {}
        triggers = json.loads(trigger_path.read_text(encoding="utf-8")) if trigger_path.is_file() else {}
        return {"spotter": spotter, "triggers": triggers}

    def _read_user_file(self, *, record_error: bool) -> dict[str, Any]:
        path = user_phrases_path()
        if not path.is_file():
            if record_error:
                self.last_user_load_error = None
            return {}
        try:
            raw = _load_json(path)
            validated = validate_user_phrases(raw)
            if record_error:
                self.last_user_load_error = None
            return validated
        except json.JSONDecodeError as exc:
            message = f"JSON inválido en user_phrases.json: {exc.msg}"
            if record_error:
                self.last_user_load_error = message
            logger.warning(message)
            return {}
        except ValueError as exc:
            message = str(exc)
            if record_error:
                self.last_user_load_error = message
            logger.warning("user_phrases.json inválido: %s", message)
            return {}

    def load_user(self) -> dict[str, Any]:
        with self._lock:
            return self._read_user_file(record_error=True)

    def load_merged(self, locale: str = "es") -> dict[str, dict[str, Any]]:
        return merge_phrase_catalog(self.load_defaults(locale=locale), self.load_user())

    def export_user(self) -> dict[str, Any]:
        return self.load_user()

    def save_user(self, overrides: dict[str, Any], *, replace: bool = False) -> dict[str, Any]:
        with self._lock:
            if replace:
                merged_raw = overrides
            else:
                existing = self._read_user_file(record_error=False)
                merged_raw = merge_user_overrides_raw(existing, overrides)
            merged_user = validate_user_phrases(merged_raw)
            if not merged_user:
                self._reset_user_unlocked()
                self.last_user_load_error = None
                return {}
            path = user_phrases_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(merged_user, handle, indent=2, ensure_ascii=False)
            self.last_user_load_error = None
            return merged_user

    def _reset_user_unlocked(self) -> None:
        path = user_phrases_path()
        if path.is_file():
            path.unlink()

    def reset_user(self) -> None:
        with self._lock:
            self._reset_user_unlocked()
            self.last_user_load_error = None
