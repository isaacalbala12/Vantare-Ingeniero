import asyncio
import json
import logging
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.models.messages import BaseMessage
from src.services.msgpack_codec import encode as mp_encode, decode as mp_decode, apply_delta, is_full_frame

logger = logging.getLogger("vantare.websocket")

router = APIRouter()


async def _safe_evaluate_cycle(engine, frame, advice) -> None:
    """Wrapper seguro para evaluate_cycle que captura excepciones sin tirar abajo el WebSocket."""
    try:
        await engine.evaluate_cycle(frame, advice)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"evaluate_cycle failed: {e}", exc_info=True)


async def _safe_handle_pilot_question(engine, question: str) -> None:
    """Wrapper seguro para handle_pilot_question que captura excepciones sin tirar abajo el WebSocket."""
    try:
        await engine.handle_pilot_question(question)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"handle_pilot_question failed: {e}", exc_info=True)


class ConnectionManager:
    """Administrador de conexiones WebSocket para múltiples clientes Tauri."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"New client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.discard(websocket)
        logger.info(f"Client disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast(self, message: BaseMessage) -> None:
        """Transmite un mensaje Pydantic tipado a todos los clientes WebSocket conectados."""
        if not self.active_connections:
            return
        payload = message.model_dump(mode="json")
        # Emitir en paralelo a todos los clientes
        await asyncio.gather(
            *(conn.send_json({"event": message.event, "data": payload}) for conn in self.active_connections),
            return_exceptions=True
        )


manager = ConnectionManager()


def broadcast_sync(message: BaseMessage) -> None:
    """Envoltura síncrona para difundir mensajes desde la capa de inteligencia."""
    try:
        loop = asyncio.get_running_loop()
        if loop.is_running():
            loop.create_task(manager.broadcast(message))
    except RuntimeError:
        # En caso de que no haya un event loop corriendo (por ejemplo en tests)
        pass


async def telemetry_sender_loop(websocket: WebSocket, app_state) -> None:
    """Emite telemetría cruda a 20Hz (cada 50ms) y evalúa el Spotter en cada tick."""
    reader = getattr(app_state, "telemetry_reader", None)
    if not reader:
        logger.warning("Telemetry reader not found in app state")
        return

    while True:
        try:
            # 1. Preferir telemetry del sidecar si está disponible
            sidecar_frame = getattr(app_state, "latest_strategy_frame", None)
            if sidecar_frame and sidecar_frame.get("frame"):
                # El sidecar envía frame como dict, usar directamente
                state_dict = sidecar_frame["frame"]
                logger.debug("Usando telemetry del sidecar")
            else:
                # 2. Fallback: usar TelemetryReader local (simulated/offline)
                state = reader.get_state()
                if state is not None:
                    state_dict = state.model_dump(mode="json")
                else:
                    await asyncio.sleep(0.05)
                    continue
                logger.debug("Usando TelemetryReader (offline)")

            # 3. Evaluar el SpotterService de ultra-baja latencia (20Hz)
            # Spotter requiere RaceState (Pydantic model), no dict
            spotter = getattr(app_state, "spotter_service", None)
            if spotter:
                reader_state = reader.get_state()
                if reader_state is not None:
                    spotter.evaluate_tick(reader_state)

            # 4. Enviar datos al frontend vía MessagePack
            raw = mp_encode(state_dict)
            await websocket.send_bytes(raw)

            await asyncio.sleep(0.05)  # 20Hz (50ms)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Error sending telemetry: {e}")
            break


async def strategy_sender_loop(websocket: WebSocket, app_state, active_subtasks: Set[asyncio.Task] = None) -> None:
    """Emite consejos de estrategia a 0.5Hz (cada 2s) y evalúa los triggers de la capa de inteligencia."""
    strategy_service = getattr(app_state, "strategy_service", None)
    if not strategy_service:
        logger.warning("Strategy service not found in app state")
        return

    last_advice_dict = None

    while True:
        try:
            # No ejecutar triggers si no hay clientes conectados
            if not manager.active_connections:
                await asyncio.sleep(2.0)
                continue

            # 1. Intentar usar strategy_frame del sidecar Windows
            sidecar_frame = getattr(app_state, "latest_strategy_frame", None)
            if sidecar_frame:
                advice = sidecar_frame.get("advice")
                frame = sidecar_frame.get("frame")
                if advice is not None:
                    advice_dict = advice if isinstance(advice, dict) else advice.model_dump(mode="json")
                    logger.debug("Usando strategy_frame del sidecar Windows")
                else:
                    advice_dict = None
            else:
                # 2. Fallback: usar StrategyService local
                advice = strategy_service.get_latest_advice()
                if advice is not None:
                    advice_dict = advice.model_dump(mode="json")
                    logger.debug("Usando StrategyService offline (sidecar no detectado)")
                else:
                    advice_dict = None

                # Resolver frame desde telemetry_reader
                frame = getattr(app_state, "latest_client_frame", None)
                if not frame:
                    reader = getattr(app_state, "telemetry_reader", None)
                    if reader:
                        frame = reader.get_state()

            if advice_dict is not None:
                # Evaluar la capa de inteligencia y triggers tácticos
                engine = getattr(app_state, "intelligence_engine", None)
                if engine and frame:
                    task = asyncio.create_task(_safe_evaluate_cycle(engine, frame, advice))
                    if active_subtasks is not None:
                        task.add_done_callback(active_subtasks.discard)
                        active_subtasks.add(task)

                # Emitir solo si ha cambiado el contenido estratégico para reducir ancho de banda
                if advice_dict != last_advice_dict:
                    await websocket.send_json({
                        "event": "strategy",
                        "data": advice_dict
                    })
                    last_advice_dict = advice_dict

            await asyncio.sleep(2.0)  # 0.5Hz (2s)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Error sending strategy advice: {e}")
            break


async def _index_events_async(event_store, frame: dict, events: list[dict]) -> None:
    """Indexa eventos en EventStore de forma asíncrona (no bloquea el WS loop)."""
    try:
        batches: list[tuple[dict, str, int]] = []
        for evt in events:
            event_type = evt.get("type", "unknown")
            lap = evt.get("lap", 1)
            batches.append((frame, event_type, lap))

        if batches:
            event_store.store_events_batch(batches)
            logger.debug("Indexados %d eventos en EventStore", len(batches))
    except Exception as e:
        logger.warning("Error indexing events in EventStore: %s", e)


@router.websocket("/ws/sidecar")
async def sidecar_endpoint(websocket: WebSocket):
    """Endpoint dedicado para el sidecar StrategyService en Windows.
    
    Solo recibe strategy_frame, sin loops de telemetría ni estrategia fantasma.
    """
    await websocket.accept()
    app_state = websocket.app.state
    logger.info("Sidecar conectado en /ws/sidecar")
    try:
        while True:
            data = await websocket.receive_json()
            event = data.get("event", "")
            if event == "strategy_frame":
                frame_data = data.get("data", {})
                if frame_data:
                    app_state.latest_strategy_frame = frame_data
                    logger.debug("strategy_frame recibido del sidecar")

                    # Indexar eventos en EventStore (RAG) — asíncrono, no bloquea
                    events = frame_data.get("events", [])
                    if events and hasattr(app_state, "event_store"):
                        frame = frame_data.get("frame", {})
                        event_store = app_state.event_store
                        asyncio.ensure_future(
                            _index_events_async(event_store, frame, events)
                        )
    except WebSocketDisconnect:
        logger.info("Sidecar desconectado de /ws/sidecar")
    except Exception as e:
        logger.warning(f"Error en sidecar endpoint: {e}")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Ruta WebSocket para la telemetría en tiempo real y la estrategia."""
    await manager.connect(websocket)
    
    # Crear tareas Concurrentes para este socket
    app_state = websocket.app.state
    active_subtasks: Set[asyncio.Task] = set()
    telemetry_task = asyncio.create_task(telemetry_sender_loop(websocket, app_state))
    strategy_task = asyncio.create_task(strategy_sender_loop(websocket, app_state, active_subtasks))

    try:
        # Loop principal para mantener la conexión viva y escuchar mensajes entrantes
        while True:
            # Recibir texto o binario (el frontend envía WAV Blob como binario)
            raw = await websocket.receive()
            if raw.get("type") == "websocket.receive":
                if "text" in raw:
                    data = raw["text"]
                elif "bytes" in raw:
                    # Mensaje binario (MessagePack telemetry del frontend)
                    try:
                        frame = mp_decode(raw["bytes"])
                        
                        # Detectar gap de timestamps para diagnóstico
                        frame_ts = frame.get("_t", 0)
                        last_ts = getattr(app_state, "_last_telemetry_t", 0)
                        if last_ts > 0 and frame_ts - last_ts > 0.5:
                            logger.warning(f"Telemetry gap detected: {frame_ts - last_ts:.2f}s since last frame")
                        app_state._last_telemetry_t = frame_ts
                        
                        # Aplicar delta o snapshot completo
                        if is_full_frame(frame):
                            app_state.latest_client_frame = frame
                        else:
                            mp_delta = {k: v for k, v in frame.items() if not k.startswith("_")}
                            if getattr(app_state, "latest_client_frame", None) is not None:
                                app_state.latest_client_frame = apply_delta(app_state.latest_client_frame, mp_delta)
                            else:
                                # Primer frame tras conexión, guardar como está
                                app_state.latest_client_frame = frame
                    except Exception as e:
                        logger.warning(f"Error decoding MessagePack telemetry: {e}")
                    continue
                else:
                    continue
            elif raw.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(code=raw.get("code", 1000))
            else:
                continue
            
            # Procesar mensajes JSON del cliente
            try:
                msg = json.loads(data)
                event = msg.get("event", "")
                
                if event == "telemetry":
                    # Almacenar la telemetría entrante del frontend para que strategy_sender_loop la use
                    telemetry_data = msg.get("data", {})
                    if telemetry_data:
                        app_state.latest_client_frame = telemetry_data
                elif event == "pilot_question":
                    question = msg.get("data", {}).get("question", "")
                    if question:
                        logger.info(f"[WS] Pregunta del piloto recibida: {question[:80]}...")
                        engine = getattr(app_state, "intelligence_engine", None)
                        if engine:
                            task = asyncio.create_task(_safe_handle_pilot_question(engine, question))
                            task.add_done_callback(active_subtasks.discard)
                            active_subtasks.add(task)
                        else:
                            logger.warning("[WS] IntelligenceEngine no disponible para procesar pregunta")
            except json.JSONDecodeError:
                logger.debug(f"Mensaje no-JSON recibido: {data[:100]}")
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed by client")
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}", exc_info=True)
    finally:
        # Cancelar todas las subtareas activas
        for t in list(active_subtasks):
            t.cancel()
        if active_subtasks:
            await asyncio.gather(*active_subtasks, return_exceptions=True)
        active_subtasks.clear()

        # Detener las tareas emisoras
        telemetry_task.cancel()
        strategy_task.cancel()
        
        # Esperar a que terminen de forma limpia
        await asyncio.gather(telemetry_task, strategy_task, return_exceptions=True)
        
        # Desconectar el cliente de la lista activa
        manager.disconnect(websocket)

