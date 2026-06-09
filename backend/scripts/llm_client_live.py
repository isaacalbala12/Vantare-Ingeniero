"""Verify VLLMClient end-to-end against live Stepfun."""
import asyncio

from src.intelligence.llm_client import VLLMClient


async def main() -> None:
    client = VLLMClient()
    text = await client.complete_text(
        "Responde en UNA frase corta de radio: tienes 4 vueltas de combustible.",
        max_tokens=256,
    )
    print("complete_text:", repr(text))

    chunks: list[str] = []
    async for token in client.ask_streaming_text(
        "Responde en UNA frase corta de radio: tienes 4 vueltas de combustible."
    ):
        chunks.append(token)
    streamed = "".join(chunks)
    print("stream joined:", repr(streamed[:300]))


if __name__ == "__main__":
    asyncio.run(main())
