"""Shared event flags (sin asyncio.Lock: eventos corren secuenciales en mismo loop).

CrewChiefV4 original usa Lock porque algunos flags se modifican desde distintos
hilos. En nuestra implementación todo el dispatch es secuencial (EventEngine.tick
procesa eventos uno tras otro en el mismo task), así que el lock es overhead
inútil. Si en el futuro paralelizamos, se añade.
"""

from dataclasses import dataclass, field
from typing import Set


@dataclass
class EventFlags:
    is_pitting: bool = False
    played_pit_request: bool = False
    waiting_mandatory_stop: bool = False
    white_flag: bool = False
    played_prelights: bool = False
    exit_close_front: Set[str] = field(default_factory=set)
    exit_close_behind: Set[str] = field(default_factory=set)
    waiting_driver_ok: bool = False
    on_formation: bool = False
    on_manual_formation_lap: bool = False
    green_for_n_laps: int = 0
    last_lap_was_pit_lap: bool = False
    fuel_warning_active: bool = False
    is_pitting_this_lap: bool = False
    waiting_for_driver_is_ok_response: bool = False

    def reset(self) -> None:
        """Reset todos los flags a su valor por defecto.

        Usa el tipo real del valor actual (no el del dataclass hint) para evitar
        confundir bool con int (en Python `isinstance(True, int)` es True).
        """
        for fname in self.__dataclass_fields__:
            current = getattr(self, fname, None)
            if isinstance(current, bool):
                setattr(self, fname, False)
            elif isinstance(current, set):
                setattr(self, fname, set())
            elif isinstance(current, int):
                setattr(self, fname, 0)
            elif isinstance(current, float):
                setattr(self, fname, 0.0)
            else:
                setattr(self, fname, None)

    reset_all = reset


# Singleton global (mismo patrón que el plan)
event_flags = EventFlags()
