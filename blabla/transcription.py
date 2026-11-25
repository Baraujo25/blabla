from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    model_init_seconds: float
    transcription_seconds: float


ProgressCallback = Callable[[str], None]


class TranscriptionService(Protocol):
    """One local engine. Another implementation can replace this later."""

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        prompt: str,
        on_progress: ProgressCallback | None = None,
    ) -> TranscriptionResult: ...


def whisper_language(code: str) -> str:
    """Map config language tags (en-US) to whisper.cpp codes (en)."""
    value = code.strip().lower().replace("_", "-")
    if value in {"", "auto"}:
        return "auto"
    primary = value.split("-", 1)[0]
    if not primary.isalpha() or not 2 <= len(primary) <= 8:
        raise ValueError(
            f"Unsupported language {code!r}. Use a code such as \"en\", \"es\", or \"auto\"."
        )
    return primary


def normalize_transcript(text: str) -> str:
    return " ".join(part.strip() for part in text.splitlines() if part.strip()).strip()
