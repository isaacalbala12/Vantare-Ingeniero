from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"
_picker_singleton: PhrasePicker | None = None


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
    def load_bundle_defaults(cls) -> "PhrasePicker":
        spotter_path = _DATA / "spotter_phrases_es.json"
        trigger_path = _DATA / "trigger_phrases_es.json"
        spotter = json.loads(spotter_path.read_text(encoding="utf-8")) if spotter_path.is_file() else {}
        triggers = json.loads(trigger_path.read_text(encoding="utf-8")) if trigger_path.is_file() else {}
        return cls(spotter=spotter, triggers=triggers)

    @classmethod
    def load_defaults(cls) -> "PhrasePicker":
        from src.intelligence.phrase_catalog import PhraseCatalog

        catalog = PhraseCatalog.load_merged()
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


def reload_picker() -> PhrasePicker:
    global _picker_singleton
    from src.intelligence.phrase_catalog import PhraseCatalog

    catalog = PhraseCatalog.load_merged()
    _picker_singleton = PhrasePicker(spotter=catalog.spotter, triggers=catalog.triggers)
    return _picker_singleton


def get_picker() -> PhrasePicker:
    global _picker_singleton
    if _picker_singleton is None:
        reload_picker()
    return _picker_singleton


def profile_from_session(session: dict | None) -> str:
    if not session:
        return "standard"
    pid = str(session.get("personalityProfileId") or "standard").strip().lower()
    return pid if pid in ("standard", "formal", "aggressive") else "standard"


def trigger_phrase_for_session(
    session: dict | None,
    key: str,
    fallback: str = "",
    *,
    seed: int | None = None,
    **kwargs: str,
) -> str:
    msg = get_picker().trigger_phrase(
        key,
        profile_id=profile_from_session(session),
        seed=seed,
        **kwargs,
    )
    return msg or fallback


def spotter_phrase_for_cache(key: str, *, profile_id: str = "standard", seed: int = 0) -> str:
    """Primera variante estable para precalentar caché TTS spotter."""
    return get_picker().spotter_phrase(key, profile_id=profile_id, seed=seed)
