import logging

from fastapi import APIRouter, File, UploadFile

from src.services.asr_service import transcribe_wav

logger = logging.getLogger("vantare.transcribe")

router = APIRouter()


@router.post("/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcripción PTT vía faster-whisper (local, español)."""
    raw = await audio.read()
    logger.info(
        "Received audio for transcription: %s (%s, %d bytes)",
        audio.filename,
        audio.content_type,
        len(raw),
    )
    text = transcribe_wav(raw, language="es")
    if not text:
        logger.warning("ASR devolvió texto vacío para %d bytes", len(raw))
    return {"text": text}
