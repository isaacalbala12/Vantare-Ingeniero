"""Global behaviour settings (singleton mutable, igual que el plan)."""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class GlobalBehaviour:
    spotter_enabled: bool = True
    use_oval: bool = False
    oval_spotter: bool = False
    just_facts: bool = False
    speak_when_spoken: bool = False
    cut_warnings: bool = True
    use_american: bool = False
    use_metric: bool = True
    max_complaints: int = 3
    complaints_count: int = 0
    messages: Set[str] = field(default_factory=lambda: {"ALL"})

    def message_type_enabled(self, category: str) -> bool:
        if "ALL" in self.messages:
            return True
        if "NONE" in self.messages:
            return False
        return category in self.messages


# Singleton global
global_settings = GlobalBehaviour()
