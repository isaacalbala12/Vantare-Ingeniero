from __future__ import annotations

import json
import logging

from src.intelligence.crewchief_events.commands import match_fast_command
from src.intelligence.pilot_tool_executor import PilotToolExecutor
from src.intelligence import prompt_templates

logger = logging.getLogger("vantare.pilot_ptt_agent")

_executor = PilotToolExecutor()


async def handle_pilot_ptt(engine, question: str) -> None:
    """PTT tool-first: LLM elige tools; loop corto si mixto; circuit breaker; free-form."""
    question = (question or "").strip()
    if not question:
        return

    if _try_circuit_breaker(engine, question):
        return

    competitors = engine.get_competitors_list()
    tools = prompt_templates.get_pilot_ptt_tools(include_competitor_query=bool(competitors))
    context = engine.build_ptt_context_minimal()

    user_content = f"Piloto dice: {question}"
    if context:
        user_content = f"{user_content}\n\nContexto mínimo:\n{context}"

    messages = [
        {"role": "system", "content": prompt_templates.PILOT_PTT_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    response = None
    try:
        response = await engine.llm_client.ask_with_tools(
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
    except Exception as exc:
        logger.warning("PTT ask_with_tools falló: %s", exc)

    if response and response.tool_calls:
        mixed = _executor.is_mixed_intent(response.tool_calls)
        results = await _executor.run_all(
            engine,
            response.tool_calls,
            emit_voice=not mixed,
        )

        if _executor.is_pure_action(response.tool_calls):
            return

        if mixed:
            summary = await _turn_two_summary(engine, messages, response.tool_calls, results)
            if summary:
                engine._emit_voice_response(summary)
            return

        if response.content.strip():
            from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

            spoken = sanitize_llm_speech(response.content.strip())
            if spoken:
                engine._emit_voice_response(spoken)
        return

    await engine._handle_free_form_question(question)


async def _turn_two_summary(engine, messages, tool_calls, results) -> str:
    """Turno 2: una frase radio que combine acción + consulta."""
    tool_summary = [
        {
            "tool": tc.name,
            "arguments": tc.arguments,
            "result": res.spoken_message or res.data,
            "ok": res.ok,
        }
        for tc, res in zip(tool_calls, results)
    ]
    follow_messages = list(messages)
    follow_messages.append(
        {
            "role": "assistant",
            "content": f"Tools ejecutadas: {json.dumps(tool_summary, ensure_ascii=False)}",
        }
    )
    follow_messages.append(
        {"role": "user", "content": prompt_templates.PILOT_PTT_TURN_TWO_PROMPT}
    )
    try:
        raw = await engine.llm_client.complete_from_messages(follow_messages, max_tokens=150)
        from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

        return sanitize_llm_speech(raw)
    except Exception as exc:
        logger.warning("PTT turno 2 falló: %s", exc)
        parts = [r.spoken_message for r in results if r.spoken_message]
        return " ".join(parts)


def _try_circuit_breaker(engine, question: str) -> bool:
    """Red de seguridad: speak_only y spotter si el LLM no invocó tool."""
    cmd = match_fast_command(question)
    if cmd is None:
        return False
    if cmd.intent not in (
        "speak_only_on",
        "speak_only_off",
        "spotter_enable",
        "spotter_disable",
    ):
        return False
    return engine._try_handle_fast_command(cmd)
