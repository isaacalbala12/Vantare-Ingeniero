from copy import deepcopy
from typing import Dict, Set, Optional
from dataclasses import dataclass, field


@dataclass
class TickChanges:
    position_changed: bool = False
    old_position: Optional[int] = None
    new_position: Optional[int] = None
    leader_changed: bool = False
    session_phase_changed: bool = False
    new_lap: bool = False
    new_sector: bool = False
    retired_drivers: Set[str] = field(default_factory=set)
    new_drivers: Set[str] = field(default_factory=set)
    pit_entries: Set[str] = field(default_factory=set)
    pit_exits: Set[str] = field(default_factory=set)


class StateDiff:
    """Detector de cambios entre ticks con anti-bouncing de 1s en posiciones."""

    def __init__(self):
        self._prev: Optional[dict] = None
        self._prev_rivals: Dict[str, dict] = {}
        self._pending: Dict[str, dict] = {}
        self._bounce_lag: float = 1.0

    def update(self, current: dict, now: float = 0.0) -> TickChanges:
        import time as _time
        now = now or _time.time()
        c = TickChanges()

        if self._prev is None:
            self._prev = deepcopy(current)
            self._prev_rivals = {
                r["driver_raw_name"]: r
                for r in current.get("rivals", [])
            }
            return c

        cl = current.get("lap_number", 0)
        pl = self._prev.get("lap_number", 0)
        c.new_lap = cl > pl

        cs = current.get("sector_number")
        ps = self._prev.get("sector_number")
        c.new_sector = cs != ps

        old_pos = self._prev.get("place", 0)
        new_pos = current.get("place", 0)
        if old_pos != new_pos and new_pos > 0:
            p = self._pending.get("player")
            if p and p["new"] == new_pos:
                if now >= p["settle"]:
                    c.position_changed = True
                    c.old_position = old_pos
                    c.new_position = new_pos
                    self._pending.pop("player", None)
            else:
                self._pending["player"] = {
                    "new": new_pos,
                    "settle": now + self._bounce_lag,
                }

        ol = self._prev.get("leader_raw_name")
        nl = current.get("leader_raw_name")
        if nl and nl != ol:
            c.leader_changed = True

        if current.get("session_phase") != self._prev.get("session_phase"):
            c.session_phase_changed = True

        prev_names = set(self._prev_rivals.keys())
        curr_names = set(r["driver_raw_name"] for r in current.get("rivals", []))
        c.retired_drivers = prev_names - curr_names
        c.new_drivers = curr_names - prev_names

        curr_d = {r["driver_raw_name"]: r for r in current.get("rivals", [])}
        for n in curr_names & prev_names:
            pr = self._prev_rivals.get(n)
            cr = curr_d.get(n)
            if pr and cr:
                if not pr.get("in_pits") and cr.get("in_pits"):
                    c.pit_entries.add(n)
                if pr.get("in_pits") and not cr.get("in_pits"):
                    c.pit_exits.add(n)

        self._prev = deepcopy(current)
        self._prev_rivals = deepcopy(curr_d)
        return c
