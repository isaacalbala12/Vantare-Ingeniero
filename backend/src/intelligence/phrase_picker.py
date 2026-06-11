from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

_DATA = Path(__file__).resolve().parent.parent / "data"


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
    def load_defaults(cls) -> "PhrasePicker":
        spotter_path = _DATA / "spotter_phrases_es.json"
        trigger_path = _DATA / "trigger_phrases_es.json"
        spotter = json.loads(spotter_path.read_text(encoding="utf-8")) if spotter_path.is_file() else {}
        triggers = json.loads(trigger_path.read_text(encoding="utf-8")) if trigger_path.is_file() else {}
        return cls(spotter=spotter, triggers=triggers)

    def spotter_phrase(self, key: str, *, profile_id: str, seed: int | None = None, **kwargs: str) -> str:
        template = self.spotter.get(profile_id, {}).get(key) or self.spotter.get("standard", {}).get(key, "")
        text = pick_variant(template, seed=seed)
        if not text:
            return ""
        try:
            return text.format(**kwargs)
        except KeyError:
            return text

    def trigger_phrase(self, key: str, *, profile_id: str, seed: int | None = None, **kwargs: str) -> str:
        entry = self.triggers.get(key, {})
        template = entry.get(profile_id) or entry.get("standard", "")
        text = pick_variant(template, seed=seed)
        if not text:
            return ""
        try:
            return text.format(**kwargs)
        except KeyError:
            return text
