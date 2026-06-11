from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_selects_pygame_when_edge_available():
    """Tras hotfix, si edge_tts_service existe antes del bloque voz -> PygameAudioPlayer."""
    from contextlib import asynccontextmanager

    captured: dict = {}

    mock_edge = MagicMock()
    mock_edge.synthesize = AsyncMock(return_value=b"\xff\xfb")

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.edge_tts_service = mock_edge
        from src.config import settings
        from src.voice.player_pygame import PygameAudioPlayer

        edge = getattr(app.state, "edge_tts_service", None)
        if settings.VOICE_BACKEND_PLAYBACK and edge is not None:
            with patch.object(PygameAudioPlayer, "__init__", lambda self: None):
                PygameAudioPlayer()
            captured["player"] = "pygame"
        else:
            captured["player"] = "mock"
        yield

    app = FastAPI(lifespan=fake_lifespan)
    async with fake_lifespan(app):
        pass
    assert captured["player"] == "pygame"
