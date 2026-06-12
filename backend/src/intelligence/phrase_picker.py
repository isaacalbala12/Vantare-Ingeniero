from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_picker_singletons: dict[str, PhrasePicker] = {}


def normalize_locale(locale: str | None) -> str:
    return "en" if locale == "en" else "es"


def pick_variant(template: str, *, seed: int | None = None) -> str:
    parts = [p.strip() for p in template.split("|") if p.strip()]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    rng = random.Random(seed)
    return rng.choice(parts)


@dataclass(frozen=True)
class PhrasePicker:
    spotter: dict[str, dict[str, str]]
    triggers: dict[str, dict[str, str]]

    @classmethod
    def load_bundle_defaults(cls, locale: str = "es") -> "PhrasePicker":
        locale = normalize_locale(locale)
        spotter_path = _DATA / f"spotter_phrases_{locale}.json"
        trigger_path = _DATA / f"trigger_phrases_{locale}.json"
        spotter = json.loads(spotter_path.read_text(encoding="utf-8")) if spotter_path.is_file() else {}
        triggers = json.loads(trigger_path.read_text(encoding="utf-8")) if trigger_path.is_file() else {}
        return cls(spotter=spotter, triggers=triggers)

    @classmethod
    def load_defaults(cls, locale: str = "es") -> "PhrasePicker":
        from src.intelligence.phrase_catalog import PhraseCatalog

        catalog = PhraseCatalog.load_merged(locale=normalize_locale(locale))
        return cls(spotter=catalog.spotter, triggers=catalog.triggers)

    @classmethod
    def from_catalog(cls, catalog: "PhraseCatalog") -> "PhrasePicker":
        return cls(spotter=catalog.spotter, triggers=catalog.triggers)

    def spotter_phrase(self, key: str, *, profile_id: str, seed: int | None = None, **kwargs: str) -> str:
        template = self.spotter.get(profile_id, {}).get(key) or self.spotter.get("standard", {}).get(key, "")
        text = pick_variant(template, seed=seed)
        if not text:
            return ""
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text

    def trigger_phrase(self, key: str, *, profile_id: str, seed: int | None = None, **kwargs: str) -> str:
        entry = self.triggers.get(key, {})
        template = entry.get(profile_id) or entry.get("standard", "")
        text = pick_variant(template, seed=seed)
        if not text:
            return ""
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text


def reload_picker(locale: str = "es") -> PhrasePicker:
    locale = normalize_locale(locale)
    from src.intelligence.phrase_catalog import PhraseCatalog

    catalog = PhraseCatalog.load_merged(locale=locale)
    picker = PhrasePicker(spotter=catalog.spotter, triggers=catalog.triggers)
    _picker_singletons[locale] = picker
    return picker


def get_picker(locale: str = "es") -> PhrasePicker:
    return reload_picker(locale)


def profile_from_session(session: dict | None) -> str:
    if not session:
        return "standard"
    pid = str(session.get("personalityProfileId") or "standard").strip().lower()
    return pid if pid in ("standard", "formal", "aggressive") else "standard"


def locale_from_session(session: dict | None) -> str:
    if not session:
        return "es"
    return normalize_locale(str(session.get("voiceLanguage") or "es").strip().lower())


def trigger_phrase_for_session(
    session: dict | None,
    key: str,
    fallback: str = "",
    *,
    seed: int | None = None,
    **kwargs: str,
) -> str:
    msg = get_picker(locale_from_session(session)).trigger_phrase(
        key,
        profile_id=profile_from_session(session),
        seed=seed,
        **kwargs,
    )
    return msg or fallback


def spotter_phrase_for_cache(key: str, *, profile_id: str = "standard", seed: int = 0, locale: str = "es") -> str:
    """Primera variante estable para precalentar caché TTS spotter."""
    return get_picker(locale).spotter_phrase(key, profile_id=profile_id, seed=seed)
