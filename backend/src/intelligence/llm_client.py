import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from src.config import settings
from src.models.messages import AdviceStartMessage, AdviceTokenMessage, AdviceEndMessage, UIAction
from src.transport.broadcaster import send
from src.intelligence.prompt_templates import SYSTEM_PROMPT, UI_TOOLS

logger = logging.getLogger("vantare.llm_client")


class VLLMClient:
    """Cliente asíncrono para el motor de lenguaje CrofAI (API compatible con OpenAI).

    Se conecta a CrofAI (https://crof.ai/v1) usando el SDK oficial de OpenAI.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or settings.CROFAI_API_KEY
        self._base_url = base_url or settings.CROFAI_BASE_URL
        self._model = model or settings.LLM_MODEL
        self._client: Optional[AsyncOpenAI] = None

        if not self._api_key:
            logger.warning(
                "*** CROFAI_API_KEY no configurada. El LLM no funcionará. ***\n"
                "    Crea un archivo backend/.env con:\n"
                "    CROFAI_API_KEY=tu-api-key-aqui"
            )

        logger.info(
            "LLMClient inicializado: base_url=%s model=%s api_key=%s",
            self._base_url,
            self._model,
            "***configurada***" if self._api_key else "VACÍA",
        )

    def _get_client(self) -> AsyncOpenAI:
        """Devuelve (y cachea) el cliente OpenAI asíncrono."""
        if self._client is None:
            import httpx
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=httpx.Timeout(25.0, connect=10.0, read=20.0),
                max_retries=1,
            )
        return self._client

    async def health_check(self) -> bool:
        """Verifica conectividad con CrofAI listando los modelos disponibles."""
        try:
            client = self._get_client()
            models = await client.models.list()
            model_ids = [m.id for m in models.data]
            logger.info(
                "CrofAI health OK: %d modelos disponibles. Modelo objetivo: %s",
                len(model_ids),
                self._model,
            )
            # Verificar que el modelo configurado existe en la lista
            if self._model not in model_ids:
                logger.warning(
                    "Modelo '%s' no encontrado en CrofAI. Disponibles: %s",
                    self._model,
                    ", ".join(model_ids[:10]),
                )
            return True
        except Exception as e:
            logger.warning("CrofAI health check fallido: %s", e)
            return False

    async def ask_streaming(
        self, prompt: str, tier: str, advice_id: str, engine_ref=None
    ) -> None:
        """Realiza una consulta por streaming al LLM de CrofAI.

        Los tokens se emiten al frontend vía WebSocket (AdviceTokenMessage).
        Al finalizar se emite AdviceEndMessage con el texto completo y acciones UI.
        """
        # 1. Emitir mensaje de inicio
        start_msg = AdviceStartMessage(advice_id=advice_id, tier=tier, event="advice_start")
        send(start_msg)

        # 2. Configurar parámetros según el tier
        tier_upper = tier.upper()
        if tier_upper == "FAST":
            max_tokens = 80
        elif tier_upper == "STANDARD":
            max_tokens = 150
        else:
            max_tokens = 300

        full_text = ""
        actions: List[UIAction] = []

        try:
            client = self._get_client()

            stream = await client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=max_tokens,
                stream=True,
                tools=UI_TOOLS if UI_TOOLS else None,
            )

            tool_call_name: Optional[str] = None
            tool_call_arguments: Dict[str, Any] = {}

            async for chunk in stream:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Contenido de texto (modelos estándar y de razonamiento Qwen/vLLM)
                token = None
                if delta.content:
                    token = delta.content
                elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
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
                            # Acumular argumentos (pueden llegar en varios chunks)
                            existing = tool_call_arguments.get(tc.index, "")
                            tool_call_arguments[tc.index] = existing + tc.function.arguments

            # 3. Procesar tool calls al final del stream
            if tool_call_name and tool_call_arguments:
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
            logger.error("Error en streaming LLM (CrofAI): %s", e)
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
