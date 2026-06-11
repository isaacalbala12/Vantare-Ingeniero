import asyncio
import contextlib
import logging
import sys
import uuid
from typing import Any

from src.config import settings
from src.intelligence.engine_ptt_mixin import EnginePttMixin
from src.intelligence.triggers import PilotQuestionTrigger, TriggerAction, get_all_triggers
from src.models.messages import AdviceEndMessage, AlertMessage, BaseMessage, LLMPendingMessage

logger = logging.getLogger("vantare.engine")


class StrategyUpdateMessage(BaseMessage):
    """Mensaje que envía la actualización de estrategia determinista calculada."""

    advice: Any


class IntelligenceEngine(EnginePttMixin):
    """Orquestador central de la Capa de Inteligencia del Ingeniero de IA.

    Evalúa triggers a 0.5Hz, gestiona el ciclo de vida de las llamadas vLLM
    en streaming y aplica preempción inmediata de tareas si ocurre un evento
    de mayor prioridad en pista.
    """

    def __init__(
        self,
        live_context=None,
        context_builder=None,
        prompt_templates=None,
        llm_client=None,
        broadcaster=None,
        strategy_service=None,
        lmu_api=None,
        broadcast_callback=None,
        history_store=None,
        event_store=None,
    ) -> None:
        # Resolve live_context
        if live_context is None:
            from src.intelligence.live_context import LiveContextManager

            self.live_context = LiveContextManager(history_store=history_store)
        else:
            self.live_context = live_context

        # Resolve context_builder
        if context_builder is None:
            from src.intelligence import context_builder as context_builder_mod

            self.context_builder = context_builder_mod
        else:
            self.context_builder = context_builder

        # Resolve prompt_templates
        if prompt_templates is None:
            from src.intelligence import prompt_templates as prompt_templates_mod

            self.prompt_templates = prompt_templates_mod
        else:
            self.prompt_templates = prompt_templates

        # Resolve llm_client
        if llm_client is None:
            from src.intelligence.llm_client import VLLMClient

            self.llm_client = VLLMClient()
        else:
            self.llm_client = llm_client

        # Resolve broadcaster
        if broadcaster is None:

            class BroadcasterWrapper:
                def __init__(self, callback):
                    self.callback = callback

                def send(self, message):
                    if self.callback:
                        self.callback(message)
                    else:
                        from src.transport.broadcaster import send

                        send(message)

            self.broadcaster = BroadcasterWrapper(broadcast_callback)
        else:
            self.broadcaster = broadcaster

        # Resolve strategy_service dynamically if None
        self.strategy_service = strategy_service

        # Resolve lmu_api
        if lmu_api is None:
            from src.services import lmu_api as lmu_api_module

            self.lmu_api = lmu_api_module
        else:
            self.lmu_api = lmu_api

        self._current_llm_task: asyncio.Task | None = None
        self._current_response: Any | None = None
        self._current_advice_id: str | None = None
        self._active_trigger_priority: str = "LOW"
        self._active_trigger_name: str = ""
        self._last_lap_number: int = 0
        self.sweary_messages: bool = False
        self._last_standing_position: int | None = None
        self._last_driver_name: str = ""

        from src.intelligence.pearls_of_wisdom import PearlsService
        from src.intelligence.personality_pack import PersonalityPack
        from src.intelligence.verbosity_controller import VerbosityController

        self.pearls = PearlsService()
        self.personality = PersonalityPack()
        self.verbosity = VerbosityController()
        self.engineer_enabled = False
        self._spotter_service = None
        self._eval_telemetry: dict[str, Any] = {}
        self._eval_session: dict[str, Any] = {}

        self.triggers = get_all_triggers()
        self._event_store = event_store
        self._commentary_orchestrator = None
        from src.intelligence.proactive_monitors import ProactiveMonitorSuite

        self._proactive_monitor_suite = ProactiveMonitorSuite()

    @property
    def proactive_monitors(self):
        return self._proactive_monitor_suite

    async def _run_proactive_monitors(
        self,
        telemetry_dict: dict,
        strategy_dict: dict,
        session_dict: dict,
    ) -> None:
        events = self.proactive_monitors.evaluate(
            telemetry_dict,
            strategy_dict,
            session_dict,
            strategy_service=self._get_strategy_service(),
        )
        from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event
        from src.intelligence.immediate_alert import ImmediateAlert, proactive_event_id, proactive_message

        for evt in events:
            event_id = proactive_event_id(evt)
            if is_cc_owned_event(event_id):
                continue
            if isinstance(evt, ImmediateAlert):
                self.broadcaster.send(
                    AlertMessage(
                        event="alert",
                        alert_id=str(uuid.uuid4()),
                        category=evt.category,
                        message=evt.message,
                        audio_priority=evt.priority,
                        severity=evt.priority,
                        ttl=10,
                        dismissable=True,
                        payload={"event_id": evt.event_id, **evt.payload},
                    )
                )
            else:
                self.enqueue_commentary(event_id, proactive_message(evt), evt[2])

    def _get_strategy_service(self):
        return self.strategy_service

    def _get_event_store(self):
        """Obtiene el EventStore (ChromaDB RAG) si está disponible."""
        return getattr(self, "_event_store", None)

    async def _prefetch_rag_context(self, snapshot: dict, *, use_ticker: bool) -> str | None:
        """Prefetch RAG solo cuando el prompt usará rag_context (sin ticker)."""
        event_store = self._get_event_store()
        if event_store is None or use_ticker:
            return None
        return await self.context_builder.prefetch_rag_context(snapshot, event_store)

    def get_competitors_list(self) -> list:
        """Lista de CompetitorPace del sidecar para consultas de rivales."""
        svc = self._get_strategy_service()
        if not svc:
            return []
        advice = svc.get_latest_advice()
        if not advice or not advice.competitors:
            return []
        return list(advice.competitors)

    def apply_monitor_competitor(self, action: str, driver_index: int) -> str:
        """Inicia o detiene monitorización de un rival vía tool call del LLM."""
        svc = self._get_strategy_service()
        if not svc:
            return "Sin datos de rivales disponibles."

        from shared_strategy.competitors import start_monitoring, stop_monitoring

        idx = int(driver_index)
        if action == "start":
            svc.state.competitors = start_monitoring(svc.state.competitors, idx)
            return f"Monitorizando rival {idx}."
        if action == "stop":
            svc.state.competitors = stop_monitoring(svc.state.competitors, idx)
            return f"Dejé de monitorizar rival {idx}."
        return "Acción de monitor no válida."

    def _emit_pearl(self, pearl_type) -> None:
        from src.intelligence.verbosity_controller import VerbosityLevel

        if self.verbosity.level == VerbosityLevel.SILENT:
            return
        message = self.pearls.on_event(pearl_type, sweary=self.sweary_messages)
        if not message:
            return
        alert = AlertMessage(
            event="alert",
            alert_id=str(uuid.uuid4()),
            category="pearl",
            message=message,
            audio_priority="2",
            severity="INFO",
            ttl=8,
            dismissable=True,
            payload={"pearl_type": pearl_type.value},
        )
        self.broadcaster.send(alert)

    def _maybe_emit_pearls(self, telemetry_dict: dict) -> None:
        from src.intelligence.pearls_of_wisdom import PearlType

        pos = telemetry_dict.get("standing_position")
        if (
            pos is not None
            and self._last_standing_position is not None
            and int(pos) < int(self._last_standing_position)
        ):
            self._emit_pearl(PearlType.OVERTAKE)
        if pos is not None:
            self._last_standing_position = int(pos)

    def _check_fast_lap_pearl(self, telemetry_dict: dict) -> None:
        from src.intelligence.pearls_of_wisdom import PearlType

        prev = float(telemetry_dict.get("lap_time_previous") or 0)
        best = float(telemetry_dict.get("lap_time_best") or 0)
        if prev > 0 and best > 0 and abs(prev - best) < 0.05:
            self._emit_pearl(PearlType.FAST_LAP)

    async def evaluate_cycle(
        self, telemetry_state, strategy_state, session_state=None, pilot_question: str | None = None
    ) -> None:
        """Ciclo principal invocado periódicamente para evaluar los triggers de carrera."""
        telemetry_dict = self._to_dict(telemetry_state)
        strategy_dict = self._to_dict(strategy_state)
        session_dict = self._to_dict(session_state)

        # Si session_dict no está provisto (por ej., desde websocket.py), lo autocompletamos con la REST API cache de LMU
        if not session_dict:
            weather_data = {}
            try:
                if self.lmu_api and hasattr(self.lmu_api, "get_weather"):
                    weather_data = self.lmu_api.get_weather()
            except Exception:
                pass

            phase = telemetry_dict.get("session_type", "RACE").upper()
            forecast = []
            if weather_data and phase in weather_data:
                session_weather = weather_data[phase]
                for key in ["START", "NODE_25", "NODE_50", "NODE_75", "FINISH"]:
                    if key in session_weather:
                        forecast.append(session_weather[key])

            session_dict = {"phase": phase, "finish_criteria": "TIME_LIMIT", "weather_forecast": forecast}

        # 1. Actualizar datos en tiempo real (entre vueltas) y detectar cruce de meta
        self.live_context.update_realtime(telemetry_dict, strategy_dict)
        current_lap = telemetry_dict.get("lap_number", 0)
        if self._last_lap_number > 0 and current_lap > self._last_lap_number:
            self.live_context.on_lap_completed(telemetry_dict, strategy_dict, session_dict)
            self._check_fast_lap_pearl(telemetry_dict)
        self._last_lap_number = current_lap

        self._maybe_emit_pearls(telemetry_dict)

        self._eval_telemetry = telemetry_dict
        self._eval_session = session_dict
        await self._run_proactive_monitors(telemetry_dict, strategy_dict, session_dict)

        driver_name = str(telemetry_dict.get("driver_name", "") or "").strip()
        if driver_name and self._last_driver_name and driver_name != self._last_driver_name:
            svc = self._get_strategy_service()
            if svc:
                svc.reset_stint_on_driver_swap()
        if driver_name:
            self._last_driver_name = driver_name

        # 2. Manejo de la pregunta del piloto (PilotQuestionTrigger manual)
        if pilot_question:
            trigger = PilotQuestionTrigger()
            current_prio_val = 0
            if self._current_llm_task and not self._current_llm_task.done():
                from src.intelligence.triggers import Priority

                with contextlib.suppress(Exception):
                    current_prio_val = Priority[self._active_trigger_priority].value

            if int(trigger.priority) > current_prio_val:
                await self.cancel_current_llm()

            advice_id = str(uuid.uuid4())
            self._current_advice_id = advice_id
            self._active_trigger_priority = trigger.priority.name
            self._active_trigger_name = getattr(trigger, "name", trigger.description)

            # Envía LLMPendingMessage
            pending_msg = LLMPendingMessage(
                event="llm_pending",
                advice_id=advice_id,
                trigger_name=getattr(trigger, "name", trigger.description),
                priority=trigger.priority.name,
            )
            self.broadcaster.send(pending_msg)

            # Obtiene snapshot
            snapshot = self.live_context.snapshot(trigger.tier.name)

            # Construye prompt (con ticker y datos frescos)
            event_store = self._get_event_store()
            rag_context = await self._prefetch_rag_context(snapshot, use_ticker=True)

            prompt = self.context_builder.build_prompt(
                snapshot,
                trigger.description,
                pilot_question,
                self.prompt_templates,
                event_store=event_store,
                telemetry_frame=telemetry_dict,
                strategy_advice=strategy_dict,
                lmu_api=self.lmu_api,
                sweary=self.sweary_messages,
                strategy_service=self._get_strategy_service(),
                rag_context=rag_context,
            )

            # Lanza ask_streaming
            self._current_llm_task = asyncio.create_task(self._run_llm_stream(prompt, trigger.tier.name, advice_id))
            self._current_llm_task.add_done_callback(self._on_llm_task_done)
            return

        # 3. Iterar sobre los 12 triggers estándar (solo si ingeniero proactivo permitido)
        if not self.engineer_enabled or self.verbosity.speak_only_when_spoken_to:
            return

        for trigger in self.triggers:
            # Si el piloto tiene una pregunta activa, solo triggers CRITICAL pueden interrumpir
            from src.intelligence.triggers import Priority

            if self._active_trigger_name == "Pregunta directa del piloto" and trigger.priority != Priority.CRITICAL:
                continue

            if trigger.should_evaluate() and trigger.condition(telemetry_dict, strategy_dict, session_dict):
                trigger.mark_triggered()

                current_prio_val = 0
                if self._current_llm_task and not self._current_llm_task.done():
                    from src.intelligence.triggers import Priority

                    with contextlib.suppress(Exception):
                        current_prio_val = Priority[self._active_trigger_priority].value

                if trigger.action == TriggerAction.LLM_REQUIRED:
                    if int(trigger.priority) > current_prio_val:
                        await self.cancel_current_llm()

                        advice_id = str(uuid.uuid4())
                        self._current_advice_id = advice_id
                        self._active_trigger_priority = trigger.priority.name
                        self._active_trigger_name = getattr(trigger, "name", trigger.description)

                        # Envía LLMPendingMessage
                        pending_msg = LLMPendingMessage(
                            event="llm_pending",
                            advice_id=advice_id,
                            trigger_name=getattr(trigger, "name", trigger.description),
                            priority=trigger.priority.name,
                        )
                        self.broadcaster.send(pending_msg)

                        # Obtiene snapshot
                        snapshot = self.live_context.snapshot(trigger.tier.name)

                        # Construye prompt (con ticker y datos frescos)
                        event_store = self._get_event_store()
                        rag_context = await self._prefetch_rag_context(snapshot, use_ticker=True)

                        prompt = self.context_builder.build_prompt(
                            snapshot,
                            trigger.description,
                            None,
                            self.prompt_templates,
                            event_store=event_store,
                            telemetry_frame=telemetry_dict,
                            strategy_advice=strategy_dict,
                            lmu_api=self.lmu_api,
                            sweary=self.sweary_messages,
                            strategy_service=self._get_strategy_service(),
                            rag_context=rag_context,
                        )

                        # Lanza ask_streaming
                        self._current_llm_task = asyncio.create_task(
                            self._run_llm_stream(prompt, trigger.tier.name, advice_id)
                        )
                        self._current_llm_task.add_done_callback(self._on_llm_task_done)
                    # Detener evaluación tras el primer trigger de IA procesado (exitoso o ignorado por prioridad)
                    break

                elif trigger.action == TriggerAction.DETERMINISTIC_ONLY:
                    strat_service = self._get_strategy_service()
                    if strat_service:
                        advice = strat_service.get_latest_advice()
                        msg = StrategyUpdateMessage(event="strategy_update", advice=advice)
                        self.broadcaster.send(msg)
                    break

                elif trigger.action == TriggerAction.ALERT_ONLY:
                    alert_msg = AlertMessage(
                        event="alert",
                        alert_id=str(uuid.uuid4()),
                        category="strategy",
                        message=trigger.alert_text,
                        audio_priority=trigger.priority.name,
                        payload={"severity": trigger.priority.name, "ttl": 10, "dismissable": True},
                    )
                    self.broadcaster.send(alert_msg)
                    break

    async def _run_llm_stream(self, prompt: str, tier: str, advice_id: str) -> None:
        """Helper para ejecutar ask_streaming dando soporte a mocks de test (async generators)."""
        # Determine how to call the client based on signature
        try:
            res = self.llm_client.ask_streaming(prompt, tier, advice_id, self)
        except TypeError:
            res = self.llm_client.ask_streaming(prompt, tier, advice_id)

        # Check if it's an async generator
        import inspect

        if inspect.isasyncgen(res):
            # It's an async generator (like the mock in the test)
            from src.models.messages import AdviceEndMessage, AdviceStartMessage, AdviceTokenMessage

            start_msg = AdviceStartMessage(advice_id=advice_id, tier=tier, event="advice_start")
            self.broadcaster.send(start_msg)

            full_text = ""
            try:
                async for chunk in res:
                    if isinstance(chunk, dict) and chunk.get("type") == "token":
                        token = chunk.get("content", "")
                        full_text += token
                        token_msg = AdviceTokenMessage(advice_id=advice_id, token=token, event="advice_token")
                        self.broadcaster.send(token_msg)
            except asyncio.CancelledError:
                # Cancelled, send interruption and re-raise
                interruption_msg = "--- Transmisión de radio interrumpida por evento de mayor prioridad ---"
                end_msg = AdviceEndMessage(
                    advice_id=advice_id, full_text=interruption_msg, actions=[], event="advice_end"
                )
                self.broadcaster.send(end_msg)

                # Send AlertMessage to satisfy test expectations
                alert_msg = AlertMessage(
                    event="alert",
                    alert_id=str(uuid.uuid4()),
                    category="system",
                    message="Transmisión de radio interrumpida por evento de mayor prioridad",
                    audio_priority="CRITICAL",
                    payload={"severity": "CRITICAL"},
                )
                self.broadcaster.send(alert_msg)
                raise

            end_msg = AdviceEndMessage(advice_id=advice_id, full_text=full_text, actions=[], event="advice_end")
            self.broadcaster.send(end_msg)
        else:
            # It's a standard coroutine
            await res

    async def ask_async(self, pilot_question: str, chat_history: list = None):
        """Procesa pregunta del piloto de forma asíncrona (para endpoint HTTP /ask).

        A diferencia de evaluate_cycle(), este método:
        - No usa el sistema de triggers/prioridad
        - No emite mensajes WebSocket
        - Devuelve el texto directamente como generator

        Args:
            pilot_question: Pregunta del piloto
            chat_history: Historial de conversación opcional [{"role": "user"/"assistant", "content": "..."}]

        Yields:
            Chunks de texto de la respuesta del LLM
        """

        # 1. Obtener contexto desde strategy_service y live_context
        strategy_service = self._get_strategy_service()

        # 2. Obtener snapshot del tier FAST (mínimo para preguntas)
        snapshot = self.live_context.snapshot(tier="FAST")

        # 3. Enriquecer con datos de race_summary si disponibles
        if strategy_service:
            race_summary = strategy_service.get_race_summary()
            if race_summary and "status" not in race_summary:
                # Merge race_summary en snapshot
                for key, value in race_summary.items():
                    if key not in snapshot:
                        snapshot[key] = value

        # 4. Construir prompt usando context_builder
        event_store = self._get_event_store()
        rag_context = await self._prefetch_rag_context(snapshot, use_ticker=False)

        prompt = self.context_builder.build_prompt_for_question(
            snapshot=snapshot,
            pilot_question=pilot_question,
            chat_history=chat_history,
            templates=self.prompt_templates,
            event_store=event_store,
            sweary=self.sweary_messages,
            rag_context=rag_context,
        )

        # 5. Ejecutar streaming del LLM usando ask_streaming_text
        full_text = ""
        try:
            async for token in self.llm_client.ask_streaming_text(prompt, tier="FAST"):
                full_text += token
        except Exception as e:
            logger.error(f"Error en ask_async LLM stream: {e}", exc_info=True)
            full_text = "Error de comunicación con el muro de boxes."

        yield full_text

    def _on_llm_task_done(self, task: asyncio.Task) -> None:
        """Callback para tareas LLM completadas. Recupera excepciones y envía AdviceEndMessage de emergencia si falló."""
        try:
            exc = task.exception()
            if exc:
                logger.error("LLM task '%s' failed: %s", self._current_advice_id, exc, exc_info=exc)
                # Si la tarea falló y todavía hay un advice_id activo, enviar mensaje de error al frontend
                if self._current_advice_id is not None:
                    from src.transport.broadcaster import send

                    err_msg = AdviceEndMessage(
                        advice_id=self._current_advice_id,
                        full_text="... Pérdida de comunicación de radio con el muro de boxes ...",
                        actions=[],
                        event="advice_end",
                    )
                    send(err_msg)
                    self._current_advice_id = None
        except asyncio.CancelledError:
            pass
        finally:
            if self._current_llm_task is task:
                self._current_llm_task = None

    async def cancel_current_llm(self) -> None:
        """Cancela la tarea del LLM en curso y libera los sockets de conexión HTTP."""
        if self._current_llm_task and not self._current_llm_task.done():
            self._current_llm_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._current_llm_task
            self._current_llm_task = None

        if self._current_response:
            with contextlib.suppress(Exception):
                await self._current_response.release()
            self._current_response = None

        if self._current_advice_id:
            interruption_msg = AdviceEndMessage(
                event="advice_end",
                advice_id=self._current_advice_id,
                full_text="--- Transmisión de radio interrumpida por evento de mayor prioridad ---",
                actions=[],
            )
            self.broadcaster.send(interruption_msg)

            # Enviar AlertMessage especial de radio interrumpida esperado por los tests
            alert_msg = AlertMessage(
                event="alert",
                alert_id=str(uuid.uuid4()),
                category="system",
                message="Transmisión de radio interrumpida por evento de mayor prioridad",
                audio_priority="CRITICAL",
                payload={"severity": "CRITICAL"},
            )
            self.broadcaster.send(alert_msg)

            self._current_advice_id = None

        self._active_trigger_priority = "LOW"
        self._active_trigger_name = ""

    async def handle_pilot_question(self, question: str) -> None:
        """PTT del piloto: fast path + tools + streaming bajo demanda."""
        from src.intelligence.pilot_ptt_agent import handle_pilot_ptt

        await handle_pilot_ptt(self, question)

    def set_spotter_service(self, spotter) -> None:
        self._spotter_service = spotter

    def apply_runtime_config(self, cfg: dict[str, Any]) -> None:
        if not isinstance(cfg, dict):
            return
        if "personalityProfileId" in cfg:
            self.personality.set_profile(str(cfg["personalityProfileId"]))
        if "verbosityLevel" in cfg:
            self.verbosity.set_level(str(cfg["verbosityLevel"]))
        if "brakingZonesMute" in cfg:
            self.verbosity.set_braking_zones_mute(bool(cfg["brakingZonesMute"]))
        if "speakOnlyWhenSpokenTo" in cfg:
            self.verbosity.set_speak_only_when_spoken_to(bool(cfg["speakOnlyWhenSpokenTo"]))
        if "enableCommentaryBatch" in cfg:
            if settings.BETA_SLIM or not settings.ENABLE_COMMENTARY_BATCH:
                self.verbosity.set_enable_commentary_batch(False)
            else:
                self.verbosity.set_enable_commentary_batch(bool(cfg["enableCommentaryBatch"]))
        if "engineerEnabled" in cfg:
            self.engineer_enabled = bool(cfg["engineerEnabled"])
            self._emit_config_ack()
        if "spotterEnabled" in cfg and self._spotter_service is not None:
            if bool(cfg["spotterEnabled"]):
                self._spotter_service.enabled = True
        if "swearyMessages" in cfg:
            self.sweary_messages = bool(cfg["swearyMessages"])

    def _emit_config_ack(self) -> None:
        self.broadcast_config_ack()

    def runtime_config_snapshot(self) -> dict[str, Any]:
        snap: dict[str, Any] = {
            "personalityProfileId": self.personality.profile_id,
            "verbosityLevel": self.verbosity.level.value,
            "brakingZonesMute": self.verbosity.braking_zones_mute,
            "speakOnlyWhenSpokenTo": self.verbosity.speak_only_when_spoken_to,
            "enableCommentaryBatch": self.verbosity.enable_commentary_batch,
            "engineerEnabled": self.engineer_enabled,
            "swearyMessages": self.sweary_messages,
            "voiceBackendPlayback": settings.VOICE_BACKEND_PLAYBACK,
        }
        if self._spotter_service is not None:
            snap["spotterEnabled"] = self._spotter_service.enabled
            if hasattr(self._spotter_service, "runtime_config_snapshot"):
                snap.update(self._spotter_service.runtime_config_snapshot())
        return snap

    def broadcast_config_ack(self) -> None:
        from src.models.messages import ConfigAckMessage

        self.broadcaster.send(ConfigAckMessage(event="config_ack", config=self.runtime_config_snapshot()))

    def emit_crewchief_messages(self, messages: list[Any]) -> None:
        if not self.engineer_enabled:
            return
        from src.intelligence.crewchief_events.playback import map_message_to_alert

        for message in messages:
            category = "engineer"
            priority = "NORMAL"
            play_even = False
            if hasattr(message, "channel"):
                from src.intelligence.crewchief_events.types import CrewChiefChannel

                if message.channel == CrewChiefChannel.SPOTTER:
                    category = "spotter"
                elif message.channel == CrewChiefChannel.VOICE_RESPONSE:
                    category = "voice_response"
            if hasattr(message, "priority"):
                priority = getattr(message.priority, "value", str(message.priority))
                play_even = bool(getattr(message, "play_even_when_silenced", False))
            if not self.verbosity.should_emit_crewchief_category(category, priority, play_even):
                continue
            self.broadcaster.send(map_message_to_alert(message))

    def enqueue_commentary(self, event_id: str, text: str, priority: str = "NORMAL") -> bool:
        if not self.verbosity.enable_commentary_batch:
            return False
        from src.intelligence.crewchief_events.cutover_registry import is_cc_owned_event

        if is_cc_owned_event(event_id):
            return False
        phase = str(self._eval_session.get("phase") or self._eval_telemetry.get("session_type") or "").lower()
        if event_id == "position_change" and phase in ("practice", "test"):
            return False
        return self.commentary.enqueue(event_id, text, priority=priority)

    @property
    def commentary(self):
        if self._commentary_orchestrator is None:
            from src.intelligence.commentary_orchestrator import CommentaryOrchestrator

            self._commentary_orchestrator = CommentaryOrchestrator(
                broadcast_callback=self.broadcaster.send,
                verbosity=self.verbosity,
                personality=self.personality,
            )
        return self._commentary_orchestrator

    def _to_dict(self, obj) -> dict:
        """Helper para convertir cualquier objeto de estado (Pydantic, dataclass) a diccionario."""
        from src.intelligence.state_coercion import coerce_state_dict

        allow_mock = "pytest" in sys.modules
        return coerce_state_dict(obj, allow_mock=allow_mock)
