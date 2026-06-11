"""Perfiles de personalidad ingeniero + spotter (prompts y voces TTS)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

DEFAULT_PROFILE_ID = "standard"


@dataclass(frozen=True)
class PersonalityProfile:
    profile_id: str
    label: str
    engineer_tone: str
    spotter_tone: str
    tts_voice_engineer: str
    tts_voice_spotter: str


_PROFILES: Dict[str, PersonalityProfile] = {
    "formal": PersonalityProfile(
        profile_id="formal",
        label="Formal",
        engineer_tone="Tono profesional y preciso. Sin muletillas. Máximo 2 frases.",
        spotter_tone="Alertas breves y neutras. Sin emoción.",
        tts_voice_engineer="es-ES-AlvaroNeural",
        tts_voice_spotter="es-ES-ElviraNeural",
    ),
    "standard": PersonalityProfile(
        profile_id="standard",
        label="Estándar",
        engineer_tone="Tono de radio de boxes: directo, claro, motivador sin excesos.",
        spotter_tone="Alertas cortas y claras, estilo spotter de carrera.",
        tts_voice_engineer="es-ES-AlvaroNeural",
        tts_voice_spotter="es-ES-ElviraNeural",
    ),
    "aggressive": PersonalityProfile(
        profile_id="aggressive",
        label="Agresivo",
        engineer_tone="Tono enérgico y exigente. Empuja al piloto. Máximo 2 frases contundentes.",
        spotter_tone="Alertas secas y urgentes. Prioriza claridad bajo presión.",
        tts_voice_engineer="es-ES-AlvaroNeural",
        tts_voice_spotter="es-ES-AlvaroNeural",
    ),
}

_PHRASES_PATH = Path(__file__).resolve().parent.parent / "data" / "spotter_phrases_es.json"
_SPOTTER_PHRASES: Dict[str, Dict[str, str]] = {}
if _PHRASES_PATH.is_file():
    with open(_PHRASES_PATH, encoding="utf-8") as f:
        _SPOTTER_PHRASES = json.load(f)


class PersonalityPack:
    """Resuelve perfil activo y aportes de tono/voz para ingeniero y spotter."""

    def __init__(self, profile_id: str = DEFAULT_PROFILE_ID) -> None:
        self._profile_id = self._normalize(profile_id)

    @staticmethod
    def _normalize(profile_id: str | None) -> str:
        pid = (profile_id or DEFAULT_PROFILE_ID).strip().lower()
        return pid if pid in _PROFILES else DEFAULT_PROFILE_ID

    @property
    def profile_id(self) -> str:
        return self._profile_id

    def set_profile(self, profile_id: str) -> str:
        self._profile_id = self._normalize(profile_id)
        return self._profile_id

    def get(self) -> PersonalityProfile:
        return _PROFILES[self._profile_id]

    def engineer_system_suffix(self) -> str:
        return self.get().engineer_tone

    def spotter_tone_hint(self) -> str:
        return self.get().spotter_tone

    def tts_voice_engineer(self) -> str:
        return self.get().tts_voice_engineer

    def tts_voice_spotter(self) -> str:
        return self.get().tts_voice_spotter

    def spotter_phrase(self, key: str, **kwargs: str) -> str:
        template = _SPOTTER_PHRASES.get(self._profile_id, {}).get(key, "")
        if not template:
            return ""
        try:
            return template.format(**kwargs)
        except KeyError:
            return template

    @staticmethod
    def list_profiles() -> list[PersonalityProfile]:
        return list(_PROFILES.values())
