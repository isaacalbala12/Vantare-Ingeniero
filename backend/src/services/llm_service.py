import json
import logging
import httpx

from src.config import settings

logger = logging.getLogger("vantare.llm_service")

LLM_API_URL = f"{settings.LLM_BASE_URL}/chat/completions"

SYSTEM_PROMPT = (
    "Eres un entrenador de simracing profesional. Analizas datos de telemetría "
    "y devuelves SOLO un JSON válido con las claves exactas: tipo, explicacion, consejo. "
    "No escribas texto fuera del JSON. Tipos válidos: "
    "frenada_tardia, trail_braking_insuficiente, sobreviraje_aceleracion, "
    "subviraje_entrada, buen_trail_braking."
)

FEW_SHOT_EXAMPLES = [
    {
        "role": "user",
        "content": "Contexto: frenada 195→85 km/h en 3.2s, brake 100%, steering 4.5° girado.",
    },
    {
        "role": "assistant",
        "content": '{"tipo":"frenada_tardia","explicacion":"Frenada muy cerca del vertice.","consejo":"Adelanta frenada 15m."}',
    },
    {
        "role": "user",
        "content": "Contexto: frenada 160→90 km/h en 2.1s, brake 85%, steering 1.2° casi recto.",
    },
    {
        "role": "assistant",
        "content": '{"tipo":"sobreviraje_aceleracion","explicacion":"Patinaje al acelerar temprano.","consejo":"Retrasa apertura gas 0.3s."}',
    },
]

MOCK_RESPONSE = {
    "tipo": "ejemplo_sin_api",
    "explicacion": "API key no configurada. El flujo completo funciona.",
    "consejo": "Configura GROQ_API_KEY en tu .env para activar el analisis con LLM.",
}

# Prompts y mocks para análisis de Cuartel General
SYSTEM_PROMPT_SESSION_TITLE = (
    "Eres un periodista de automovilismo profesional. Recibes datos de telemetría "
    "de una sesión de simracing y debes generar un TITULAR ÚNICO de máximo 15 palabras "
    "que resuma lo más destacado de la sesión. "
    "Devuelve SOLO un JSON válido con la clave: session_title."
)

SYSTEM_PROMPT_TRAINING_PLAN = (
    "Eres un entrenador de simracing profesional. Basado en los datos de telemetría, "
    "genera un plan de entrenamiento semanal con 7 misiones (una por día). "
    "Devuelve SOLO un JSON válido con la clave: training_plan, que sea un array de objetos "
    "con claves: day, title, description, difficulty. "
    "Los días deben ser: Lunes, Martes, Miércoles, Jueves, Viernes, Sábado, Domingo. "
    "Difficulty puede ser: Fácil, Medio, Difícil."
)

MOCK_SESSION_TITLE = {
    "session_title": "Sesión sólida con progresión constante en el Autódromo Nacional"
}

MOCK_TRAINING_PLAN = {
    "training_plan": [
        {
            "day": "Lunes",
            "title": "Análisis de telemetría",
            "description": "Revisar datos de la sesión anterior",
            "difficulty": "Medio",
        },
        {
            "day": "Martes",
            "title": "Práctica de frenada",
            "description": "Trabajar en puntos de frenada para mejorar consistencia",
            "difficulty": "Medio",
        },
        {
            "day": "Miércoles",
            "title": "Optimización de trazada",
            "description": "Estudiar ángulos de giro y mejorar salida de curvas",
            "difficulty": "Difícil",
        },
        {
            "day": "Jueves",
            "title": "Sesión de clasificación",
            "description": "Simular vuelta rápida con enfoque en sectores",
            "difficulty": "Difícil",
        },
        {
            "day": "Viernes",
            "title": "Entrenamiento de consistencia",
            "description": "Completar 10 vueltas con delta menor a 0.5s",
            "difficulty": "Medio",
        },
        {
            "day": "Sábado",
            "title": "Carrera simulada",
            "description": "Simular una carrera completa con gestión de neumáticos",
            "difficulty": "Difícil",
        },
        {
            "day": "Domingo",
            "title": "Descanso activo",
            "description": "Revisar datos de la semana y planificar próxima sesión",
            "difficulty": "Fácil",
        },
    ]
}


