import asyncio
import json
import logging
import time
from typing import Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.models.messages import BaseMessage
from src.platform.runtime import native_telemetry_enabled
from src.intelligence.spotter_adapter import frame_to_spotter_tick
from src.services.msgpack_codec import encode as mp_encode, decode as mp_decode, apply_delta, is_full_frame

logger = logging.getLogger("vantare.websocket")

router = APIRouter()


def _enrich_frame_session(app_state, frame) -> tuple[dict, dict]:
    """Asegura session_type_int en frame desde StrategyService o telemetría LMU."""
    from shared_telemetry.session_kind import session_kind_from_lmu_int, sync_session_fields

    frame_dict = dict(frame if isinstance(frame, dict) else frame.model_dump(mode="json"))

    sti = frame_dict.get("session_type_int")
    if sti is None:
        svc = getattr(app_state, "strategy_service", None)
        latest = getattr(svc, "latest_frame", None) if svc else None
        if latest is not None:
            sti = getattr(latest, "session_type_int", None)
            if sti is None and hasattr(latest, "model_dump"):
                sti = latest.model_dump(mode="json").get("session_type_int")

    if sti is not None:
        frame_dict["session_type_int"] = int(sti)
        frame_dict["session_type"] = session_kind_from_lmu_int(int(sti))

    session_state = {
        "phase": frame_dict.get("session_type", "race"),
        "session_type_int": frame_dict.get("session_type_int"),
    }
    return sync_session_fields(frame_dict, session_state)


def _resolve_telemetry_frame(app_state, reader) -> dict | None:
    strategy_service = getattr(app_state, "strategy_service", None)
    if strategy_service and hasattr(strategy_service, "snapshot_frame"):
        state_dict = strategy_service.snapshot_frame()
        if state_dict is not None:
            return state_dict
    if reader:
        state = reader.get_state()
        if state is not None:
            return state.model_dump(mode="json")
    return None


def _resolve_strategy_advice_dict(strategy_service) -> dict:
    if strategy_service is None:
        return {}
    advice = strategy_service.get_latest_advice()
    if advice is None:
        return {}
    return advice.model_dump(mode="json")


async def _safe_evaluate_cycle(engine, frame, advice, session_state=None) -> None:
    """Wrapper seguro para evaluate_cycle que captura excepciones sin tirar abajo el WebSocket."""
    try:
        await engine.evaluate_cycle(frame, advice, session_state)
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
        pass


async def telemetry_sender_loop(websocket: WebSocket, app_state) -> None:
    """Emite telemetría cruda a 20Hz (cada 50ms) y evalúa el Spotter en cada tick."""
    reader = getattr(app_state, "telemetry_reader", None)
    if not reader:
        logger.warning("Telemetry reader not found in app state")
        return

    strategy_service = getattr(app_state, "strategy_service", None)

    while True:
        try:
            state_dict = _resolve_telemetry_frame(app_state, reader)
            if state_dict is None:
                await asyncio.sleep(0.05)
                continue

            strategy_dict = _resolve_strategy_advice_dict(strategy_service)

            spotter = getattr(app_state, "spotter_service", None)
            if spotter:
                spotter_tick = frame_to_spotter_tick(state_dict, strategy_dict or None)
                spotter.evaluate_tick(spotter_tick)

            cc_loop = getattr(app_state, "crewchief_game_state_loop", None)
            if cc_loop and state_dict:
                state_for_cc, _ = _enrich_frame_session(app_state, state_dict)
                cc_loop.on_frame(
                    state_for_cc,
                    now=time.monotonic(),
                    strategy=strategy_dict,
                )

            raw = mp_encode(state_dict)
            await websocket.send_bytes(raw)

            await asyncio.sleep(0.05)
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
            if not manager.active_connections:
                await asyncio.sleep(2.0)
                continue

            advice = strategy_service.get_latest_advice()
            frame = strategy_service.latest_frame
            if frame is not None and hasattr(frame, "model_dump"):
                frame = frame.model_dump(mode="json")
            advice_dict = advice.model_dump(mode="json") if advice is not None else None

            if native_telemetry_enabled() and getattr(app_state, "event_store", None):
                events = strategy_service.get_latest_events()
                if events and frame is not None:
                    frame_dict = frame if isinstance(frame, dict) else frame.model_dump(mode="json")
                    asyncio.ensure_future(
                        _index_events_async(app_state.event_store, frame_dict, events)
                    )

            if advice_dict is not None:
                engine = getattr(app_state, "intelligence_engine", None)
                if engine and frame:
                    frame_dict, session_state = _enrich_frame_session(app_state, frame)
                    task = asyncio.create_task(
                        _safe_evaluate_cycle(engine, frame_dict, advice, session_state)
                    )
                    if active_subtasks is not None:
                        task.add_done_callback(active_subtasks.discard)
                        active_subtasks.add(task)

                if advice_dict != last_advice_dict:
                    payload = dict(advice_dict)
                    if frame is not None:
                        frame_dict = frame if isinstance(frame, dict) else frame.model_dump(mode="json")
                        for key in (
                            "time_gap_car_ahead",
                            "time_gap_car_behind",
                            "time_gap_place_ahead",
                            "time_gap_place_behind",
                        ):
                            if key in frame_dict:
                                payload[key] = frame_dict[key]
                    await websocket.send_json({
                        "event": "strategy",
                        "data": payload
                    })
                    last_advice_dict = advice_dict

            await asyncio.sleep(2.0)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Error sending strategy advice: {e}")
            break


