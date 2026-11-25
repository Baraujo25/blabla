from __future__ import annotations

import logging
import os
import signal
import subprocess
import time

from blabla.bins import resolve_ffmpeg
from blabla.config import Config
from blabla.paths import config_path, current_audio, ensure_dirs, log_path, pid_path

log = logging.getLogger("blabla.recorder")


def list_audio_devices(config: Config | None = None) -> str:
    """Return a clean list of AVFoundation audio input devices."""
    ffmpeg = resolve_ffmpeg(config.ffmpeg_bin if config else "")
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        capture_output=True,
        text=True,
    )
    raw = proc.stderr or proc.stdout or ""
    lines = raw.splitlines()

    audio_section = False
    devices: list[tuple[str, str]] = []
    for line in lines:
        if "AVFoundation audio devices" in line:
            audio_section = True
            continue
        if "AVFoundation video devices" in line:
            audio_section = False
            continue
        if not audio_section:
            continue
        if "] [" in line and "]" in line.rsplit("[", 1)[-1]:
            try:
                after = line.rsplit("] [", 1)[-1]
                idx, name = after.split("]", 1)
                devices.append((idx.strip(), name.strip()))
            except ValueError:
                continue

    if not devices:
        return "No audio devices found.\nRaw ffmpeg output:\n" + raw

    out = [f"Audio devices (set audio_device in {config_path()}):\n"]
    for idx, name in devices:
        out.append(f"  {idx}  {name}")
    out.append('\nExample: audio_device = "1"')
    out.append("Note: the ffmpeg I/O error at the end of a raw device listing is normal.")
    return "\n".join(out)


def is_recording() -> bool:
    path = pid_path()
    if not path.exists():
        return False
    try:
        pid = int(path.read_text().strip())
    except ValueError:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_recording(config: Config):
    ensure_dirs()
    if is_recording():
        raise RuntimeError("Already recording")

    audio = current_audio()
    if audio.exists():
        audio.unlink()

    ffmpeg = resolve_ffmpeg(config.ffmpeg_bin)
    device = f":{config.audio_device}"
    cmd = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "avfoundation",
        "-i",
        device,
        "-ac",
        "1",
        "-ar",
        str(config.sample_rate),
        "-sample_fmt",
        "s16",
        "-c:a",
        "flac",
        str(audio),
    ]

    log_file = log_path().open("a", encoding="utf-8")
    log_file.write(
        f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"device={device} ffmpeg={ffmpeg} ---\n"
    )
    log_file.flush()

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=log_file,
        stderr=log_file,
        start_new_session=not bool(os.environ.get("BLABLA_ROOT")),
    )
    pid_path().write_text(str(proc.pid), encoding="utf-8")
    time.sleep(0.4)
    if proc.poll() is not None:
        pid_path().unlink(missing_ok=True)
        raise RuntimeError(
            "ffmpeg failed to start recording. "
            "Enable Microphone for BlaBla in "
            "System Settings → Privacy & Security → Microphone, then run: blabla devices"
        )
    return audio


def stop_recording():
    path = pid_path()
    if not path.exists():
        raise RuntimeError("Not recording")

    try:
        pid = int(path.read_text().strip())
    except ValueError as exc:
        path.unlink(missing_ok=True)
        raise RuntimeError("Corrupt recorder pid file") from exc

    try:
        os.kill(pid, signal.SIGINT)
    except ProcessLookupError:
        pass

    for _ in range(50):
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except OSError:
            break
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass

    path.unlink(missing_ok=True)
    audio = current_audio()
    if not audio.exists() or audio.stat().st_size < 100:
        raise RuntimeError("Recording file missing or empty")
    return audio
