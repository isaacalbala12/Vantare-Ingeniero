import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from src.services.asr_service import transcribe_wav

logger = logging.getLogger("vantare.transcribe")

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(audio: Annotated[UploadFile, File()]):
    """Transcribe pilot PTT WAV via faster-whisper (local ASR)."""
    logger.info("Received audio for transcription: %s (%s)", audio.filename, audio.content_type)
    raw = await audio.read()
    text = await asyncio.to_thread(transcribe_wav, raw)
    if text:
        logger.info("ASR transcript: %r", text[:120])
    else:
        logger.info("ASR transcript empty (%d bytes)", len(raw))
    return {"text": text}
