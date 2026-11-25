"""Local transcription engines."""

from __future__ import annotations

from blabla.backends.whisper_cpp import WhisperCppService
from blabla.config import Config
from blabla.transcription import TranscriptionService


def get_transcription_service(config: Config) -> TranscriptionService:
    if config.backend != "whisper":
        raise RuntimeError(
            f"Backend {config.backend!r} is not available. Set backend = \"whisper\"."
        )
    return WhisperCppService(config)
