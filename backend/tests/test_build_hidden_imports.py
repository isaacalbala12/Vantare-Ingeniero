"""Hidden imports PyInstaller deben cubrir módulos voice/race críticos."""

from pathlib import Path

VOICE_RACE_MODULES = [
    "src.race.tick_loop",
    "src.race.telemetry_hub",
    "src.voice.bridge",
    "src.voice.playback_notify",
    "src.voice.service",
    "src.voice.player_pygame",
    "src.voice.voice_queue",
    "src.voice.play_command",
    "src.voice.spotter_cache",
    "src.voice.tts_manager",
    "pygame",
    "shared_telemetry",
    "shared_strategy",
]


def test_build_backend_hidden_imports_cover_voice_race():
    build_py = Path(__file__).resolve().parents[1] / "build_backend.py"
    text = build_py.read_text(encoding="utf-8")
    missing = [mod for mod in VOICE_RACE_MODULES if mod not in text]
    assert not missing, f"build_backend.py missing hidden imports: {missing}"
