from __future__ import annotations

import subprocess
from pathlib import Path

from blabla.bins import resolve_ffmpeg, resolve_ffprobe
from blabla.config import Config

SILENCE_MAX_DB = -50.0


def audio_duration_seconds(path: Path, config: Config | None = None) -> float:
    ffprobe = resolve_ffprobe(config.ffprobe_bin if config else "")
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(proc.stdout.strip())


def measure_volume(path: Path, config: Config) -> tuple[float, float]:
    """Return (mean_db, max_db) via ffmpeg volumedetect."""
    ffmpeg = resolve_ffmpeg(config.ffmpeg_bin)
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    mean_db = max_db = -100.0
    for line in (proc.stderr or "").splitlines():
        if "mean_volume:" in line:
            mean_db = _parse_db(line, "mean_volume:", mean_db)
        if "max_volume:" in line:
            max_db = _parse_db(line, "max_volume:", max_db)
    return mean_db, max_db


def _parse_db(line: str, label: str, fallback: float) -> float:
    try:
        return float(line.split(label, 1)[1].split("dB", 1)[0].strip())
    except (IndexError, ValueError):
        return fallback


def silence_message(max_db: float, device: str) -> str | None:
    if max_db > SILENCE_MAX_DB:
        return None
    return (
        f"Recording looks silent (max {max_db:.1f} dB). "
        f"Current audio_device={device}. "
        "With the lid closed the built-in mic is off — use an external mic "
        "and confirm the input in System Settings → Sound → Input. "
        "List devices with: blabla devices"
    )


def convert_to_wav(src: Path, dest: Path, config: Config) -> None:
    """16 kHz mono PCM WAV, which is what whisper.cpp reads without its own ffmpeg."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = resolve_ffmpeg(config.ffmpeg_bin)
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(dest),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not dest.is_file():
        detail = (proc.stderr or proc.stdout or "ffmpeg failed").strip()
        raise RuntimeError(f"Could not convert audio for transcription:\n{detail}")
