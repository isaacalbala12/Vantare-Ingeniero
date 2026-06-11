from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_play_bytes_stops_immediate_when_busy():
    fake_mixer = MagicMock()
    fake_mixer.music.get_busy.side_effect = [True, True, False]
    with patch("src.voice.player_pygame.pygame") as pg:
        pg.mixer = fake_mixer
        from src.voice.player_pygame import PygameAudioPlayer

        player = PygameAudioPlayer()
        await player.play_bytes(b"data", priority="IMMEDIATE")
    fake_mixer.music.stop.assert_called_once()
