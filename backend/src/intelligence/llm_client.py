import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from src.config import settings
from src.models.messages import AdviceStartMessage, AdviceTokenMessage, AdviceEndMessage, UIAction
from src.transport.broadcaster import send
from src.intelligence import prompt_templates


logger = logging.getLogger("vantare.llm_client")

SPEECH_MAX_TOKENS = 1024


@dataclass
class ParsedToolCall:
    name: str
    arguments: Dict[str, Any]
    id: str = ""


@dataclass
class AskWithToolsResult:
    content: str = ""
    tool_calls: List[ParsedToolCall] = field(default_factory=list)


class VLLMClient:
    """Cliente asíncrono para el motor de lenguaje LLM (API compatible con OpenAI).

    Se conecta a la URL configurada en LLM_BASE_URL usando el SDK oficial de OpenAI.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.LLM_API_KEY
        self._base_url = base_url or settings.LLM_BASE_URL
        self._model = model or settings.LLM_MODEL
        self._client: Optional[AsyncOpenAI] = None

        if not self._api_key:
            logger.warning(
                "*** LLM_API_KEY no configurada. El LLM no funcionará. ***\n"
                "    Crea un archivo backend/.env con:\n"
                "    LLM_API_KEY=tu-api-key-aqui"
            )

        logger.info(
            "LLMClient inicializado: base_url=%s model=%s api_key=%s",
            self._base_url,
            self._model,
            "***configurada***" if self._api_key else "VACÍA",
        )

    def _get_client(self) -> AsyncOpenAI:
        """Devuelve (y cachea) el cliente OpenAI asíncrono con timeout."""
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=httpx.Timeout(25.0, connect=10.0, read=20.0),
            )
        return self._client

    def _is_stepfun(self) -> bool:
        return "stepfun.ai" in self._base_url

    def _stepfun_extra_body(self) -> Optional[dict]:
        # Turno con tools / clasificación: reasoning separado.
        if self._is_stepfun():
            return {"thinking": {"type": "enabled"}}
        return None

    def _stepfun_speech_extra_body(self) -> Optional[dict]:
        # Voz/TTS: thinking separado; solo emitimos content (reasoning se descarta).
        if self._is_stepfun():
            return {"thinking": {"type": "enabled"}}
        return None

    @staticmethod
    def _extract_speech_from_message(message: Any) -> str:
        """Content preferido; si Stepfun deja content vacío, extrae radio del reasoning."""
        from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

        content = sanitize_llm_speech(
            (getattr(message, "content", None) or "").strip(),
            finalize=True,
        )
        if content.strip():
            return content
        reasoning = (getattr(message, "reasoning_content", None) or "").strip()
        if not reasoning:
            return ""
        extracted = sanitize_llm_speech(reasoning, finalize=True)
        if extracted.strip():
            logger.info(
                "PTT LLM: content vacío, respuesta extraída del reasoning (%d chars)",
                len(extracted),
            )
        return extracted

    @staticmethod
    def _message_raw_text(message: Any) -> str:
        """Texto hablable: solo content (nunca reasoning)."""
        return (getattr(message, "content", None) or "").strip()

    @staticmethod
    def _message_speech_text(message: Any) -> str:
        from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

        return sanitize_llm_speech(VLLMClient._message_raw_text(message))

    async def health_check(self) -> bool:
        """Verifica conectividad con el LLM listando los modelos disponibles."""
        try:
            client = self._get_client()
            models = await client.models.list()
            model_ids = [m.id for m in models.data]
            logger.info(
                "LLM health OK: %d modelos disponibles. Modelo objetivo: %s",
                len(model_ids),
                self._model,
            )
            # Verificar que el modelo configurado existe en la lista
            if self._model not in model_ids:
                logger.warning(
                    "Modelo '%s' no encontrado en el LLM. Disponibles: %s",
                    self._model,
                    ", ".join(model_ids[:10]),
                )
            return True
        except Exception as e:
            logger.warning("LLM health check fallido: %s", e)
            return False

    async def ask_streaming(
        self, prompt: str, tier: str, advice_id: str, engine_ref=None
    ) -> None:
        """Realiza una consulta por streaming al LLM.

        Los tokens se emiten al frontend vía WebSocket (AdviceTokenMessage).
        Al finalizar se emite AdviceEndMessage con el texto completo y acciones UI.
        """
        # 1. Emitir mensaje de inicio
        start_msg = AdviceStartMessage(advice_id=advice_id, tier=tier, event="advice_start")
        send(start_msg)

        # 2. Configurar parámetros según el tier
        max_tokens = 500

        full_text = ""
        actions: List[UIAction] = []

        try:
            client = self._get_client()

            competitors = []
            if engine_ref and hasattr(engine_ref, "get_competitors_list"):
                competitors = engine_ref.get_competitors_list()

            create_kwargs: dict = {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": max_tokens,
                "stream": True,
            }
            if self._is_stepfun():
                extra = self._stepfun_extra_body()
                if extra:
                    create_kwargs["extra_body"] = extra
            else:
                create_kwargs["tools"] = prompt_templates.get_llm_tools(
                    include_competitor_query=bool(competitors)
                )

            stream = await client.chat.completions.create(**create_kwargs)

            tool_call_name: Optional[str] = None
            tool_call_arguments: Dict[str, Any] = {}
            competitor_query_args: Optional[Dict[str, Any]] = None
            from src.intelligence.llm_speech_sanitize import (
                SpeechSanitizeState,
                sanitize_llm_speech_delta,
            )

            speech_state = SpeechSanitizeState()

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                content_token = delta.content if delta.content else None
                reasoning_token = getattr(delta, "reasoning_content", None) or None

                if reasoning_token and self._is_stepfun():
                    pass  # no acumular reasoning para voz
                elif content_token:
                    full_text += content_token
                    _, delta_spoken = sanitize_llm_speech_delta(full_text, speech_state)
                    if delta_spoken:
                        send(AdviceTokenMessage(advice_id=advice_id, token=delta_spoken, event="advice_token"))

                # Tool calls (para acciones UI)
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        if tc.function and tc.function.name:
                            tool_call_name = tc.function.name
                        if tc.function and tc.function.arguments:
                            existing = tool_call_arguments.get(tc.index, "")
                            tool_call_arguments[tc.index] = existing + tc.function.arguments

            # 3. Procesar tool calls al final del stream
            if tool_call_name == "query_competitor" and tool_call_arguments and competitors:
                for idx, args_str in tool_call_arguments.items():
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        from src.intelligence.competitor_queries import resolve_from_tool_args
                        result = resolve_from_tool_args(args, competitors)
                        competitor_query_args = args
                        if result.summary:
                            summary_token = f"\n[RIVAL] {result.summary}"
                            full_text += summary_token
                            send(AdviceTokenMessage(advice_id=advice_id, token=summary_token, event="advice_token"))
                    except Exception as e:
                        logger.warning("Error resolviendo query_competitor (idx=%s): %s", idx, e)

            elif tool_call_name == "monitor_competitor" and tool_call_arguments and engine_ref:
                for idx, args_str in tool_call_arguments.items():
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        action = args.get("action")
                        driver_index = args.get("driver_index")
                        if action and driver_index is not None and hasattr(engine_ref, "apply_monitor_competitor"):
                            msg = engine_ref.apply_monitor_competitor(action, driver_index)
                            summary_token = f"\n[MONITOR] {msg}"
                            full_text += summary_token
                            send(AdviceTokenMessage(advice_id=advice_id, token=summary_token, event="advice_token"))
                    except Exception as e:
                        logger.warning("Error resolviendo monitor_competitor (idx=%s): %s", idx, e)

            elif tool_call_name == "set_verbosity" and tool_call_arguments and engine_ref:
                for idx, args_str in tool_call_arguments.items():
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        level = args.get("level")
                        if level and hasattr(engine_ref, "apply_set_verbosity"):
                            msg = engine_ref.apply_set_verbosity(level)
                            summary_token = f"\n[VERBOSIDAD] {msg}"
                            full_text += summary_token
                            send(AdviceTokenMessage(advice_id=advice_id, token=summary_token, event="advice_token"))
                    except Exception as e:
                        logger.warning("Error resolviendo set_verbosity (idx=%s): %s", idx, e)

            elif tool_call_name == "set_braking_zones_mute" and tool_call_arguments and engine_ref:
                for idx, args_str in tool_call_arguments.items():
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        if "enabled" in args and hasattr(engine_ref, "apply_set_braking_zones_mute"):
                            msg = engine_ref.apply_set_braking_zones_mute(bool(args["enabled"]))
                            summary_token = f"\n[FRENADA] {msg}"
                            full_text += summary_token
                            send(AdviceTokenMessage(advice_id=advice_id, token=summary_token, event="advice_token"))
                    except Exception as e:
                        logger.warning("Error resolviendo set_braking_zones_mute (idx=%s): %s", idx, e)

            elif tool_call_name and tool_call_arguments:
                for idx, args_str in tool_call_arguments.items():
                    try:
                        args = json.loads(args_str) if isinstance(args_str, str) else args_str
                        target = args.get("target")
                        action = args.get("action")
                        duration_ms = args.get("duration_ms", 1000)
                        if target and action:
                            actions.append(
                                UIAction(
                                    action_type=f"{target}_{action}",
                                    params={
                                        "target": target,
                                        "action": action,
                                        "duration_ms": duration_ms,
                                    },
                                )
                            )
                            logger.info(
                                "Acción visual parseada del LLM: %s -> %s", target, action
                            )
                    except Exception as e:
                        logger.warning(
                            "Error parseando tool call arguments (idx=%s): %s", idx, e
                        )

            # 4. Emitir mensaje final
            from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

            full_text = sanitize_llm_speech(full_text, finalize=True)
            if not full_text.strip():
                try:
                    full_text = await self._complete_speech_messages(
                        [{"role": "user", "content": prompt}],
                        max_tokens=max_tokens,
                    )
                except Exception as fallback_exc:
                    logger.warning("LLM stream fallback no-stream falló: %s", fallback_exc)
            if not full_text.strip():
                full_text = "No he podido generar respuesta ahora. Repite la pregunta."
            end_msg = AdviceEndMessage(
                advice_id=advice_id,
                full_text=full_text,
                actions=actions,
                event="advice_end",
            )
            send(end_msg)

        except asyncio.CancelledError:
            logger.info("Streaming LLM para el consejo %s cancelado por preempción.", advice_id)
            interruption_msg = "--- Transmisión de radio interrumpida por evento de mayor prioridad ---"
            send(AdviceEndMessage(
                advice_id=advice_id,
                full_text=interruption_msg,
                actions=[],
                event="advice_end",
            ))

        except Exception as e:
            logger.error("Error en streaming LLM: %s", e)
            error_fallback = "--- Pérdida de comunicación de radio con el muro de boxes ---"
            send(
                AdviceEndMessage(
                    advice_id=advice_id,
                    full_text=error_fallback,
                    actions=[],
                    event="advice_end",
                )
            )
        finally:
            if engine_ref:
                engine_ref._current_response = None

    async def ask_with_tools(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        tool_choice: str | Dict[str, Any] = "auto",
        max_tokens: int = 384,
    ) -> AskWithToolsResult:
        """Completado no-streaming con tool calls (PTT turno 1)."""
        client = self._get_client()
        request_messages = list(messages)
        if self._is_stepfun():
            request_messages = self._inject_stepfun_tools_prompt(request_messages, tools)

        create_kwargs: dict = {
            "model": self._model,
            "messages": request_messages,
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        if self._is_stepfun():
            extra = self._stepfun_extra_body()
            if extra:
                create_kwargs["extra_body"] = extra
        else:
            create_kwargs["tools"] = tools
            create_kwargs["tool_choice"] = tool_choice

        resp = await client.chat.completions.create(**create_kwargs)
        message = resp.choices[0].message
        content = self._message_raw_text(message)
        tool_calls: List[ParsedToolCall] = []

        raw_tools = getattr(message, "tool_calls", None) or []
        for tc in raw_tools:
            fn = tc.function
            if not fn or not fn.name:
                continue
            try:
                args = json.loads(fn.arguments) if fn.arguments else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ParsedToolCall(name=fn.name, arguments=args, id=getattr(tc, "id", "") or "")
            )

        if not tool_calls and self._is_stepfun() and content:
            parsed = self._parse_stepfun_tool_json(content)
            if not parsed:
                parsed = self._parse_stepfun_tool_markup(content)
            if parsed:
                tool_calls.append(parsed)
                content = ""

        return AskWithToolsResult(content=content, tool_calls=tool_calls)

    async def complete_from_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 150,
    ) -> str:
        """Completado no-streaming multi-turno (PTT turno 2)."""
        client = self._get_client()
        create_kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        extra = self._stepfun_extra_body()
        if extra:
            create_kwargs["extra_body"] = extra
        resp = await client.chat.completions.create(**create_kwargs)
        return self._message_speech_text(resp.choices[0].message)

    @staticmethod
    def _inject_stepfun_tools_prompt(
        messages: List[Dict[str, str]], tools: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Stepfun no expone tools nativas: inyecta schema en el system prompt."""
        hint = VLLMClient._format_stepfun_tools_instruction(tools)
        out = list(messages)
        if out and out[0].get("role") == "system":
            out[0] = {
                **out[0],
                "content": f"{out[0].get('content', '')}\n\n{hint}".strip(),
            }
        else:
            out.insert(0, {"role": "system", "content": hint})
        return out

    @staticmethod
    def _format_stepfun_tools_instruction(tools: List[Dict[str, Any]]) -> str:
        lines = [
            "TOOLS (obligatorio para acciones/consultas de estado): responde SOLO con JSON válido en content:",
            '{"tool":"nombre_exacto","arguments":{...}}',
            "No uses XML ni <tool_call>. Nombres disponibles:",
        ]
        for tool in tools:
            fn = tool.get("function") if isinstance(tool, dict) else None
            if not fn:
                continue
            name = fn.get("name", "")
            desc = fn.get("description", "")
            lines.append(f"- {name}: {desc}")
        return "\n".join(lines)

    _STEPFUN_TOOL_ALIASES: Dict[str, str] = {
        "consultar_estado_combustible": "get_fuel_status",
        "estado_combustible": "get_fuel_status",
        "fuel_status": "get_fuel_status",
        "get_fuel": "get_fuel_status",
        "consultar_gap": "get_gap_status",
        "gap_status": "get_gap_status",
        "consultar_danos": "get_damage_report",
        "damage_status": "get_damage_report",
        "consultar_neumaticos": "get_tire_wear",
        "tire_wear": "get_tire_wear",
        "spotter": "spotter_toggle",
        "toggle_spotter": "spotter_toggle",
        "speak_only": "set_speak_only",
        "silencio": "set_speak_only",
        "verbosity": "set_verbosity",
        "monitor_rival": "monitor_competitor",
        "query_competitor": "query_competitor",
    }

    @classmethod
    def _normalize_stepfun_tool_name(cls, raw_name: str) -> str:
        key = raw_name.strip().lower().replace("-", "_")
        return cls._STEPFUN_TOOL_ALIASES.get(key, raw_name.strip())

    @classmethod
    def _parse_stepfun_tool_markup(cls, content: str) -> Optional[ParsedToolCall]:
        """Fallback Stepfun: XML/Qwen-style <tool_call><function=name>…"""
        if "<function=" not in content and "<tool_call>" not in content.lower():
            return None
        fn_match = re.search(r"<function=([^>\s]+)>", content, re.IGNORECASE)
        if not fn_match:
            fn_match = re.search(r'"tool"\s*:\s*"([^"]+)"', content)
        if not fn_match:
            return None
        name = cls._normalize_stepfun_tool_name(fn_match.group(1))
        args: Dict[str, Any] = {}
        for param_match in re.finditer(
            r"<parameter=([^>\s]+)>\s*([^<]+)\s*</parameter>", content, re.IGNORECASE
        ):
            key = param_match.group(1).strip()
            val = param_match.group(2).strip()
            if val.isdigit():
                args[key] = int(val)
            else:
                try:
                    args[key] = float(val)
                except ValueError:
                    args[key] = val
        return ParsedToolCall(name=name, arguments=args)

    @staticmethod
    def _parse_stepfun_tool_json(content: str) -> Optional[ParsedToolCall]:
        """Fallback Stepfun: JSON inline {"tool":"...", "arguments":{...}}."""
        try:
            data = json.loads(content)
            if isinstance(data, dict) and data.get("tool"):
                return ParsedToolCall(
                    name=VLLMClient._normalize_stepfun_tool_name(str(data["tool"])),
                    arguments=data.get("arguments") if isinstance(data.get("arguments"), dict) else {},
                )
        except json.JSONDecodeError:
            pass
        match = re.search(r'\{\s*"tool"\s*:\s*"([^"]+)"', content)
        if not match:
            return None
        try:
            data = json.loads(content[match.start() : content.rfind("}") + 1])
            return ParsedToolCall(
                name=VLLMClient._normalize_stepfun_tool_name(str(data.get("tool", ""))),
                arguments=data.get("arguments") if isinstance(data.get("arguments"), dict) else {},
            )
        except (json.JSONDecodeError, ValueError):
            return None

    async def complete_text(self, prompt: str, max_tokens: int = 120) -> str:
        """Completado no-streaming para commentary batch y prompts cortos."""
        return await self._complete_speech_messages(
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )

    async def _complete_speech_messages(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = SPEECH_MAX_TOKENS,
    ) -> str:
        """Completado para voz: content + fallback reasoning sanitizado."""
        client = self._get_client()
        create_kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.2,
        }
        extra = self._stepfun_speech_extra_body()
        if extra:
            create_kwargs["extra_body"] = extra
        resp = await client.chat.completions.create(**create_kwargs)
        return self._extract_speech_from_message(resp.choices[0].message)

    async def complete_text_legacy(self, prompt: str, max_tokens: int = 120) -> str:
        """Completado legacy sin forzar speech mode."""
        client = self._get_client()
        create_kwargs: dict = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.4,
        }
        extra = self._stepfun_extra_body()
        if extra:
            create_kwargs["extra_body"] = extra
        resp = await client.chat.completions.create(**create_kwargs)
        return self._message_speech_text(resp.choices[0].message)

    async def ask_streaming_messages(
        self,
        messages: List[Dict[str, str]],
        tier: str = "FAST",
    ) -> AsyncGenerator[str, None]:
        """Streaming multi-turno para PTT/ask (system + user)."""
        max_tokens = SPEECH_MAX_TOKENS
        from src.intelligence.llm_speech_sanitize import SpeechSanitizeState, sanitize_llm_speech_delta

        speech_state = SpeechSanitizeState()

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }
        stepfun_extra = self._stepfun_speech_extra_body()
        if stepfun_extra:
            payload.update(stepfun_extra)

        content_text = ""
        reasoning_text = ""
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=90.0,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                        else:
                            data_str = line

                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            choices = data.get("choices", [])
                            if not choices:
                                continue

                            delta = data["choices"][0]["delta"]

                            content_token = delta.get("content") or ""
                            reasoning_token = delta.get("reasoning_content") or ""

                            if reasoning_token:
                                reasoning_text += reasoning_token
                                continue

                            token = content_token
                            if not token:
                                continue

                            if token.strip() in ("", "<|im_end|>", "<|im_start|>", "<!--", "-->", "<think>"):
                                continue

                            if token.strip().startswith("<"):
                                token = re.sub(r"^\s*</?think[^>]*>\s*", "", token)
                                if not token or token.strip() in ("\n", "\n\n"):
                                    continue

                            content_text += token
                            _, delta_spoken = sanitize_llm_speech_delta(content_text, speech_state)
                            if delta_spoken:
                                yield delta_spoken
                        except json.JSONDecodeError:
                            continue

                    from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

                    final_text = sanitize_llm_speech(content_text, finalize=True)
                    if not final_text.strip() and reasoning_text.strip():
                        final_text = sanitize_llm_speech(reasoning_text, finalize=True)
                        if final_text.strip():
                            logger.info(
                                "PTT LLM stream: content vacío, usada reasoning sanitize (%d chars)",
                                len(final_text),
                            )
                    if not final_text.strip():
                        final_text = await self._complete_speech_messages(messages, max_tokens=max_tokens)
                    if final_text and final_text != speech_state.last_spoken:
                        remaining = (
                            final_text[len(speech_state.last_spoken) :]
                            if final_text.startswith(speech_state.last_spoken)
                            else final_text
                        )
                        if remaining.strip():
                            yield remaining
        except Exception as e:
            logger.error(f"Error en ask_streaming_messages: {e}", exc_info=True)

    async def ask_streaming_text(self, prompt: str, tier: str = "FAST") -> AsyncGenerator[str, None]:
        """Streaming de un solo mensaje user (legacy / scripts)."""
        async for token in self.ask_streaming_messages(
            [{"role": "user", "content": prompt}],
            tier=tier,
        ):
            yield token