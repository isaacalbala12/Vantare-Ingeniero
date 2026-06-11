from __future__ import annotations

import logging

logger = logging.getLogger("vantare.ptt_pipeline")

MIN_PILOT_QUESTION_CHARS = 2


def normalize_pilot_question(text: str) -> str | None:
    """Valida pregunta PTT antes de LLM/tools."""
    question = (text or "").strip()
    if len(question) < MIN_PILOT_QUESTION_CHARS:
        logger.info("PTT ignorado: pregunta vacía o demasiado corta (%r)", text)
        return None
    return question
