"""Control de verbosidad estilo Crew Chief (silencioso / normal / detallado)."""

from __future__ import annotations

from enum import Enum


class VerbosityLevel(str, Enum):
    SILENT = "silent"
    NORMAL = "normal"
    DETAILED = "detailed"


_PRIORITY_RANK = {
    "CRITICAL": 4,
    "IMPORTANT": 3,
    "HIGH": 3,
    "NORMAL": 2,
    "MEDIUM": 2,
    "LOW": 1,
}


class VerbosityController:
    """Filtra emisión de comentarios proactivos según nivel configurado."""

    def __init__(self, level: str = VerbosityLevel.NORMAL.value) -> None:
        self._level = self._normalize(level)
        self._braking_zones_mute = False
        self._max_pearls_per_race = 2
        self._auto_floor_rank = 1
        self._speak_only_when_spoken_to = False
        self._enable_commentary_batch = False

    @staticmethod
    def _normalize(level: str | None) -> VerbosityLevel:
        raw = (level or VerbosityLevel.NORMAL.value).strip().lower()
        try:
            return VerbosityLevel(raw)
        except ValueError:
            return VerbosityLevel.NORMAL

    @property
    def level(self) -> VerbosityLevel:
        return self._level

    @property
    def braking_zones_mute(self) -> bool:
        return self._braking_zones_mute

    @property
    def speak_only_when_spoken_to(self) -> bool:
        return self._speak_only_when_spoken_to

    @property
    def enable_commentary_batch(self) -> bool:
        return self._enable_commentary_batch

    def set_enable_commentary_batch(self, enabled: bool) -> None:
        self._enable_commentary_batch = bool(enabled)

    @property
    def max_pearls_per_race(self) -> int:
        if self._level == VerbosityLevel.SILENT:
            return 0
        if self._level == VerbosityLevel.NORMAL:
            return self._max_pearls_per_race
        return self._max_pearls_per_race + 2

    def set_level(self, level: str) -> tuple[bool, str]:
        prev = self._level
        self._level = self._normalize(level)
        labels = {
            VerbosityLevel.SILENT: "silencioso",
            VerbosityLevel.NORMAL: "normal",
            VerbosityLevel.DETAILED: "detallado",
        }
        return True, f"Verbosidad cambiada de {labels[prev]} a {labels[self._level]}."

    def set_braking_zones_mute(self, enabled: bool) -> None:
        self._braking_zones_mute = bool(enabled)

    def set_speak_only_when_spoken_to(self, enabled: bool) -> None:
        self._speak_only_when_spoken_to = bool(enabled)

    def update_auto_context(self, telemetry: dict, session: dict) -> None:
        self._auto_floor_rank = 1
        speed = float(telemetry.get("speed_ms") or telemetry.get("speed") or 0.0)
        phase = str(session.get("phase") or telemetry.get("session_type") or "").lower()
        if speed <= 5:
            return
        if phase == "race":
            ahead = float(telemetry.get("time_gap_car_ahead") or telemetry.get("gap_ahead") or 999.0)
            behind = float(telemetry.get("time_gap_car_behind") or telemetry.get("gap_behind") or 999.0)
            very_close = (0 < ahead < 1.0) or (0 < behind < 1.0)
            close = (0 < ahead < 2.0) or (0 < behind < 2.0)
            if very_close:
                self._auto_floor_rank = _PRIORITY_RANK["HIGH"]
            elif close:
                self._auto_floor_rank = _PRIORITY_RANK["MEDIUM"]

    def should_mute_for_braking(self, brake_pressure: float | None, threshold: float = 0.15) -> bool:
        if not self._braking_zones_mute or brake_pressure is None:
            return False
        return brake_pressure >= threshold

    def should_emit_priority(self, priority: str) -> bool:
        rank = _PRIORITY_RANK.get((priority or "LOW").upper(), 1)
        if self._level == VerbosityLevel.SILENT:
            configured = _PRIORITY_RANK["CRITICAL"]
        elif self._level == VerbosityLevel.NORMAL:
            configured = _PRIORITY_RANK["MEDIUM"]
        else:
            configured = _PRIORITY_RANK["LOW"]
        return rank >= max(configured, self._auto_floor_rank)

    def should_emit_crewchief_category(
        self,
        category: str,
        priority: str,
        play_even_when_silenced: bool,
    ) -> bool:
        if self._speak_only_when_spoken_to:
            return category == "voice_response"
        if play_even_when_silenced:
            return True
        rank = _PRIORITY_RANK.get((priority or "LOW").upper(), 1)
        return self.should_emit_priority(priority) and rank >= self._auto_floor_rank

    def should_emit_event(self, verbosity_min: str) -> bool:
        return self.should_emit_priority(verbosity_min)
