from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TtsRouting:
    provider_engineer: str = "edge"
    provider_spotter: str = "edge"
    gemini_voice_engineer: str = "Kore"
    gemini_voice_spotter: str = "Kore"
    edge_voice_engineer: str = "es-ES-AlvaroNeural"
    edge_voice_spotter: str = "es-ES-ElviraNeural"

    def provider_for_category(self, category: str) -> str:
        if category in ("spotter", "proximity", "gaps"):
            return self.provider_spotter
        return self.provider_engineer
