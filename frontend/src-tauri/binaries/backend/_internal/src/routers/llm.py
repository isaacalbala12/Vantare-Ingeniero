from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = Field(..., description="Rol de la interacción: 'user' o 'assistant'")
    content: str = Field(..., description="Contenido del mensaje de texto")


class AskRequest(BaseModel):
    question: str = Field(..., description="Pregunta enviada por el piloto")
    chat_history: list[ChatMessage] | None = Field(
        default=None, description="Historial de mensajes previos de la sesión"
    )


@router.post("/ask")
async def ask_copilot(request: Request, body: AskRequest):
    """Endpoint POST para preguntas de texto directo.

    Usa IntelligenceEngine (mismo motor que el WebSocket) para garantizar
    respuestas consistentes con el sistema de ingeniero de carreras.
    """

    # 1. Obtener IntelligenceEngine desde el estado de la aplicación
    engine = getattr(request.app.state, "intelligence_engine", None)
    if not engine:
        raise HTTPException(status_code=503, detail="IntelligenceEngine no está inicializado en el servidor.")

    # 2. Formatear chat_history si existe
    formatted_history = []
    if body.chat_history:
        for msg in body.chat_history:
            formatted_history.append({"role": msg.role, "content": msg.content})

    # 3. Procesar la pregunta usando IntelligenceEngine
    full_response = ""
    async for chunk in engine.ask_async(body.question, formatted_history):
        full_response += chunk

    if not full_response.strip():
        full_response = "No he podido generar una respuesta en este momento."

    # 4. Devolver texto plano (el TTS se solicita al endpoint /tts)
    return Response(
        content=full_response,
        media_type="text/plain",
    )
