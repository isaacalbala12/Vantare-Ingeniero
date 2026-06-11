from __future__ import annotations

import logging

from src.config import settings

logger = logging.getLogger("vantare.ducking")


class DuckingController:
    """Baja volumen del endpoint default de Windows durante TTS.

    Usa pycaw (IAudioEndpointVolume) para escalar el master volume.
    Si pycaw no está disponible, es noop (fallback Tauri en Hito 4).
    """

    def __init__(self, level: float | None = None) -> None:
        self._level = level if level is not None else settings.AUDIO_DUCK_LEVEL
        self._pycaw_ok = False
        self._saved_scalar: float | None = None
        self._endpoint_volume = None
        self._init_pycaw()

    def _init_pycaw(self) -> None:
        try:
            from ctypes import POINTER, cast

            from comtypes import CLSCTX_ALL
            from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            self._endpoint_volume = cast(interface, POINTER(IAudioEndpointVolume))
            self._pycaw_ok = True
            logger.info("pycaw endpoint volume initialized")
        except Exception:
            logger.info("pycaw unavailable — ducking noop (instalar con 'pip install pycaw' para ducking real)")

    def duck_on(self) -> None:
        if not self._pycaw_ok or self._endpoint_volume is None:
            return
        try:
            if self._saved_scalar is None:
                self._saved_scalar = self._endpoint_volume.GetMasterVolumeLevelScalar()
            self._endpoint_volume.SetMasterVolumeLevelScalar(self._level, None)
            logger.debug("duck_on: volume %.2f -> %.2f", self._saved_scalar, self._level)
        except Exception as exc:
            logger.warning("duck_on failed: %s", exc)

    def duck_off(self) -> None:
        if not self._pycaw_ok or self._endpoint_volume is None or self._saved_scalar is None:
            return
        try:
            self._endpoint_volume.SetMasterVolumeLevelScalar(self._saved_scalar, None)
            logger.debug("duck_off: volume restored to %.2f", self._saved_scalar)
            self._saved_scalar = None
        except Exception as exc:
            logger.warning("duck_off failed: %s", exc)
