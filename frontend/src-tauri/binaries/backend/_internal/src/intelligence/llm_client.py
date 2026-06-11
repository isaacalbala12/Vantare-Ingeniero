import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

import httpx
from openai import AsyncOpenAI
from src.config import settings
from src.intelligence import prompt_templates
from src.intelligence.llm_speech_sanitize import sanitize_llm_speech
from src.models.messages import AdviceEndMessage, AdviceStartMessage, AdviceTokenMessage, UIAction
from src.transport.broadcaster import send

logger = logging.getLogger("vantare.llm_client")


@dataclass
class ParsedToolCall:
    name: str
    arguments: dict[str, Any]


@dataclass
class AskWithToolsResult:
    content: str = ""
    tool_calls: list[ParsedToolCall] = field(default_factory=list)


class VLLMClient:
    """Cliente asíncrono para el motor de lenguaje LLM (API compatible con OpenAI).

    Se conecta a la URL configurada en LLM_BASE_URL usando el SDK oficial de OpenAI.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.LLM_API_KEY
        self._base_url = base_url or settings.LLM_BASE_URL
        self._model = model or settings.LLM_MODEL
        self._client: AsyncOpenAI | None = None

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

    async def ask_streaming(self, prompt: str, tier: str, advice_id: str, engine_ref=None) -> None:
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
        actions: list[UIAction] = []

        try:
            client = self._get_client()

            competitors = []
            if engine_ref and hasattr(engine_ref, "get_competitors_list"):
                competitors = engine_ref.get_competitors_list()

            stream = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
                stream=True,
                tools=prompt_templates.get_llm_tools(include_competitor_query=bool(competitors)),
            )

            tool_call_name: str | None = None
            tool_call_arguments: dict[str, Any] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Solo emitir contenido final al frontend; reasoning_content queda fuera de radio/TTS.
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    continue

                token = delta.content if delta.content else None
                if token:
                    full_text += token
                    spoken = sanitize_llm_speech(token, finalize=False, preserve_trailing_space=True)
                    if spoken:
                        send(AdviceTokenMessage(advice_id=advice_id, token=spoken, event="advice_token"))

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
                            logger.info("Acción visual parseada del LLM: %s -> %s", target, action)
                    except Exception as e:
                        logger.warning("Error parseando tool call arguments (idx=%s): %s", idx, e)

            # 4. Emitir mensaje final (sin chain-of-thought)
            final_text = sanitize_llm_speech(full_text, finalize=True)
            if not final_text.strip():
                final_text = "... Sin respuesta audible del ingeniero ..."
            end_msg = AdviceEndMessage(
                advice_id=advice_id,
                full_text=final_text,
                actions=actions,
                event="advice_end",
            )
            send(end_msg)

        except asyncio.CancelledError:
            logger.info("Streaming LLM para el consejo %s cancelado por preempción.", advice_id)
            interruption_msg = "--- Transmisión de radio interrumpida por evento de mayor prioridad ---"
            send(
                AdviceEndMessage(
                    advice_id=advice_id,
                    full_text=interruption_msg,
                    actions=[],
                    event="advice_end",
                )
            )

        except Exception as e:
            logger.error("Error en streaming LLM: %s", e)
            error_fallback = "... Pérdida de comunicación de radio con el muro de boxes ..."
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

        try:
            async with (
                httpx.AsyncClient() as client,
                client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30.0,
                ) as response,
            ):
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    # Formato SSE: "data: {...}"
                    data_str = line[6:].strip() if line.startswith("data: ") else line

                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        choices = data.get("choices", [])
                        if not choices:
                            continue

                        delta = data["choices"][0]["delta"]

                        # Descartar completamente los chunks de razonamiento
                        if delta.get("reasoning_content"):
                            continue

                        # Solo procesar el contenido real (respuesta final)
                        token = delta.get("content", "")
                        if not token:
                            continue

                        # Limpiar etiquetas de control residuales
                        if token.strip() in ("", "<|im_end|>", "<|im_start|>", "<!--", "-->", "<think>"):
                            continue

                        # Eliminar prefijos de etiquetas que puedan colarse
                        if token.strip().startswith("<"):
                            token = re.sub(r"^\s*</?think[^>]*>\s*", "", token)
                            if not token or token.strip() in ("\n", "\n\n"):
                                continue

                        # Token válido
                        full_text += token
                        yield token
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error en ask_streaming_text: {e}", exc_info=True)

    def _is_stepfun(self) -> bool:
        return "stepfun" in (self._base_url or "").lower()

    def _stepfun_extra_body(self) -> dict[str, Any] | None:
        """Desactiva chain-of-thought en Stepfun para respuestas directas de radio."""
        if self._is_stepfun():
            return {"thinking": {"type": "off"}}
        return None

    @staticmethod
    def _extract_message_speech(message: Any) -> str:
        """Texto hablable del mensaje: content primero, reasoning_content como respaldo."""
        content = (getattr(message, "content", None) or "").strip()
        if content:
            return content
        reasoning = getattr(message, "reasoning_content", None) or ""
        if isinstance(reasoning, str):
            return reasoning.strip()
        return ""

    @staticmethod
    def _delta_reasoning(delta: Any) -> str:
        raw = getattr(delta, "reasoning_content", None) or ""
        return raw if isinstance(raw, str) else ""

    _STEPFUN_TOOL_ALIASES: dict[str, str] = {
        "consultar_estado_combustible": "get_fuel_status",
        "get_fuel_status": "get_fuel_status",
    }

    @staticmethod
    def _parse_stepfun_tool_markup(raw: str) -> ParsedToolCall | None:
        import re

        fn_match = re.search(r"<function=([^>\n]+)>", raw, re.IGNORECASE)
        if not fn_match:
            return None
        raw_name = fn_match.group(1).strip()
        mapped = VLLMClient._STEPFUN_TOOL_ALIASES.get(raw_name, raw_name)
        args: dict[str, Any] = {}
        for param_match in re.finditer(
            r"<parameter=([^>\n]+)>\s*(.*?)\s*</parameter>",
            raw,
            re.DOTALL | re.IGNORECASE,
        ):
            args[param_match.group(1).strip()] = param_match.group(2).strip()
        return ParsedToolCall(name=mapped, arguments=args)

    async def complete_text(self, prompt: str, *, max_tokens: int = 500) -> str:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=max_tokens,
        )
        return (response.choices[0].message.content or "").strip()

    async def complete_from_messages(self, messages: list[dict], *, max_tokens: int = 500) -> str:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        extra = self._stepfun_extra_body()
        if extra:
            kwargs["extra_body"] = extra
        response = await client.chat.completions.create(**kwargs)
        raw = self._extract_message_speech(response.choices[0].message)
        if not raw.strip():
            logger.warning("LLM complete_from_messages: respuesta vacía (content y reasoning)")
        return sanitize_llm_speech(raw, finalize=True)

    async def _complete_speech_messages(self, messages: list[dict], *, max_tokens: int = 400) -> str:
        return await self.complete_from_messages(messages, max_tokens=max_tokens)

    async def ask_streaming_messages(
        self,
        messages: list[dict],
        *,
        tier: str = "FAST",
    ) -> AsyncGenerator[str, None]:
        del tier
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 500,
            "stream": True,
        }
        extra = self._stepfun_extra_body()
        if extra:
            kwargs["extra_body"] = extra
        stream = await client.chat.completions.create(**kwargs)
        content_buf = ""
        reasoning_buf = ""
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = self._delta_reasoning(delta)
            if reasoning:
                reasoning_buf += reasoning
            token = delta.content or ""
            if not token:
                continue
            content_buf += token
            spoken = sanitize_llm_speech(token, finalize=False, preserve_trailing_space=True)
            if spoken:
                yield spoken

        if not content_buf.strip() and reasoning_buf.strip():
            logger.warning(
                "PTT stream sin content (%d chars reasoning); usando sanitizado de respaldo",
                len(reasoning_buf),
            )
            spoken = sanitize_llm_speech(reasoning_buf, finalize=True)
            if spoken:
                yield spoken

    async def ask_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        *,
        tool_choice: str = "auto",
        max_tokens: int = 256,
    ) -> AskWithToolsResult:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }
        extra = self._stepfun_extra_body()
        if extra:
            kwargs["extra_body"] = extra
        if tools and not self._is_stepfun():
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = await client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        content = sanitize_llm_speech(self._extract_message_speech(message), finalize=True)
        parsed: list[ParsedToolCall] = []
        for tc in message.tool_calls or []:
            fn = tc.function
            if not fn or not fn.name:
                continue
            try:
                args = json.loads(fn.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            parsed.append(ParsedToolCall(name=fn.name, arguments=args if isinstance(args, dict) else {}))
        return AskWithToolsResult(content=content, tool_calls=parsed)
