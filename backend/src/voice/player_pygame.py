from __future__ import annotations

import asyncio
import io
import logging

logger = logging.getLogger("vantare.pygame_player")

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore[assignment]


class MockAudioPlayer:
    def __init__(self) -> None:
        self.played: list[str] = []

    async def play_text(self, text: str, *, priority: str) -> None:
        self.played.append(text)


class PygameAudioPlayer:
    def __init__(self) -> None:
        if pygame is None:
            raise RuntimeError("pygame not installed")
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._lock = asyncio.Lock()

    async def play_bytes(self, data: bytes, *, priority: str) -> None:
        async with self._lock:
            if priority == "IMMEDIATE" and pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            buf = io.BytesIO(data)
            pygame.mixer.music.load(buf, namehint="alert.mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                await asyncio.sleep(0.02)

    async def play_text(self, text: str, *, priority: str) -> None:
        logger.warning("play_text without bytes — mock fallback: %s", text[:40])
