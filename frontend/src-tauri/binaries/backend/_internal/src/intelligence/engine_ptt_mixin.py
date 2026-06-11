"""PTT helpers mixed into IntelligenceEngine (Task 13)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import Any

from src.intelligence.triggers import PilotQuestionTrigger
from src.models.messages import AdviceEndMessage, AdviceStartMessage, AdviceTokenMessage, AlertMessage, LLMPendingMessage

logger = logging.getLogger("vantare.engine")


class EnginePttMixin:
    """Voice-response, fast commands, and free-form pilot questions."""

    def _emit_voice_response(self, text: str, *, fast_command: bool = False) -> None:
        spoken = (text or "").strip()
        if not spoken:
            return
        self.broadcaster.send(
            AlertMessage(
                event="alert",
                alert_id=str(uuid.uuid4()),
                category="voice_response",
                message=spoken,
                audio_priority="HIGH",
                severity="INFO",
                ttl=12,
                dismissable=True,
                payload={"fast_command": fast_command, "service": "engineer"},
            )
        )

    def _emit_competitor_response(self, text: str, *, payload: dict | None = None) -> None:
        spoken = (text or "").strip()
        if not spoken:
            return
        self.broadcaster.send(
            AlertMessage(
                event="alert",
                alert_id=str(uuid.uuid4()),
                category="competitor",
                message=spoken,
                audio_priority="HIGH",
                severity="INFO",
                ttl=12,
                dismissable=True,
                payload={"service": "engineer", **(payload or {})},
            )
        )

    def apply_speak_only(self, enabled: bool, *, emit_voice: bool = True) -> str:
        """Silencia al ingeniero proactivo; el spotter sigue activo si el toggle lo permite."""
        self.verbosity.set_speak_only_when_spoken_to(bool(enabled))
        self.broadcast_config_ack()
        if enabled:
            msg = "Entendido, solo hablaré cuando me preguntes."
        else:
            msg = "Modo normal: vuelvo a hablar en pista."
        if emit_voice:
            self._emit_voice_response(msg, fast_command=True)
        return msg

    def apply_set_verbosity(self, level: str) -> str:
        ok, msg = self.verbosity.set_level(level)
        if ok:
            self.broadcast_config_ack()
        return msg

    def apply_engineer_toggle(self, enabled: bool, *, emit_alert: bool = True) -> str:
        self.engineer_enabled = bool(enabled)
        self.broadcast_config_ack()
        msg = "Ingeniero activado." if enabled else "Ingeniero desactivado."
        if emit_alert:
            self._emit_voice_response(msg, fast_command=True)
        return msg

    def apply_spotter_toggle(self, enabled: bool, *, emit_alert: bool = True) -> str | None:
        if self._spotter_service is None:
            msg = "Spotter no disponible."
            if emit_alert:
                self._emit_voice_response(msg)
            return msg
        self._spotter_service.enabled = bool(enabled)
        self.broadcast_config_ack()
        msg = "Spotter activado." if enabled else "Spotter desactivado."
        if emit_alert:
            self.broadcaster.send(
                AlertMessage(
                    event="alert",
                    alert_id=str(uuid.uuid4()),
                    category="spotter",
                    message=msg,
                    audio_priority="NORMAL",
                    severity="INFO",
                    ttl=8,
                    dismissable=True,
                    payload={"service": "spotter"},
                )
            )
        return msg

    def apply_set_braking_zones_mute(self, enabled: bool) -> str:
        self.verbosity.set_braking_zones_mute(bool(enabled))
        self.broadcast_config_ack()
        return "Silencio en frenada activado." if enabled else "Silencio en frenada desactivado."

    def pit_menu_dry_run(self) -> bool:
        from src.config import settings

        return bool(getattr(settings, "PIT_MENU_DRY_RUN", True))

    def _resolve_ptt_telemetry(self) -> dict[str, Any]:
        svc = self._get_strategy_service()
        if svc and svc.latest_frame is not None:
            frame = self._to_dict(svc.latest_frame)
            if frame:
                return frame
        return dict(self._eval_telemetry or {})

    def build_ptt_context_minimal(self) -> str:
        tele = self._resolve_ptt_telemetry()
        parts: list[str] = []
        lap = tele.get("lap_number") or tele.get("lap")
        pos = tele.get("standing_position") or tele.get("position") or tele.get("place")
        if lap is not None:
            parts.append(f"vuelta {lap}")
        if pos is not None:
            parts.append(f"P{pos}")
        fuel = tele.get("fuel_laps_remaining")
        if fuel is not None:
            parts.append(f"fuel ~{float(fuel):.1f} vueltas")
        return ", ".join(parts)

    async def _try_handle_fast_command(self, cmd) -> bool:
        from src.intelligence.crewchief_events.commands import FastCommand
        from src.intelligence.pilot_tool_executor import PilotToolExecutor

        if not isinstance(cmd, FastCommand):
            return False

        intent = cmd.intent
        if intent == "speak_only_on":
            self.apply_speak_only(True)
            return True
        if intent == "speak_only_off":
            self.apply_speak_only(False)
            return True
        if intent == "spotter_enable":
            self.apply_spotter_toggle(True)
            return True
        if intent == "spotter_disable":
            self.apply_spotter_toggle(False)
            return True

        tool_map = {
            "fuel_status": "get_fuel_status",
            "gap_status": "get_gap_status",
            "damage_status": "get_damage_report",
        }
        tool_name = tool_map.get(intent)
        if tool_name:
            await PilotToolExecutor().run(self, tool_name, {})
            return True
        return False

    async def _handle_free_form_question(self, question: str) -> None:
        from src.intelligence import prompt_templates

        strat_service = self._get_strategy_service()
        telemetry_state = strat_service.latest_frame if strat_service else None
        strategy_state = strat_service.latest_advice if strat_service else None
        telemetry_dict = self._to_dict(telemetry_state)
        strategy_dict = self._to_dict(strategy_state)

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

        self.broadcaster.send(
            LLMPendingMessage(
                event="llm_pending",
                advice_id=advice_id,
                trigger_name=getattr(trigger, "name", trigger.description),
                priority=trigger.priority.name,
            )
        )

        snapshot = self.live_context.snapshot(trigger.tier.name)
        context: dict[str, Any] = {
            "pilot_question": question,
            "sweary": self.sweary_messages,
        }
        if telemetry_dict:
            from src.intelligence.context_builder import _build_ticker_data
            from src.intelligence.ptt_prompt_context import build_ptt_context_for_question
            from src.intelligence.ticker import generate_ticker

            ticker_data = _build_ticker_data(snapshot, telemetry_dict, strategy_dict, self.lmu_api)
            full_ticker = generate_ticker(ticker_data)
            context["ptt_context"] = build_ptt_context_for_question(question, ticker_data, full_ticker)
        else:
            context["snapshot"] = snapshot

        messages = prompt_templates.render_pilot_question_messages(context, trigger.tier.name)
        self._current_llm_task = asyncio.create_task(
            self._run_pilot_question_stream(messages, trigger.tier.name, advice_id, question)
        )
        self._current_llm_task.add_done_callback(self._on_llm_task_done)

    async def _run_pilot_question_stream(
        self,
        messages: list[dict[str, str]],
        tier: str,
        advice_id: str,
        question: str,
    ) -> None:
        from src.intelligence.crewchief_events.commands import match_fast_command
        from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

        self.broadcaster.send(AdviceStartMessage(advice_id=advice_id, tier=tier, event="advice_start"))
        full_text = ""
        try:
            async for token in self.llm_client.ask_streaming_messages(messages, tier=tier):
                if not token:
                    continue
                full_text += token
                spoken = sanitize_llm_speech(token, finalize=False)
                if spoken:
                    self.broadcaster.send(
                        AdviceTokenMessage(advice_id=advice_id, token=spoken, event="advice_token")
                    )

            if not full_text.strip():
                fallback = await self.llm_client._complete_speech_messages(messages)
                if fallback.strip():
                    full_text = fallback.strip()
                else:
                    fast = match_fast_command(question)
                    if fast and fast.intent == "speak_only_on":
                        self.apply_speak_only(True, emit_voice=False)
                        full_text = "Entendido, solo hablaré cuando me preguntes."
                    else:
                        full_text = "No te he entendido bien. Repite la pregunta por radio."

            final_text = sanitize_llm_speech(full_text, finalize=True) or full_text.strip()
            self.broadcaster.send(
                AdviceEndMessage(
                    advice_id=advice_id,
                    full_text=final_text,
                    actions=[],
                    event="advice_end",
                )
            )
        except asyncio.CancelledError:
            logger.info("Streaming PTT cancelado para %s", advice_id)
            self.broadcaster.send(
                AdviceEndMessage(
                    advice_id=advice_id,
                    full_text="--- Transmisión de radio interrumpida ---",
                    actions=[],
                    event="advice_end",
                )
            )
            raise
        except Exception as exc:
            logger.error("Error en streaming PTT: %s", exc, exc_info=True)
            self.broadcaster.send(
                AdviceEndMessage(
                    advice_id=advice_id,
                    full_text="... Pérdida de comunicación de radio con el muro de boxes ...",
                    actions=[],
                    event="advice_end",
                )
            )
        finally:
            self._current_advice_id = None
            self._active_trigger_name = ""
            self._active_trigger_priority = "LOW"
