from typing import List, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.services.llm_service import llamar_copiloto_stream

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(..., description="Rol de la interacción: 'user' o 'assistant'")
    content: str = Field(..., description="Contenido del mensaje de texto")


class AskRequest(BaseModel):
    question: str = Field(..., description="Pregunta enviada por el piloto")
    chat_history: Optional[List[ChatMessage]] = Field(
        default=None, description="Historial de mensajes previos de la sesión"
    )


@router.post("/ask")
async def ask_copilot(request: Request, body: AskRequest):
    """Endpoint POST para pruebas con curl. Devuelve texto plano.
    
    El flujo PTT real usa WebSocket (pilot_question).
    El TTS se solicita al endpoint /tts por separado.
    """
    
    # 1. Obtener servicio de estrategia desde el estado de la aplicación
    strategy_service = getattr(request.app.state, "strategy_service", None)
    if not strategy_service:
        raise HTTPException(
            status_code=503,
            detail="El motor de estrategia e ingenieria no está inicializado en el servidor."
        )

    # 2. Generar el resumen de carrera enriquecido con telemetría actual
    contexto = strategy_service.get_race_summary()

    # 3. Formatear chat_history para la API de OpenAI si existe
    formatted_history = []
    if body.chat_history:
        for msg in body.chat_history:
            formatted_history.append({
                "role": msg.role,
                "content": msg.content
            })

    # 4. Consumir el stream completo para obtener el texto de respuesta
    full_response = ""
    async for chunk in llamar_copiloto_stream(
        pregunta=body.question,
        contexto=contexto,
        chat_history=formatted_history
    ):
        full_response += chunk

    if not full_response.strip():
        full_response = "No he podido generar una respuesta en este momento."

    # 5. Devolver texto plano (el TTS se sirve desde /tts)
    return Response(
        content=full_response,
        media_type="text/plain",
    )
