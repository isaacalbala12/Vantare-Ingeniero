"""Inspect Stepfun stream chunk fields."""
import asyncio
import json

from openai import AsyncOpenAI

from src.config import settings


async def main() -> None:
    client = AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=60,
    )
    stream = await client.chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {
                "role": "user",
                "content": "Responde en UNA frase corta de radio: tienes 4 vueltas de combustible.",
            }
        ],
        max_tokens=512,
        temperature=0.2,
        stream=True,
        extra_body={"thinking": {"type": "enabled"}},
    )

    content = ""
    reasoning = ""
    n = 0
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        c = getattr(delta, "content", None) or ""
        r = getattr(delta, "reasoning_content", None) or ""
        if c or r:
            n += 1
            if n <= 8 or c:
                cs = repr(c[:80]) if c else ""
                rs = repr(r[:80]) if r else ""
                print(f"#{n} content={cs} reasoning={rs}")
        content += c
        reasoning += r

    print("---")
    print("total chunks with data:", n)
    print("final content:", repr(content[:300]))
    print("final reasoning tail:", repr(reasoning[-300:]))


if __name__ == "__main__":
    asyncio.run(main())
