import asyncio
import json
import logging
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from src.app_runtime.runtime import native_telemetry_enabled
from src.config import settings
from src.models.messages import BaseMessage, ConfigAckMessage
from src.services.msgpack_codec import apply_delta, is_full_frame
from src.services.msgpack_codec import decode as mp_decode
from src.services.msgpack_codec import encode as mp_encode

logger = logging.getLogger("vantare.websocket")

router = APIRouter()

MAX_PILOT_QUESTION_LEN = 512

TELEMETRY_INTERVAL_S = 0.05
UI_TELEMETRY_INTERVAL_S = 0.1  # 10 Hz UI broadcast
STRATEGY_INTERVAL_S = 2.0


def compute_loop_sleep(interval_s: float, loop_started_at: float) -> float:
    """Segundos restantes para mantener la frecuencia objetivo del bucle."""
    elapsed = time.monotonic() - loop_started_at
    return max(0.0, interval_s - elapsed)


def _normalize_pilot_question(question: str) -> str | None:
    cleaned = (question or "").strip()
    if not cleaned:
        return None
    if len(cleaned) > MAX_PILOT_QUESTION_LEN:
        logger.warning(
            "pilot_question truncado de %d a %d caracteres",
            len(cleaned),
            MAX_PILOT_QUESTION_LEN,
        )
        return cleaned[:MAX_PILOT_QUESTION_LEN]
    return cleaned


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
        self.active_connections: set[WebSocket] = set()

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
            return_exceptions=True,
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
    """Broadcast last snapshot from TelemetryHub to UI (~10 Hz). No race logic here."""
    while True:
        loop_started_at = time.monotonic()
        try:
            state_dict = None
            hub = getattr(app_state, "telemetry_hub", None)
            if hub is not None:
                state_dict, _ = hub.get_latest()

            if state_dict is None:
                strategy_service = getattr(app_state, "strategy_service", None)
                if strategy_service and hasattr(strategy_service, "snapshot_frame"):
                    state_dict = strategy_service.snapshot_frame()
                else:
                    reader = getattr(app_state, "telemetry_reader", None)
                    if reader:
                        state = reader.get_state()
                        if state is not None:
                            state_dict = state.model_dump(mode="json")

            if state_dict is None:
                await asyncio.sleep(UI_TELEMETRY_INTERVAL_S)
                continue

            raw = mp_encode(state_dict)
            await websocket.send_bytes(raw)

            await asyncio.sleep(compute_loop_sleep(UI_TELEMETRY_INTERVAL_S, loop_started_at))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Error sending telemetry: %s", e)
            break


