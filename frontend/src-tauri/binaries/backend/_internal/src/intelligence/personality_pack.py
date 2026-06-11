"""Perfiles de personalidad ingeniero + spotter (prompts y voces TTS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.intelligence.phrase_picker import get_picker

DEFAULT_PROFILE_ID = "standard"
VALID_PROACTIVITY = frozenset({"low", "normal", "high"})


@dataclass(frozen=True)
class PersonalityProfile:
    profile_id: str
    label: str
    engineer_tone: str
    spotter_tone: str
    tts_voice_engineer: str
    tts_voice_spotter: str


@dataclass
class PersonalityRuntime:
    sweary: bool = False
    proactivity: str = "normal"
    pearl_frequency: float = 0.5


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

_PROACTIVE_RANK = {"CRITICAL": 4, "HIGH": 3, "IMPORTANT": 3, "MEDIUM": 2, "NORMAL": 2, "LOW": 1}


class PersonalityPack:
    """Resuelve perfil activo y aportes de tono/voz para ingeniero y spotter."""

    def __init__(
        self,
        profile_id: str = DEFAULT_PROFILE_ID,
        *,
        sweary: bool = False,
        proactivity: str = "normal",
        pearl_frequency: float = 0.5,
    ) -> None:
        self._profile_id = self._normalize(profile_id)
        self._runtime = PersonalityRuntime(
            sweary=bool(sweary),
            proactivity=self._normalize_proactivity(proactivity),
            pearl_frequency=self._clamp_pearl_frequency(pearl_frequency),
        )

    @staticmethod
    def _normalize(profile_id: str | None) -> str:
        pid = (profile_id or DEFAULT_PROFILE_ID).strip().lower()
        return pid if pid in _PROFILES else DEFAULT_PROFILE_ID

    @staticmethod
    def _normalize_proactivity(value: str | None) -> str:
        raw = (value or "normal").strip().lower()
        return raw if raw in VALID_PROACTIVITY else "normal"

    @staticmethod
    def _clamp_pearl_frequency(value: float | int | None) -> float:
        try:
            freq = float(value if value is not None else 0.5)
        except (TypeError, ValueError):
            return 0.5
        return max(0.0, min(1.0, freq))

    @property
    def profile_id(self) -> str:
        return self._profile_id

    @property
    def sweary_enabled(self) -> bool:
        return self._runtime.sweary

    @property
    def proactivity(self) -> str:
        return self._runtime.proactivity

    @property
    def pearl_frequency(self) -> float:
        return self._runtime.pearl_frequency

    def set_profile(self, profile_id: str) -> str:
        self._profile_id = self._normalize(profile_id)
        return self._profile_id

    def apply_runtime(
        self,
        *,
        sweary: bool | None = None,
        proactivity: str | None = None,
        pearl_frequency: float | None = None,
    ) -> None:
        if sweary is not None:
            self._runtime.sweary = bool(sweary)
        if proactivity is not None:
            self._runtime.proactivity = self._normalize_proactivity(proactivity)
        if pearl_frequency is not None:
            self._runtime.pearl_frequency = self._clamp_pearl_frequency(pearl_frequency)

    def get(self) -> PersonalityProfile:
        return _PROFILES[self._profile_id]

    def engineer_system_suffix(self) -> str:
        tone = self.get().engineer_tone
        if self._runtime.sweary:
            tone += " Lenguaje coloquial de paddock permitido; evita prefijos robóticos tipo «Atención»."
        return tone

    def tone_preview(self) -> str:
        return self.engineer_system_suffix()

    def spotter_tone_hint(self) -> str:
        return self.get().spotter_tone

    def tts_voice_engineer(self) -> str:
        return self.get().tts_voice_engineer

    def tts_voice_spotter(self) -> str:
        return self.get().tts_voice_spotter

    def should_emit_proactive(self, priority: str) -> bool:
        rank = _PROACTIVE_RANK.get((priority or "LOW").upper(), 1)
        if self._runtime.proactivity == "low":
            return rank >= _PROACTIVE_RANK["HIGH"]
        if self._runtime.proactivity == "normal":
            return rank >= _PROACTIVE_RANK["MEDIUM"]
        return rank >= _PROACTIVE_RANK["LOW"]

    def spotter_phrase(self, key: str, **kwargs: str) -> str:
        return get_picker().spotter_phrase(key, profile_id=self._profile_id, **kwargs)

    @staticmethod
    def list_profiles() -> list[PersonalityProfile]:
        return list(_PROFILES.values())
