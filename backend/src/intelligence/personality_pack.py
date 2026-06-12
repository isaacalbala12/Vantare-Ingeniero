"""Perfiles de personalidad ingeniero + spotter (prompts y voces TTS)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from src.intelligence.phrase_picker import get_picker, normalize_locale

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


_PROFILES_ES: Dict[str, PersonalityProfile] = {
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

_PROFILES_EN: Dict[str, PersonalityProfile] = {
    "formal": PersonalityProfile(
        profile_id="formal",
        label="Formal",
        engineer_tone="Professional and precise tone. No filler. Maximum 2 sentences.",
        spotter_tone="Brief neutral alerts. No emotion.",
        tts_voice_engineer="en-GB-RyanNeural",
        tts_voice_spotter="en-US-JennyNeural",
    ),
    "standard": PersonalityProfile(
        profile_id="standard",
        label="Standard",
        engineer_tone="Race radio tone: direct, clear, motivating without excess.",
        spotter_tone="Short, clear alerts, race spotter style.",
        tts_voice_engineer="en-GB-RyanNeural",
        tts_voice_spotter="en-US-JennyNeural",
    ),
    "aggressive": PersonalityProfile(
        profile_id="aggressive",
        label="Aggressive",
        engineer_tone="Energetic and demanding tone. Pushes the driver. Maximum 2 forceful sentences.",
        spotter_tone="Crisp urgent alerts. Prioritises clarity under pressure.",
        tts_voice_engineer="en-GB-RyanNeural",
        tts_voice_spotter="en-US-JennyNeural",
    ),
}

_PROACTIVE_RANK = {"CRITICAL": 4, "HIGH": 3, "IMPORTANT": 3, "MEDIUM": 2, "NORMAL": 2, "LOW": 1}


class PersonalityPack:
    """Resuelve perfil activo y aportes de tono/voz para ingeniero y spotter."""

    def __init__(
        self,
        profile_id: str = DEFAULT_PROFILE_ID,
        *,
        locale: str = "es",
        sweary: bool = False,
        proactivity: str = "normal",
        pearl_frequency: float = 0.5,
    ) -> None:
        self._locale = normalize_locale(locale)
        self._profile_id = self._normalize(profile_id)
        self._runtime = PersonalityRuntime(
            sweary=bool(sweary),
            proactivity=self._normalize_proactivity(proactivity),
            pearl_frequency=self._clamp_pearl_frequency(pearl_frequency),
        )

    def _normalize(self, profile_id: str | None) -> str:
        profiles = _PROFILES_EN if self._locale == "en" else _PROFILES_ES
        pid = (profile_id or DEFAULT_PROFILE_ID).strip().lower()
        return pid if pid in profiles else DEFAULT_PROFILE_ID

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
    def locale(self) -> str:
        return self._locale

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

    def set_locale(self, locale: str | None) -> str:
        self._locale = normalize_locale(locale)
        self._profile_id = self._normalize(self._profile_id)
        return self._locale

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
        profiles = _PROFILES_EN if self._locale == "en" else _PROFILES_ES
        return profiles[self._profile_id]

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
        return get_picker(self._locale).spotter_phrase(key, profile_id=self._profile_id, **kwargs)

    def trigger_phrase(self, key: str, **kwargs: str) -> str:
        return get_picker(self._locale).trigger_phrase(key, profile_id=self._profile_id, **kwargs)

    @staticmethod
    def list_profiles(locale: str = "es") -> list[PersonalityProfile]:
        profiles = _PROFILES_EN if normalize_locale(locale) == "en" else _PROFILES_ES
        return list(profiles.values())
