# 🏎️ Vantare Ingeniero IA — Orquestador de Proyecto

## ¿Qué es?
Ingeniero de carreras con IA para Le Mans Ultimate. Escucha voz, analiza telemetría en tiempo real, responde con voz sintetizada y calcula estrategia. Distribuido en dos PCs (Windows con LMU + frontend Tauri; Linux con LLM local, LiteLLM y backend FastAPI).

## Estado actual (26 mayo 2026)
- Telemetría LMU: ✅ 20 Hz vía shared memory.
- Motor determinista: ✅ shared-strategy funcional (combustible, neumáticos, pits).
- LLM local: ✅ Qwen 3.5 4B MQ4 en Hipfire (Vulkan), streaming SSE.
- LiteLLM: ✅ proxy en :4000, OpenAI-compatible, expuesto por Cloudflare Tunnel: `https://considering-replies-nursery-gnome.trycloudflare.com`
- TTS: ✅ Edge TTS (es-ES-AlvaroNeural), ~500ms.
- Flujo HTTP texto→voz: ✅ completo.
- WebSocket telemetría en vivo: ⚠️ pendiente de reparar.
- Reconocimiento de voz: ⚠️ solo Windows/Tauri (Linux no compatible).
- Prompt del sistema: ✅ SYSTEM_PROMPT_BASIC corregido (respuesta natural y abierta).
- Código: ⚠️ pendiente limpieza (legacy CrofAI, imports no usados).

## Decisiones técnicas clave
- Python 3.12+, FastAPI + WebSocket.
- Hipfire + LiteLLM para inferencia local con API OpenAI.
- Edge TTS gratuito, sin consumo de VRAM.
- Cloudflare Tunnel para exponer LLM sin abrir puertos.
- React + Zustand, Tauri (no Electron) para frontend ligero.
- Qwen 4B en vez de 9B por bug de `reasoning_content`.

## Próximo objetivo (prioridad)
Reparar WebSocket y ajustar el prompt del sistema para que el ingeniero sea contextual (no hable de carreras sin telemetría). Luego, integrar el motor determinista en el flujo de preguntas.

## Tareas inmediatas (orden sugerido)
1. Ajustar SYSTEM_PROMPT_BASIC: respuestas contextuales, sin frases fuera de lugar.
2. Reparar WebSocket para telemetría en vivo (frontend en PC principal).
3. Integrar shared-strategy en el endpoint /ask para enriquecer respuestas del LLM.
4. Limpiar código: eliminar imports no usados, código legacy de CrofAI y duplicados.
5. Probar reconocimiento de voz en Windows/Tauri (si procede).

## Próximos hitos
- Motor determinista integrado → LLM con datos reales de carrera.
- Prompt contextual → ingeniero responde según modo (carrera o genérico).
- Beta cerrada con 5-10 pilotos.

## Comandos de prueba
```bash
# Probar SYSTEM_PROMPT_BASIC (sin telemetría)
curl -X POST http://localhost:8008/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Cuánto es 2+2?"}'

# Probar con historial de chat
curl -X POST http://localhost:8008/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "¿Qué presión de neumáticos usamos?",
    "chat_history": [
      {"role": "user", "content": "Llevamos 3停了"},
      {"role": "assistant", "content": "Bien, entrada en 2 vuelta"}
    ]
  }'
```

## Historial de decisiones
2026-05-26: SYSTEM_PROMPT_BASIC corregido - respuesta natural y abierta, sin arrogancia.
