import sys
from unittest.mock import MagicMock, patch

from src.app_runtime.runtime import is_windows, native_telemetry_enabled


def test_is_windows_on_win32():
    with patch.object(sys, "platform", "win32"):
        assert is_windows() is True


def test_is_windows_false_on_linux():
    with patch.object(sys, "platform", "linux"):
        assert is_windows() is False


def test_native_telemetry_default_true_on_windows():
    with patch.object(sys, "platform", "win32"):
        with patch.dict("os.environ", {"VANTARE_NATIVE_TELEMETRY": "1"}, clear=False):
            assert native_telemetry_enabled() is True


def test_native_telemetry_can_be_disabled():
    with patch.object(sys, "platform", "win32"):
        with patch.dict("os.environ", {"VANTARE_NATIVE_TELEMETRY": "0"}, clear=False):
            assert native_telemetry_enabled() is False


def test_native_telemetry_false_on_linux_even_with_env():
    with patch.object(sys, "platform", "linux"):
        with patch.dict("os.environ", {"VANTARE_NATIVE_TELEMETRY": "1"}, clear=False):
            assert native_telemetry_enabled() is False


def test_health_reports_native_source_when_connected():
    from fastapi import FastAPI
    from starlette.testclient import TestClient
    from src.routers.health import router as health_router

    app = FastAPI()
    app.include_router(health_router)
    reader = MagicMock()
    reader.offline = False
    reader.get_state.return_value = MagicMock(player=MagicMock(current_lap=2))
    app.state.telemetry_reader = reader

    with patch("src.routers.health.native_telemetry_enabled", return_value=True):
        with TestClient(app) as client:
            data = client.get("/health").json()
            assert data["telemetry"]["source"] == "native"
