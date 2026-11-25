from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from blabla.paths import config_path, data_dir, ensure_dirs, repo_root

REMOVED_BACKENDS = frozenset({"speech", "gcloud", "google", "gemini"})
LOCAL_BACKENDS = frozenset({"", "whisper", "whisper.cpp", "local"})
LEGACY_KEYS = (
    "gcloud_bin",
    "chunk_seconds",
    "insert_text",
    "restore_clipboard",
    "clipboard_restore_delay_sec",
)
LOG_LEVELS = frozenset({"debug", "info", "warning", "error"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})


@dataclass
class Config:
    configured_backend: str = "whisper"
    backend: str = "whisper"
    audio_device: str = "0"
    sample_rate: int = 16000
    keep_recordings: bool = True
    language: str = "en"
    model: str = "large-v3-turbo"
    model_dir: str = ""
    model_url: str = ""
    whisper_server_bin: str = ""
    whisper_cli_bin: str = ""
    whisper_mode: str = "server"
    server_host: str = "127.0.0.1"
    server_port: int = 8178
    whisper_threads: int = 4
    use_gpu: bool = True
    vocabulary_path: str = ""
    initial_prompt: str = ""
    prompt_max_chars: int = 800
    notify_preview: bool = True
    log_level: str = "info"
    log_transcripts: bool = False
    model_load_timeout_sec: float = 180.0
    transcribe_timeout_sec: float = 0.0
    ffmpeg_bin: str = ""
    ffprobe_bin: str = ""
    ignored_legacy: tuple[str, ...] = field(default_factory=tuple)

    @property
    def removed_backend(self) -> bool:
        return self.configured_backend in REMOVED_BACKENDS


def vocabulary_file(config: Config) -> Path:
    if config.vocabulary_path.strip():
        return Path(config.vocabulary_path).expanduser()
    return data_dir() / "vocabulary.json"


def _as_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("rb") as handle:
            loaded = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"Could not read {path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"{path} must be a TOML table")
    return loaded


def default_config_text() -> str:
    example = repo_root() / "config.example.toml"
    if example.is_file():
        return example.read_text(encoding="utf-8")
    raise RuntimeError("config.example.toml is missing from the BlaBla checkout")


def default_vocabulary_text() -> str:
    example = repo_root() / "vocabulary.example.json"
    if example.is_file():
        return example.read_text(encoding="utf-8")
    return "{}\n"


def ensure_user_files() -> Config:
    """Create the config and vocabulary files when they are absent."""
    ensure_dirs()
    path = config_path()
    if not path.exists():
        path.write_text(default_config_text(), encoding="utf-8")
    config = load_config()
    vocab = vocabulary_file(config)
    if not vocab.exists():
        vocab.parent.mkdir(parents=True, exist_ok=True)
        vocab.write_text(default_vocabulary_text(), encoding="utf-8")
    return config


def load_config() -> Config:
    ensure_dirs()
    path = config_path()
    raw = _load_toml(path)
    try:
        return _config_from_raw(raw)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc


def _config_from_raw(raw: dict[str, Any]) -> Config:
    configured = str(raw.get("backend", "whisper")).strip().lower()
    if configured in LOCAL_BACKENDS:
        backend = "whisper"
    elif configured in REMOVED_BACKENDS:
        backend = "whisper"
    else:
        raise ValueError(
            f"Unknown backend {configured!r}. Set backend = \"whisper\"."
        )

    if "language" in raw:
        language = str(raw["language"])
    elif "speech_language" in raw:
        language = str(raw["speech_language"])
    else:
        language = "en"

    mode = str(raw.get("whisper_mode", "server")).strip().lower()
    if mode not in {"server", "cli"}:
        raise ValueError('whisper_mode must be "server" or "cli"')

    host = str(raw.get("server_host", "127.0.0.1")).strip() or "127.0.0.1"
    if host not in LOOPBACK_HOSTS:
        raise ValueError(
            "server_host must be 127.0.0.1 or localhost so transcription stays on this Mac."
        )

    log_level = str(raw.get("log_level", "info")).strip().lower()
    if log_level not in LOG_LEVELS:
        raise ValueError("log_level must be debug, info, warning, or error")

    port = int(raw.get("server_port", 8178))
    if not 1 <= port <= 65535:
        raise ValueError("server_port must be between 1 and 65535")

    threads = int(raw.get("whisper_threads", 4))
    if threads < 1:
        raise ValueError("whisper_threads must be at least 1")

    sample_rate = int(raw.get("sample_rate", 16000))
    if sample_rate < 8000:
        raise ValueError("sample_rate must be at least 8000")

    prompt_max = int(raw.get("prompt_max_chars", 800))
    if prompt_max < 0:
        raise ValueError("prompt_max_chars must be 0 or greater")

    load_timeout = float(raw.get("model_load_timeout_sec", 180))
    request_timeout = float(raw.get("transcribe_timeout_sec", 0))
    if load_timeout <= 0 or request_timeout < 0:
        raise ValueError("timeouts must be non-negative, and model_load_timeout_sec must be > 0")

    ignored = tuple(key for key in LEGACY_KEYS if key in raw)
    return Config(
        configured_backend=configured or "whisper",
        backend=backend,
        audio_device=str(raw.get("audio_device", "0")),
        sample_rate=sample_rate,
        keep_recordings=_as_bool(raw.get("keep_recordings"), True),
        language=language.strip() or "en",
        model=str(raw.get("model", "large-v3-turbo")).strip() or "large-v3-turbo",
        model_dir=str(raw.get("model_dir", "") or ""),
        model_url=str(raw.get("model_url", "") or ""),
        whisper_server_bin=str(raw.get("whisper_server_bin", "") or ""),
        whisper_cli_bin=str(raw.get("whisper_cli_bin", "") or ""),
        whisper_mode=mode,
        server_host=host,
        server_port=port,
        whisper_threads=threads,
        use_gpu=_as_bool(raw.get("use_gpu"), True),
        vocabulary_path=str(raw.get("vocabulary_path", "") or ""),
        initial_prompt=str(raw.get("initial_prompt", "") or ""),
        prompt_max_chars=prompt_max,
        notify_preview=_as_bool(raw.get("notify_preview"), True),
        log_level=log_level,
        log_transcripts=_as_bool(raw.get("log_transcripts"), False),
        model_load_timeout_sec=load_timeout,
        transcribe_timeout_sec=request_timeout,
        ffmpeg_bin=str(raw.get("ffmpeg_bin", "") or ""),
        ffprobe_bin=str(raw.get("ffprobe_bin", "") or ""),
        ignored_legacy=ignored,
    )
