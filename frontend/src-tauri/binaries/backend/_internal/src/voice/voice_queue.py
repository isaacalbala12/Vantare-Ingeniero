from __future__ import annotations

import asyncio

from src.voice.play_command import PlayCommand

PRIORITY_RANK = {"IMMEDIATE": 0, "NORMAL": 1, "ENGINEER": 2}


class VoiceQueue:
    def __init__(self, maxsize: int = 16) -> None:
        self._queue: asyncio.PriorityQueue[tuple[int, int, PlayCommand]] = asyncio.PriorityQueue(maxsize=maxsize)
        self._seq = 0

    async def _evict_one(self) -> None:
        items: list[tuple[int, int, PlayCommand]] = []
        while not self._queue.empty():
            items.append(self._queue.get_nowait())
        if not items:
            return
        # Remove item with highest rank (lowest priority); on tie, drop oldest (lowest seq)
        worst = max(range(len(items)), key=lambda i: (items[i][0], -items[i][1]))
        del items[worst]
        for item in items:
            self._queue.put_nowait(item)

    async def put(self, cmd: PlayCommand) -> None:
        rank = PRIORITY_RANK.get(cmd.priority, 9)
        if self._queue.full():
            await self._evict_one()
        self._seq += 1
        await self._queue.put((rank, self._seq, cmd))

    async def get(self) -> PlayCommand:
        _, _, cmd = await self._queue.get()
        return cmd

    def qsize(self) -> int:
        return self._queue.qsize()
