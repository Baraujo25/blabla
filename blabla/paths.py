from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Checkout that contains this package, unless BLABLA_ROOT is set."""
    override = os.environ.get("BLABLA_ROOT", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def data_dir() -> Path:
    """Runtime state: config, recordings, logs. Override with BLABLA_HOME."""
    override = os.environ.get("BLABLA_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".blabla"


def support_dir() -> Path:
    """Models and built engines. Override with BLABLA_SUPPORT_DIR."""
    override = os.environ.get("BLABLA_SUPPORT_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "Application Support" / "BlaBla"


def default_model_dir() -> Path:
    return support_dir() / "models"


def default_bin_dir() -> Path:
    return support_dir() / "bin"


def config_path() -> Path:
    return data_dir() / "config.toml"


def state_path() -> Path:
    return data_dir() / "state.json"


def pid_path() -> Path:
    return data_dir() / "recorder.pid"


def transcribe_pid_path() -> Path:
    return data_dir() / "transcribe.pid"


def recordings_dir() -> Path:
    return data_dir() / "recordings"


def current_audio() -> Path:
    return data_dir() / "current.flac"


def last_transcript_path() -> Path:
    return data_dir() / "last_transcript.txt"


def last_timings_path() -> Path:
    return data_dir() / "last_timings.json"


def log_path() -> Path:
    return data_dir() / "blabla.log"


def server_state_path() -> Path:
    return data_dir() / "whisper-server.json"


def server_log_path() -> Path:
    return data_dir() / "whisper-server.log"


def server_lock_path() -> Path:
    return data_dir() / "server.lock"


def work_dir() -> Path:
    return data_dir() / "tmp"


def helper_binary() -> Path:
    return (
        repo_root()
        / "helper"
        / "BlaBla.app"
        / "Contents"
        / "MacOS"
        / "BlaBlaBin"
    )


def ensure_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)
    recordings_dir().mkdir(parents=True, exist_ok=True)
    work_dir().mkdir(parents=True, exist_ok=True)
    support_dir().mkdir(parents=True, exist_ok=True)
    default_model_dir().mkdir(parents=True, exist_ok=True)
    default_bin_dir().mkdir(parents=True, exist_ok=True)
