import logging
import asyncio
from src.routers.websocket import broadcast_sync

logger = logging.getLogger("vantare.broadcaster")

def send(message) -> None:
    """Envía un mensaje al frontend a través del WebSocket broadcaster."""
    try:
        broadcast_sync(message)
    except Exception as e:
        logger.error(f"Error broadcasting message: {e}")
