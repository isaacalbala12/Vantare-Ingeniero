"""EventEngine: dispatch secuencial de eventos con timeout y auto-disable.

Patrón:
- 29 eventos registrados por nombre
- Cada tick: ordenar por sequence, ejecutar los aplicables
- Timeout 2s por evento (no bloquea el loop)
- Tras 10 fallos consecutivos, el evento se desactiva
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from src.models.game_state_data import GameStateData
from src.intelligence.base_event import AbstractEvent

logger = logging.getLogger("vantare.event_engine")


class EventEngine:
    MAX_FAIL = 10
    TIMEOUT = 2.0

    def __init__(self, ap: Any = None, audio_player: Any = None) -> None:
        if ap is None and audio_player is not None:
            ap = audio_player
        self._events: Dict[str, AbstractEvent] = {}
        self._fail_counts: Dict[str, int] = {}
        self._has_any_fail: bool = False
        self.ap = ap

    def register(self, name: str, event: AbstractEvent) -> None:
        self._events[name] = event

    register_event = register

    def unregister(self, name: str) -> None:
        self._events.pop(name, None)
        self._fail_counts.pop(name, None)

    def clear_all(self) -> None:
        for ev in self._events.values():
            try:
                ev.clear_state()
            except Exception as e:
                logger.error(f"clear_state failed for {type(ev).__name__}: {e}")
        self._fail_counts.clear()
        self._has_any_fail = False

    clear_all_state = clear_all

    async def tick(
        self,
        prev: Optional[GameStateData],
        curr: Optional[GameStateData],
    ) -> None:
        if curr is None:
            return

        st = curr.session.session_type
        sp = curr.session.session_phase

        # Ordenar por sequence, luego por key de registro (determinista)
        ordered = sorted(
            self._events.items(),
            key=lambda kv: (kv[1].sequence, kv[0]),
        )

        loop = asyncio.get_event_loop()
        for name, ev in ordered:
            if not ev.applicable(st, sp):
                continue
            try:
                if ev.should_suppress(curr):
                    continue
            except Exception as e:
                logger.error(f"should_suppress failed in {name}: {e}")
                continue

            if self._has_any_fail and self._fail_counts.get(name, 0) >= self.MAX_FAIL:
                continue

            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, ev.trigger_internal, prev, curr),
                    timeout=self.TIMEOUT,
                )
                # Éxito: reset contador
                if name in self._fail_counts:
                    self._fail_counts[name] = 0
            except asyncio.TimeoutError:
                fail = self._fail_counts.get(name, 0) + 1
                self._fail_counts[name] = fail
                logger.error(
                    f"TIMEOUT in {name} ({fail}/{self.MAX_FAIL})"
                )
                if fail >= self.MAX_FAIL:
                    self._has_any_fail = True
                    logger.error(
                        f"{name} disabled after {fail} consecutive failures"
                    )
            except Exception as e:
                fail = self._fail_counts.get(name, 0) + 1
                self._fail_counts[name] = fail
                logger.error(
                    f"FAIL in {name} ({fail}/{self.MAX_FAIL}): {e}",
                    exc_info=False,
                )
                if fail >= self.MAX_FAIL:
                    self._has_any_fail = True

    def get(self, name: str) -> Optional[AbstractEvent]:
        return self._events.get(name)

    def get_fail_count(self, name: str) -> int:
        return self._fail_counts.get(name, 0)

    def is_disabled(self, name: str) -> bool:
        return self._fail_counts.get(name, 0) >= self.MAX_FAIL

    def registered_names(self) -> list:
        return list(self._events.keys())

    tick_async = tick