async def strategy_sender_loop(websocket: WebSocket, app_state, active_subtasks: set[asyncio.Task] = None) -> None:
    """Emite consejos de estrategia a 0.5Hz (cada 2s) y evalúa los triggers de la capa de inteligencia."""
    strategy_service = getattr(app_state, "strategy_service", None)
    if not strategy_service:
        logger.warning("Strategy service not found in app state")
        return

    last_advice_dict = None

    while True:
        loop_started_at = time.monotonic()
        try:
            # No ejecutar triggers si no hay clientes conectados
            if not manager.active_connections:
                await asyncio.sleep(STRATEGY_INTERVAL_S)
                continue

            # Obtener frame y advice desde StrategyService (telemetría nativa o offline)
            advice = strategy_service.get_latest_advice()
            if advice is not None:
                advice_dict = advice.model_dump(mode="json")
                logger.debug("Usando StrategyService local")
            else:
                advice_dict = None

            if native_telemetry_enabled() and strategy_service.latest_frame is not None:
                frame = strategy_service.latest_frame.model_dump(mode="json")
            else:
                frame = getattr(app_state, "latest_client_frame", None)
                if not frame:
                    reader = getattr(app_state, "telemetry_reader", None)
                    if reader:
                        state = reader.get_state()
                        frame = state.model_dump(mode="json") if state is not None else None

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
                    await websocket.send_json({"event": "strategy", "data": advice_dict})
                    last_advice_dict = advice_dict

            await asyncio.sleep(compute_loop_sleep(STRATEGY_INTERVAL_S, loop_started_at))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug("Error sending strategy advice: %s", e)
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
            await asyncio.to_thread(event_store.store_events_batch, batches)
            logger.debug("Indexados %d eventos en EventStore", len(batches))
    except Exception as e:
        logger.warning("Error indexing events in EventStore: %s", e)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Ruta WebSocket para la telemetría en tiempo real y la estrategia."""
    await manager.connect(websocket)

    # Crear tareas Concurrentes para este socket
    app_state = websocket.app.state
    active_subtasks: set[asyncio.Task] = set()
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
                        trace_store = getattr(app_state, "trace_store", None)
                        if trace_store and trace_store.is_recording and app_state.latest_client_frame:
                            trace_store.append_frame(app_state.latest_client_frame)
                        mqtt_svc = getattr(app_state, "mqtt_service", None)
                        if mqtt_svc and app_state.latest_client_frame:
                            mqtt_svc.enqueue_telemetry(app_state.latest_client_frame)
                    except Exception as e:
                        logger.warning(f"Error decoding MessagePack telemetry: {e}")
                    continue
                else:
                    continue
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
                        trace_store = getattr(app_state, "trace_store", None)
                        if trace_store and trace_store.is_recording:
                            trace_store.append_frame(telemetry_data)
                elif event == "config_update":
                    cfg = msg.get("data", {})
                    engine = getattr(app_state, "intelligence_engine", None)
                    if engine is not None and hasattr(engine, "apply_runtime_config"):
                        engine.apply_runtime_config(cfg)
                    spotter = getattr(app_state, "spotter_service", None)
                    if spotter is not None and hasattr(spotter, "apply_runtime_config"):
                        spotter.apply_runtime_config(cfg)
                        if "spotterEnabled" in cfg:
                            logger.info("[WS] config spotterEnabled=%s", cfg["spotterEnabled"])
                    if "swearyMessages" in cfg:
                        app_state.sweary_messages = bool(cfg["swearyMessages"])
                        if engine is not None:
                            engine.sweary_messages = app_state.sweary_messages
                        logger.info("[WS] sweary_messages=%s", app_state.sweary_messages)
                    if spotter is not None:
                        if "spotterOffQualifying" in cfg:
                            spotter.spotter_off_qualifying = bool(cfg["spotterOffQualifying"])
                        if "spotterExcludeStopped" in cfg:
                            spotter.spotter_exclude_stopped = bool(cfg["spotterExcludeStopped"])
                    if engine is not None and hasattr(engine, "runtime_config_snapshot"):
                        await manager.broadcast(
                            ConfigAckMessage(
                                event="config_ack",
                                config=engine.runtime_config_snapshot(),
                            )
                        )
                elif event == "engineer_command":
                    action = msg.get("data", {}).get("action", "")
                    engine = getattr(app_state, "intelligence_engine", None)
                    if engine and action in ("enable", "disable"):
                        enabled = action == "enable"
                        engine.apply_runtime_config({"engineerEnabled": enabled})
                        engine.broadcast_config_ack()
                        logger.info("[WS] engineer enabled=%s", enabled)
                elif event == "spotter_command":
                    action = msg.get("data", {}).get("action", "")
                    spotter = getattr(app_state, "spotter_service", None)
                    engine = getattr(app_state, "intelligence_engine", None)
                    if action in ("enable", "disable") and spotter is not None:
                        enabled = action == "enable"
                        if engine is not None:
                            if engine._spotter_service is None:
                                engine._spotter_service = spotter
                            engine.apply_spotter_toggle(enabled)
                        else:
                            spotter.enabled = enabled
                            import uuid

                            from src.models.messages import AlertMessage

                            await manager.broadcast(
                                AlertMessage(
                                    event="alert",
                                    alert_id=str(uuid.uuid4()),
                                    category="spotter",
                                    message="Spotter activado." if enabled else "Spotter desactivado.",
                                    audio_priority="NORMAL",
                                    severity="INFO",
                                    ttl=8,
                                    dismissable=True,
                                    payload={"service": "spotter"},
                                )
                            )
                        logger.info("[WS] spotter enabled=%s", enabled)
                elif event == "test_audio":
                    voice_queue = getattr(app_state, "voice_queue", None)
                    if voice_queue is not None and settings.VOICE_BACKEND_PLAYBACK:
                        from src.voice.play_command import play_command_from_alert

                        cmd = play_command_from_alert(
                            text="Probando audio. ¿Me escuchás?",
                            category="engineer",
                            audio_priority="NORMAL",
                            event_id="test_audio",
                            ttl_seconds=10,
                            payload={"event_id": "test_audio"},
                        )
                        await voice_queue.put(cmd)
                        logger.info("[WS] test_audio enqueued")
                    else:
                        logger.warning("[WS] test_audio ignored — voice queue unavailable")
                elif event == "pilot_question":
                    raw_question = msg.get("data", {}).get("question", "")
                    question = _normalize_pilot_question(raw_question)
                    if question:
                        logger.info("[WS] Pregunta del piloto recibida: %s...", question[:80])
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
