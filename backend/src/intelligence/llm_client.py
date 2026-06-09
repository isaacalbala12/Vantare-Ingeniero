import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

import httpx
from openai import AsyncOpenAI
from src.config import settings
from src.intelligence import prompt_templates
from src.models.messages import AdviceEndMessage, AdviceStartMessage, AdviceTokenMessage, UIAction
from src.transport.broadcaster import send

logger = logging.getLogger("vantare.llm_client")


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
            competitor_query_args: dict[str, Any] | None = None

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Contenido de texto (modelos estándar y de razonamiento Qwen/vLLM)
                token = None
                if delta.content:
                    token = delta.content
                elif hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    token = delta.reasoning_content

                if token:
                    full_text += token
                    send(AdviceTokenMessage(advice_id=advice_id, token=token, event="advice_token"))

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

            # 4. Emitir mensaje final
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
