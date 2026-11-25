from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from blabla.config import Config
from blabla.paths import default_model_dir

HF_BASE = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main"
MIN_MODEL_BYTES = 1_000_000


def ggml_filename(model: str) -> str:
    name = Path(model.strip()).name
    if name.endswith(".bin"):
        return name
    return f"ggml-{name}.bin"


def default_model_url(model: str) -> str:
    return f"{HF_BASE}/{ggml_filename(model)}"


def model_file(config: Config) -> Path:
    raw = config.model.strip()
    expanded = Path(raw).expanduser()
    if expanded.is_absolute() or raw.startswith("."):
        return expanded
    directory = Path(config.model_dir).expanduser() if config.model_dir.strip() else default_model_dir()
    return directory / ggml_filename(raw)


def model_url(config: Config) -> str:
    if config.model_url.strip():
        return config.model_url.strip()
    return default_model_url(config.model)


def model_is_usable(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size < MIN_MODEL_BYTES:
        return False
    with path.open("rb") as handle:
        magic = handle.read(16)
    return not magic.startswith((b"<", b"{", b"PK"))


def download_model(config: Config) -> Path:
    """Download ggml weights once. A complete file is left in place."""
    dest = model_file(config)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if model_is_usable(dest):
        print(f"Model already present: {dest}")
        return dest

    url = model_url(config)
    partial = dest.with_suffix(dest.suffix + ".partial")
    print(f"Downloading {url}")
    print(f"Destination: {dest}")
    request = urllib.request.Request(url, headers={"User-Agent": "BlaBla/2.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            total = int(response.headers.get("Content-Length") or 0)
            written = 0
            next_report = 8 * 1024 * 1024
            with partial.open("wb") as handle:
                while True:
                    block = response.read(1024 * 256)
                    if not block:
                        break
                    handle.write(block)
                    written += len(block)
                    if written >= next_report:
                        if total:
                            print(f"  {written // (1024 * 1024)} / {total // (1024 * 1024)} MB")
                        else:
                            print(f"  {written // (1024 * 1024)} MB")
                        next_report += 8 * 1024 * 1024
    except urllib.error.URLError as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Could not download the model from {url}\n{exc}\n"
            "Check the network connection, or set model_url in the config file."
        ) from exc

    partial.replace(dest)
    if not model_is_usable(dest):
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"Downloaded file at {dest} does not look like a ggml model. "
            "The URL may be wrong. Set model or model_url and try again."
        )
    print(f"Saved {dest} ({dest.stat().st_size // (1024 * 1024)} MB)")
    return dest
