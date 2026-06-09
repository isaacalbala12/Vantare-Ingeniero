"""Audit LLM pipeline paths for Stepfun."""
import asyncio

from src.intelligence.llm_client import VLLMClient
from src.intelligence.llm_speech_sanitize import sanitize_llm_speech
from src.intelligence import prompt_templates


async def audit() -> None:
    client = VLLMClient()
    print("=== config ===")
    print("model:", client._model)
    print("base:", client._base_url)
    print("stepfun:", client._is_stepfun())

    print("\n=== PTT turn1 ask_with_tools ===")
    tools = prompt_templates.get_pilot_ptt_tools(include_competitor_query=False)
    messages = [
        {"role": "system", "content": prompt_templates.PILOT_PTT_SYSTEM_PROMPT},
        {"role": "user", "content": "Piloto dice: cuantas vueltas de combustible me quedan?"},
    ]
    r = await client.ask_with_tools(messages, tools, max_tokens=256)
    print("tool_calls:", [(t.name, t.arguments) for t in r.tool_calls])
    print("content:", repr(r.content[:400]))
    print("sanitized:", repr(sanitize_llm_speech(r.content)))

    print("\n=== free-form stream (ask_streaming_text) ===")
    prompt = (
        "Responde en UNA frase corta estilo radio de ingeniero: "
        "cuantas vueltas de combustible tengo?"
    )
    parts: list[str] = []
    async for tok in client.ask_streaming_text(prompt):
        parts.append(tok)
    joined = "".join(parts)
    print("stream len:", len(joined))
    print("stream:", repr(joined[:350]))

    print("\n=== complete_text ===")
    ct = await client.complete_text(prompt, max_tokens=256)
    print("complete:", repr(ct[:350]))


if __name__ == "__main__":
    asyncio.run(audit())
