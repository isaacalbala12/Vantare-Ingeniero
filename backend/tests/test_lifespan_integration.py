"""Test integración lifespan: TestClient(app) + /health refleja wiring voice+race.

Requiere pygame hardware (no CI). Skip documentado si pygame mixer falla.
"""

import time

import pytest
from fastapi.testclient import TestClient
from src.main import app


def _pygame_available() -> bool:
    """Check if pygame mixer can init (requires audio hardware)."""
    try:
        import pygame

        pygame.mixer.init()
        pygame.mixer.quit()
        return True
    except Exception:
        return False


# Mark whole module as slow / hardware-dependent
pytestmark = [
    pytest.mark.timeout(15),  # 15s max for lifespan + health
]


@pytest.mark.skipif(
    not _pygame_available(),
    reason="pygame mixer init failed (no audio hardware / headless CI)",
)
def test_lifespan_health_voice_and_race_loop():
    """GET /health tras lifespan debe reflejar voice+race wiring.

    Verifica que el context manager lifespan arranca los componentes
    y que /health los reporta correctamente.
    """
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()

        # Estructura general
        assert body["status"] == "ok"

        # Voice wiring
        voice = body["voice"]
        assert voice["backend_playback"] is True
        assert voice["player"] is not None, "player debe estar inicializado"
        assert voice["player"] in (
            "PygameAudioPlayer",
            "MockAudioPlayer",
        ), f"player inesperado: {voice['player']}"

        # Race loop wiring
        race_loop = body["race_loop"]
        assert "tick_count" in race_loop
        assert race_loop["tick_count"] >= 0

        # Shared memory status (depende de si LMU shared memory existe)
        assert body["shared_memory"]["status"] in ("offline", "simulated", "connected")

        # Spotter present
        assert "enabled" in body["spotter"]

    # After context manager exit: lifespan shutdown completes


@pytest.mark.skipif(
    not _pygame_available(),
    reason="pygame mixer init failed (no audio hardware / headless CI)",
)
def test_lifespan_race_loop_advances():
    """Tick_count debe subir tras esperar breve tras lifespan arranque."""
    with TestClient(app) as client:
        r0 = client.get("/health")
        t0 = r0.json()["race_loop"]["tick_count"]

        time.sleep(0.15)

        r1 = client.get("/health")
        t1 = r1.json()["race_loop"]["tick_count"]

        assert t1 > t0, (
            f"race_loop no avanzó tras lifespan: t0={t0} t1={t1} (puede que telemetry loop no emita ticks sin LMU)"
        )
