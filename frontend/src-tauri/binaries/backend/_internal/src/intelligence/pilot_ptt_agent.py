from __future__ import annotations

import json
import logging

from src.intelligence.crewchief_events.commands import count_fast_intent_groups, match_fast_command, match_radio_check
from src.intelligence.pilot_tool_executor import PilotToolExecutor
from src.intelligence.ptt_pipeline import normalize_pilot_question
from src.intelligence import prompt_templates

logger = logging.getLogger("vantare.pilot_ptt_agent")

_executor = PilotToolExecutor()


async def _try_handle_competitor_question(engine, question: str) -> bool:
    competitors = engine.get_competitors_list()
    if not competitors:
        return False
    from src.intelligence.driver_names import get_driver_by_partial
    from src.intelligence.pilot_tool_executor import PilotToolExecutor

    comp_dicts = [c.model_dump() if hasattr(c, "model_dump") else c for c in competitors]
    matched = get_driver_by_partial(question, comp_dicts)
    if matched is None:
        for comp in comp_dicts:
            name = str(comp.get("driver_name") or "")
            if not name:
                continue
            surname = name.split()[-1]
            if len(surname) >= 3 and surname.lower() in question.lower():
                matched = comp
                break
    if matched is None:
        return False
    name = str(matched.get("driver_name") or "")
    await PilotToolExecutor().run(engine, "query_competitor", {"name": name})
    return True


async def handle_pilot_ptt(engine, question: str) -> None:
    """PTT: fast path → free-form directo → tools solo si intención mixta."""
    question = normalize_pilot_question(question)
    if not question:
        return

    await engine.cancel_current_llm()

    if match_radio_check(question):
        engine._emit_voice_response("Afirmativo, recepción clara.", fast_command=True)
        return

    intent_groups = count_fast_intent_groups(question)
    cmd = match_fast_command(question)

    if intent_groups == 1 and cmd is not None:
        if await engine._try_handle_fast_command(cmd):
            return
        if cmd.intent in ("fuel_status", "gap_status", "damage_status"):
            await engine._handle_free_form_question(question)
            return

    if intent_groups == 0:
        if await _try_handle_competitor_question(engine, question):
            return
        await engine._handle_free_form_question(question)
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