async def _index_events_async(event_store, frame: dict, events: list[dict]) -> None:
    """Indexa eventos en EventStore sin bloquear el event loop (embeddings en thread)."""
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

    app_state = websocket.app.state
    cc_loop = getattr(app_state, "crewchief_game_state_loop", None)
    if cc_loop is not None and hasattr(cc_loop, "reset_flag_state"):
        cc_loop.reset_flag_state()
    active_subtasks: Set[asyncio.Task] = set()
    telemetry_task = asyncio.create_task(telemetry_sender_loop(websocket, app_state))
    strategy_task = asyncio.create_task(strategy_sender_loop(websocket, app_state, active_subtasks))

    try:
        while True:
            raw = await websocket.receive()
            if raw.get("type") == "websocket.disconnect":
                break
            if raw.get("type") != "websocket.receive":
                continue
            if "bytes" in raw:
                try:
                    frame = mp_decode(raw["bytes"])
                    frame_ts = frame.get("_t", 0)
                    last_ts = getattr(app_state, "_last_telemetry_t", 0)
                    if last_ts > 0 and frame_ts - last_ts > 0.5:
                        logger.warning(f"Telemetry gap detected: {frame_ts - last_ts:.2f}s since last frame")
                    app_state._last_telemetry_t = frame_ts
                    if is_full_frame(frame):
                        app_state.latest_client_frame = frame
                    else:
                        mp_delta = {k: v for k, v in frame.items() if not k.startswith("_")}
                        if getattr(app_state, "latest_client_frame", None) is not None:
                            app_state.latest_client_frame = apply_delta(app_state.latest_client_frame, mp_delta)
                        else:
                            app_state.latest_client_frame = frame
                    trace_store = getattr(app_state, "trace_store", None)
                    if trace_store and trace_store.is_recording and app_state.latest_client_frame:
                        trace_store.append_frame(app_state.latest_client_frame)
                    mqtt_svc = getattr(app_state, "mqtt_service", None)
                    if mqtt_svc and app_state.latest_client_frame:
                        asyncio.create_task(mqtt_svc.publish_telemetry(app_state.latest_client_frame))
                except Exception as e:
                    logger.warning(f"Error decoding MessagePack telemetry: {e}")
                continue
            if "text" not in raw:
                continue
            data = raw["text"]

            try:
                msg = json.loads(data)
                event = msg.get("event", "")

                if event == "telemetry":
                    telemetry_data = msg.get("data", {})
                    if telemetry_data:
                        app_state.latest_client_frame = telemetry_data
                        trace_store = getattr(app_state, "trace_store", None)
                        if trace_store and trace_store.is_recording:
                            trace_store.append_frame(telemetry_data)
                elif event == "config_update":
                    cfg = msg.get("data", {})
                    engine = getattr(app_state, "intelligence_engine", None)
                    if engine is not None:
                        if "swearyMessages" in cfg:
                            app_state.sweary_messages = bool(cfg["swearyMessages"])
                            engine.sweary_messages = app_state.sweary_messages
                            logger.info("[WS] sweary_messages=%s", app_state.sweary_messages)
                        engine.apply_runtime_config(cfg)
                    spotter = getattr(app_state, "spotter_service", None)
                    if spotter is not None:
                        spotter.apply_runtime_config(cfg)
                        if "spotterOffQualifying" in cfg:
                            spotter.spotter_off_qualifying = bool(cfg["spotterOffQualifying"])
                        if "spotterExcludeStopped" in cfg:
                            spotter.spotter_exclude_stopped = bool(cfg["spotterExcludeStopped"])
                    if engine is not None:
                        engine.broadcast_config_ack()
                elif event == "spotter_command":
                    action = msg.get("data", {}).get("action", "")
                    spotter = getattr(app_state, "spotter_service", None)
                    if spotter and action in ("enable", "disable"):
                        spotter.enabled = action == "enable"
                        from src.models.messages import AlertMessage
                        import uuid as _uuid
                        ack = AlertMessage(
                            event="alert",
                            alert_id=str(_uuid.uuid4()),
                            category="spotter",
                            message="Spotter activado." if spotter.enabled else "Spotter desactivado.",
                            audio_priority="1",
                            severity="INFO",
                            ttl=3,
                            dismissable=True,
                            payload={"spotter_enabled": spotter.enabled},
                        )
                        await manager.broadcast(ack)
                        logger.info("[WS] spotter enabled=%s", spotter.enabled)
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
        for t in list(active_subtasks):
            t.cancel()
        if active_subtasks:
            await asyncio.gather(*active_subtasks, return_exceptions=True)
        active_subtasks.clear()

        telemetry_task.cancel()
        strategy_task.cancel()

        await asyncio.gather(telemetry_task, strategy_task, return_exceptions=True)

        manager.disconnect(websocket)
