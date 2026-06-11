"""Catálogo mergeado spotter/triggers (defaults + overrides usuario)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.persistence.phrase_store import PhraseStore


@dataclass(frozen=True)
class PhraseCatalog:
    spotter: dict[str, dict[str, str]]
    triggers: dict[str, dict[str, str]]

    @classmethod
    def load_merged(cls, store: PhraseStore | None = None) -> "PhraseCatalog":
        data = (store or PhraseStore()).load_merged()
        return cls(
            spotter=data.get("spotter") or {},
            triggers=data.get("triggers") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {"spotter": self.spotter, "triggers": self.triggers}
