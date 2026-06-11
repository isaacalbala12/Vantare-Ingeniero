import asyncio
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_telemetry_loop_uses_strategy_service_snapshot_when_native():
    from src.routers import websocket as ws_mod

    app_state = MagicMock()
    strategy = MagicMock()
    strategy.snapshot_frame.return_value = {
        "lap_number": 3,
        "speed": 55.0,
        "session_type_int": 10,
        "num_penalties": 0,
    }
    app_state.strategy_service = strategy
    app_state.telemetry_hub = None  # sin hub → fallback snapshot_frame (native path)
    app_state.spotter_service = None
    app_state.crewchief_game_state_loop = None
    app_state.telemetry_reader = MagicMock()

    with patch.object(ws_mod, "native_telemetry_enabled", return_value=True):
        with patch.object(ws_mod, "mp_encode", return_value=b""):
            ws = MagicMock()
            ws.send_bytes = AsyncMock()
            task = asyncio.create_task(
                ws_mod.telemetry_sender_loop(ws, app_state)
            )
            await asyncio.sleep(0.12)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    assert strategy.snapshot_frame.call_count >= 2


def test_snapshot_frame_does_not_call_rest(monkeypatch, mock_race_state):
    from src.services.strategy_service import StrategyService

    reader = MagicMock()
    reader.get_state.return_value = mock_race_state
    reader.offline = True
    reader.shmm = None
    svc = StrategyService(reader)
    svc._cached_brake_wear = {"fl": 0.0, "fr": 0.0, "rl": 0.0, "rr": 0.0}

    def _boom(endpoint):
        raise AssertionError("REST must not run at 20 Hz")

    monkeypatch.setattr("src.services.strategy_service.get_additional_data", _boom)
    result = svc.snapshot_frame()
    assert result is not None


def test_snapshot_and_process_cycle_use_frame_lock():
    from src.services.strategy_service import StrategyService

    reader = MagicMock()
    reader.get_state.return_value = MagicMock(player=MagicMock(current_lap=1, in_pits=False))
    reader.offline = True
    svc = StrategyService(reader)
    assert isinstance(svc._frame_lock, type(threading.Lock()))
