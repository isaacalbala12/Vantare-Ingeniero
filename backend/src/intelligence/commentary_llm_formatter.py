"""Formateo LLM batch para comentarios proactivos (fallback determinista)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Sequence, Tuple

logger = logging.getLogger("vantare.commentary_llm")

EventTuple = Tuple[str, str, str]


@dataclass
class ParsedCommentary:
    speak: bool
    text: str
    priority: str = "NORMAL"


def format_batch_deterministic(events: Sequence[EventTuple], tone: str = "") -> str:
    parts = [e[1] for e in events if e[1].strip()]
    body = " ".join(parts)
    if len(body) > 280:
        return body[:277] + "..."
    return body


def parse_llm_commentary_response(raw: str) -> ParsedCommentary:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        data = json.loads(match.group())
    return ParsedCommentary(
        speak=bool(data.get("speak", True)),
        text=str(data.get("text", "")).strip(),
        priority=str(data.get("priority", "NORMAL")).upper(),
    )


def build_commentary_prompt(events: Sequence[EventTuple], personality_tone: str) -> str:
    bullets = "\n".join(f"- [{eid}] {summary}" for eid, summary, _prio in events)
    return (
        "Eres ingeniero de pista en Le Mans Ultimate. Redacta UN mensaje de radio en español.\n"
        f"Tono: {personality_tone}\n"
        "Máximo 2 frases. Sin markdown. Responde SOLO JSON:\n"
        '{"speak": true, "text": "...", "priority": "NORMAL|LOW"}\n'
        f"Hechos:\n{bullets}"
    )


async def format_commentary_batch(
    events: Sequence[EventTuple],
    personality_tone: str,
    llm_complete: Optional[Callable[[str], Awaitable[str]]] = None,
    timeout_s: float = 2.0,
) -> str:
    if not events:
        return ""
    fallback = format_batch_deterministic(events, personality_tone)
    if llm_complete is None:
        return fallback
    prompt = build_commentary_prompt(events, personality_tone)
    try:
        raw = await asyncio.wait_for(llm_complete(prompt), timeout=timeout_s)
        parsed = parse_llm_commentary_response(raw)
        if parsed.speak and parsed.text:
            from src.intelligence.llm_speech_sanitize import sanitize_llm_speech

            text = sanitize_llm_speech(parsed.text)
            if not text:
                return fallback
            return text[:280] if len(text) <= 280 else text[:277] + "..."
    except Exception as exc:
        logger.warning("LLM commentary batch fallback: %s", exc)
    return fallback
