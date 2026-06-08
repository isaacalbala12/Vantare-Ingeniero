"""Task 49-S9: sidecar route and frame state must not exist post-cutover."""

from fastapi.routing import APIWebSocketRoute


def test_sidecar_ws_route_removed():
    from src.main import app

    ws_paths = [
        getattr(r, "path", "")
        for r in app.routes
        if isinstance(r, APIWebSocketRoute)
    ]
    assert "/ws/sidecar" not in ws_paths


def test_main_has_no_latest_strategy_frame_state():
    import inspect
    import src.main as main_mod

    source = inspect.getsource(main_mod)
    assert "latest_strategy_frame" not in source


def test_websocket_native_only_frame_path():
    import inspect
    import src.routers.websocket as ws_mod

    source = inspect.getsource(ws_mod.telemetry_sender_loop)
    assert "sidecar_frame" not in source
    assert "latest_strategy_frame" not in source
