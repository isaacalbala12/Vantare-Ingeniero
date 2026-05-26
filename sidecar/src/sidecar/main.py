"""
Entrypoint del sidecar StrategyService.

Corre en Windows junto a LMU:
1. Conecta WebSocket al backend Linux (/ws/sidecar)
2. Lee shared memory real (TelemetryReader offline=False)
3. Cada 2s: StrategyRunner.process_cycle() → StateChangeDetector.detect() → envía strategy_frame
"""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path

import websockets
from dotenv import load_dotenv

# Añadir shared libs al path si están en modo editable
_sidecar_root = Path(__file__).resolve().parent.parent.parent  # sidecar/
_repo_root = _sidecar_root.parent  # Vantare-Ingeniero/
_shared_telemetry = _repo_root / "shared-telemetry" / "src"
_shared_strategy = _repo_root / "shared-strategy" / "src"
for _p in (_shared_telemetry, _shared_strategy):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from shared_telemetry import TelemetryReader
from sidecar.strategy_runner import StrategyRunner
from sidecar.event_detector import StateChangeDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] sidecar: %(message)s"
)
logger = logging.getLogger("vantare.sidecar")

# Evento para graceful shutdown
_shutdown_event = asyncio.Event()


def _signal_handler() -> None:
    """Maneja Ctrl+C y señales de terminación."""
    logger.info("Señal de shutdown recibida. Cerrando sidecar...")
    _shutdown_event.set()


async def main() -> None:
    """Loop principal del sidecar."""
    load_dotenv()
    ws_url = os.getenv("BACKEND_WS_URL", "ws://127.0.0.1:8008/ws/sidecar")

    logger.info("Iniciando sidecar StrategyService...")
    logger.info("Backend WebSocket: %s", ws_url)

    # 1. Inicializar lector de shared memory real (offline=False)
    reader = TelemetryReader(offline=False, poll_rate=0.05)  # 20Hz interno
    reader.start()
    logger.info("TelemetryReader started (offline=False, 20Hz)")

    # 2. Inicializar motor de estrategia y detector de eventos
    runner = StrategyRunner(reader)
    detector = StateChangeDetector()

    # Registrar signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _signal_handler)
        except NotImplementedError:
            # Windows no soporta add_signal_handler
            pass

    consecutive_errors = 0
    max_consecutive_errors = 10

    while not _shutdown_event.is_set():
        try:
            async with websockets.connect(ws_url, ping_interval=15, ping_timeout=5) as ws:
                logger.info("Conectado al backend en %s", ws_url)
                consecutive_errors = 0

                while not _shutdown_event.is_set():
                    try:
                        await asyncio.sleep(2.0)

                        # 3. Procesar ciclo de estrategia
                        runner.process_cycle()

                        if runner.latest_frame is None or runner.latest_advice is None:
                            continue

                        # 4. Detectar eventos
                        events = detector.detect(runner.latest_frame)

                        # 5. Construir y enviar strategy_frame
                        payload = {
                            "event": "strategy_frame",
                            "data": {
                                "advice": runner.latest_advice.model_dump(mode="json"),
                                "frame": runner.latest_frame.model_dump(mode="json"),
                                "events": events,
                            }
                        }
                        await ws.send(json.dumps(payload))

                        if events:
                            logger.debug("Enviados %d eventos al backend", len(events))

                    except websockets.ConnectionClosed:
                        logger.warning("Conexión WebSocket cerrada por el backend")
                        break

        except (websockets.ConnectionClosed, OSError, ConnectionRefusedError) as e:
            consecutive_errors += 1
            if consecutive_errors > max_consecutive_errors:
                logger.error("Demasiados errores consecutivos (%d). Saliendo.", consecutive_errors)
                break
            wait_time = min(2 ** consecutive_errors, 30)
            logger.warning("Error de conexión (%d/%d): %s. Reintentando en %ds...",
                           consecutive_errors, max_consecutive_errors, e, wait_time)
            await asyncio.sleep(wait_time)
        except Exception as e:
            logger.error("Error inesperado en el loop principal: %s", e, exc_info=True)
            consecutive_errors += 1
            if consecutive_errors > max_consecutive_errors:
                break
            await asyncio.sleep(5.0)

    # Cleanup
    reader.stop()
    logger.info("Sidecar detenido.")


if __name__ == "__main__":
    asyncio.run(main())
