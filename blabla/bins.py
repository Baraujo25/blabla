from __future__ import annotations

import os
import shutil
from pathlib import Path

from blabla.paths import default_bin_dir, repo_root

# Directories that often hold ffmpeg when a menu-bar host launches with a tiny PATH.
# Each entry is added only when that directory exists on this Mac.
_EXTRA_PATHS = (
    "/opt/homebrew/bin",
    "/opt/homebrew/sbin",
    "/usr/local/bin",
)


def ensure_path() -> None:
    """Prepend common tool directories that are actually present."""
    parts = [part for part in os.environ.get("PATH", "").split(":") if part]
    for extra in reversed(_EXTRA_PATHS):
        if extra not in parts and Path(extra).is_dir():
            parts.insert(0, extra)
    os.environ["PATH"] = ":".join(parts)


def resolve_binary(name: str, *, env_var: str = "", configured: str = "") -> str:
    ensure_path()
    for candidate in (configured, os.environ.get(env_var, "")):
        candidate = (candidate or "").strip()
        if candidate and Path(candidate).expanduser().is_file():
            return str(Path(candidate).expanduser())

    found = shutil.which(name)
    if found:
        return found

    for directory in _EXTRA_PATHS:
        path = Path(directory) / name
        if path.is_file():
            return str(path)

    hint = env_var or f"{name.upper()}_BIN"
    raise RuntimeError(
        f"{name} was not found. Install it and make sure it is on PATH, "
        f"or set {hint} (environment) or the matching config path. "
        f"Current PATH={os.environ.get('PATH', '')}"
    )


def resolve_ffmpeg(configured: str = "") -> str:
    return resolve_binary("ffmpeg", env_var="FFMPEG_BIN", configured=configured)


def resolve_ffprobe(configured: str = "") -> str:
    return resolve_binary("ffprobe", env_var="FFPROBE_BIN", configured=configured)


def resolve_whisper_tool(name: str, *, env_var: str, configured: str = "") -> str:
    """Find a whisper.cpp binary shipped by setup, then a dev build, then PATH."""
    ensure_path()
    candidates: list[str] = []
    if configured.strip():
        candidates.append(configured.strip())
    env_value = os.environ.get(env_var, "").strip()
    if env_value:
        candidates.append(env_value)
    candidates.append(str(default_bin_dir() / name))
    candidates.append(str(repo_root() / ".tools" / "whisper.cpp" / "build" / "bin" / name))
    for candidate in candidates:
        path = Path(candidate).expanduser()
        if path.is_file():
            return str(path)

    found = shutil.which(name)
    if found:
        return found

    raise RuntimeError(
        f"{name} was not found. From the BlaBla checkout run: scripts/setup.sh "
        f"Or set {env_var} to the binary."
    )


def resolve_whisper_server(configured: str = "") -> str:
    return resolve_whisper_tool(
        "whisper-server", env_var="WHISPER_SERVER_BIN", configured=configured
    )


def resolve_whisper_cli(configured: str = "") -> str:
    return resolve_whisper_tool("whisper-cli", env_var="WHISPER_CLI_BIN", configured=configured)
