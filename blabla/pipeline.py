from __future__ import annotations

import logging
import time
from pathlib import Path

from blabla.audio import measure_volume, silence_message
from blabla.backends import get_transcription_service
from blabla.config import Config, vocabulary_file
from blabla.transcription import (
    TranscriptionResult,
    TranscriptionService,
    normalize_transcript,
    whisper_language,
)
from blabla.vocabulary import apply_vocabulary, build_prompt, load_vocabulary

log = logging.getLogger("blabla.pipeline")


def transcribe_recording(
    path: Path,
    config: Config,
    *,
    on_progress=None,
    service: TranscriptionService | None = None,
) -> tuple[str, TranscriptionResult, float]:
    """Transcribe one recording and apply deterministic vocabulary corrections."""
    mean_db, max_db = measure_volume(path, config)
    log.info("audio_level mean_db=%.1f max_db=%.1f", mean_db, max_db)
    silent = silence_message(max_db, config.audio_device)
    if silent:
        raise RuntimeError(silent)

    vocab = load_vocabulary(vocabulary_file(config))
    prompt = build_prompt(vocab, config.initial_prompt, config.prompt_max_chars)
    log.info("prompt_chars=%d replacements=%d", len(prompt), len(vocab.replacements))
    engine = service or get_transcription_service(config)
    result = engine.transcribe(
        path,
        language=whisper_language(config.language),
        prompt=prompt,
        on_progress=on_progress,
    )
    started = time.perf_counter()
    text = apply_vocabulary(normalize_transcript(result.text), vocab.replacements)
    post_seconds = time.perf_counter() - started
    log.info("transcript_chars=%d", len(text))
    if config.log_transcripts:
        log.info("transcript: %s", text)
    if not text:
        raise RuntimeError(
            "No speech detected. "
            f"Audio levels mean={mean_db:.1f} dB max={max_db:.1f} dB, language={config.language}."
        )
    return text, result, post_seconds