async def _llm_request(messages: list, response_json: bool = True) -> dict | None:
    """Realiza una request asíncrona al LLM."""
    if not settings.LLM_API_KEY:
        logger.warning("GROQ_API_KEY is empty. Skipping LLM request and using mock fallback.")
        return None

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
    }

    if response_json:
        # Forzar respuesta en formato JSON estructurado
        payload["response_format"] = {"type": "json_object"}

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                LLM_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()

            # Sanitización del contenido por si acaso (para compatibilidad)
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(
                    lines[1:-1] if lines[-1].startswith("```") else lines[1:]
                )

            return json.loads(content)
    except Exception as e:
        logger.error(f"LLM request failed: {e}", exc_info=True)
        return None


async def llamar_llm(contexto: dict) -> dict:
    """Envía el contexto al LLM. Si no hay key, devuelve respuesta mock."""
    if not settings.LLM_API_KEY:
        return MOCK_RESPONSE

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *FEW_SHOT_EXAMPLES,
        {
            "role": "user",
            "content": f"Contexto: {json.dumps(contexto, ensure_ascii=False)}",
        },
    ]

    result = await _llm_request(messages)
    return result if result is not None else MOCK_RESPONSE


async def llamar_llm_session_title(contexto: dict) -> dict:
    """Genera un titular de sesión usando el LLM. Mock si no hay API key."""
    if not settings.LLM_API_KEY:
        return MOCK_SESSION_TITLE

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_SESSION_TITLE},
        {
            "role": "user",
            "content": f"Contexto de sesión: {json.dumps(contexto, ensure_ascii=False)}",
        },
    ]

    result = await _llm_request(messages)
    if result is None or "session_title" not in result:
        return MOCK_SESSION_TITLE
    return result


async def llamar_llm_training_plan(contexto: dict) -> dict:
    """Genera un plan de entrenamiento semanal usando el LLM. Mock si no hay API key."""
    if not settings.LLM_API_KEY:
        return MOCK_TRAINING_PLAN

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_TRAINING_PLAN},
        {
            "role": "user",
            "content": f"Contexto de sesión: {json.dumps(contexto, ensure_ascii=False)}",
        },
    ]

    result = await _llm_request(messages)
    if result is None or "training_plan" not in result:
        return MOCK_TRAINING_PLAN
    return result


async def llamar_copiloto_stream(pregunta: str, contexto: dict, chat_history: list = None):
    """Envía la pregunta del piloto y el contexto de carrera actual al LLM.
    
    Yields chunks de texto en tiempo real (streaming).
    """
    if not settings.LLM_API_KEY:
        yield "Copiado piloto, pero no tengo conexión de red activa en boxes ahora mismo. Configura la clave de LLM_API_KEY para que pueda guiarte."
        return

    system_prompt = (
        "Eres el Ingeniero de Carrera Principal de un equipo de simracing. Tu piloto te está hablando "
        "por la radio de boxes/coche durante una sesión de Le Mans Ultimate.\n\n"
        "Debes responder de forma extremadamente concisa, directa y profesional (como un ingeniero de F1/WEC real, "
        "ej. 'Copiado, piloto', 'Entendido'). Usa un tono calmado, enfocado en datos, neumáticos, combustible y seguridad.\n\n"
        "Se te proporciona el contexto en tiempo real del coche. Usa estos datos para responder con precisión y brevedad.\n"
        "No divagues ni uses un lenguaje pomposo. Respuestas cortas, listas para oír en pista."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"CONTEXTO ACTUAL DE CARRERA: {json.dumps(contexto, ensure_ascii=False)}"}
    ]

    if chat_history:
        # Añadir últimas 3 interacciones (6 mensajes)
        messages.extend(chat_history[-6:])

    messages.append({"role": "user", "content": pregunta})

    headers = {
        "Authorization": f"Bearer {settings.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.LLM_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 512,
        "stream": True
    }

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                LLM_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data_json = json.loads(data_str)
                            delta = data_json["choices"][0]["delta"]
                            if "content" in delta:
                                yield delta["content"]
                        except Exception:
                            pass
    except Exception as e:
        logger.error(f"Error in LLM streaming: {e}", exc_info=True)
        yield f" Error de radio: {e}. Intenta de nuevo."

