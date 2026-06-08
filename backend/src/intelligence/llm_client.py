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
        if self._is_stepfun():
            return {"thinking": {"type": "off"}}
        return None

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

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Solo contenido hablable — nunca razonamiento interno (Stepfun/Qwen)
                token = delta.content if delta.content else None

                if token:
                    full_text += token
                    from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

                    spoken = sanitize_llm_speech(full_text)
                    prev_spoken = sanitize_llm_speech(full_text[:-len(token)] if len(full_text) > len(token) else "")
                    delta_spoken = spoken[len(prev_spoken):] if spoken.startswith(prev_spoken) else spoken
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

            full_text = sanitize_llm_speech(full_text)
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
        max_tokens: int = 128,
    ) -> AskWithToolsResult:
        """Completado no-streaming con tool calls (PTT turno 1)."""
        client = self._get_client()
        create_kwargs: dict = {
            "model": self._model,
            "messages": messages,
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
        content = (message.content or "").strip()
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
        return (resp.choices[0].message.content or "").strip()

    @staticmethod
    def _parse_stepfun_tool_json(content: str) -> Optional[ParsedToolCall]:
        """Fallback Stepfun: JSON inline {"tool":"...", "arguments":{...}}."""
        try:
            data = json.loads(content)
            if isinstance(data, dict) and data.get("tool"):
                return ParsedToolCall(
                    name=str(data["tool"]),
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
                name=str(data.get("tool", "")),
                arguments=data.get("arguments") if isinstance(data.get("arguments"), dict) else {},
            )
        except (json.JSONDecodeError, ValueError):
            return None

    async def complete_text(self, prompt: str, max_tokens: int = 120) -> str:
        """Completado no-streaming para commentary batch y prompts cortos."""
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
        return (resp.choices[0].message.content or "").strip()

    async def ask_streaming_text(self, prompt: str, tier: str = "FAST") -> AsyncGenerator[str, None]:
        """Similar a ask_streaming() pero devuelve generador de texto para HTTP, no emite WebSocket.
        
        Usa httpx.stream() directamente para manejar respuestas SSE de LiteLLM.
        """
        max_tokens = 500
        full_text = ""

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "stream": True,
        }
        stepfun_extra = self._stepfun_extra_body()
        if stepfun_extra:
            payload.update(stepfun_extra)

        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line:
                            continue

                        # Formato SSE: "data: {...}"
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

                            # Descartar razonamiento explícito del stream
                            if delta.get("reasoning_content"):
                                continue

                            token = delta.get("content", "")
                            if not token:
                                continue

                            if token.strip() in ("", "<|im_end|>", "<|im_start|>", "<!--", "-->", "<think>"):
                                continue

                            if token.strip().startswith("<"):
                                token = re.sub(r"^\s*</?think[^>]*>\s*", "", token)
                                if not token or token.strip() in ("\n", "\n\n"):
                                    continue

                            full_text += token
                            from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

                            spoken = sanitize_llm_speech(full_text)
                            prev_spoken = sanitize_llm_speech(
                                full_text[: -len(token)] if len(full_text) > len(token) else ""
                            )
                            delta_spoken = (
                                spoken[len(prev_spoken):] if spoken.startswith(prev_spoken) else spoken
                            )
                            if delta_spoken:
                                yield delta_spoken
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Error en ask_streaming_text: {e}", exc_info=True)