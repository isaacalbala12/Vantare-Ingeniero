"""Smoke test Stepfun / LLM response fields."""
import asyncio

from openai import AsyncOpenAI

from src.config import settings


async def try_call(label: str, extra_body=None, stream: bool = False) -> None:
    client = AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=30,
    )
    kwargs = {
        "model": settings.LLM_MODEL,
        "messages": [
            {
                "role": "user",
                "content": "Responde en UNA frase corta de radio: tienes 4 vueltas de combustible.",
            }
        ],
        "max_tokens": 512,
        "temperature": 0.2,
        "stream": stream,
    }
    if extra_body is not None:
        kwargs["extra_body"] = extra_body

    resp = await client.chat.completions.create(**kwargs)
    if stream:
        content = ""
        reasoning = ""
        async for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if getattr(delta, "content", None):
                content += delta.content
            if getattr(delta, "reasoning_content", None):
                reasoning += delta.reasoning_content
        print(
            label,
            "stream",
            "content=",
            repr(content[:200]),
            "reasoning=",
            repr(reasoning[:200]),
        )
        return

    msg = resp.choices[0].message
    rc = getattr(msg, "reasoning_content", None)
    print(label, "content=", repr(msg.content), "reasoning=", repr(rc[:200] if rc else rc))


async def main() -> None:
    print("model=", settings.LLM_MODEL, "base=", settings.LLM_BASE_URL)
    await try_call("no extra")
    await try_call("thinking off", {"thinking": {"type": "off"}})
    await try_call("thinking enabled", {"thinking": {"type": "enabled"}})
    await try_call("stream thinking enabled", {"thinking": {"type": "enabled"}}, stream=True)


if __name__ == "__main__":
    asyncio.run(main())
