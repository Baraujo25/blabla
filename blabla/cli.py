from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from blabla.audio import measure_volume
from blabla.backends.whisper_cpp import stop_whisper_server
from blabla.bins import ensure_path, resolve_ffmpeg, resolve_ffprobe, resolve_whisper_cli, resolve_whisper_server
from blabla.config import Config, ensure_user_files, load_config
from blabla.control import cancel_transcription, clear_transcribe_pid, exclusive_action, write_transcribe_pid
from blabla.models import download_model, model_file, model_is_usable
from blabla.paths import (
    current_audio,
    ensure_dirs,
    helper_binary,
    last_timings_path,
    last_transcript_path,
    log_path,
    pid_path,
    recordings_dir,
)
from blabla.pipeline import transcribe_recording
from blabla.recorder import is_recording, list_audio_devices, start_recording, stop_recording
from blabla.state import read_state, set_status, widget_label
from blabla.timings import Timings
from blabla.util import copy_to_clipboard, mac_notify

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
log = logging.getLogger("blabla")


def _archive_recording(config: Config) -> Path | None:
    audio = current_audio()
    if not audio.exists():
        return None
    if not config.keep_recordings:
        return audio
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = recordings_dir() / f"{stamp}.flac"
    shutil.copy2(audio, dest)
    return dest


def _on_progress(message: str, config: Config) -> None:
    set_status("processing", message, keep_started_at=True, backend=config.backend, clear_timings=True)


def cmd_status() -> int:
    print(widget_label())
    return 0


def cmd_state() -> int:
    import json

    print(json.dumps(read_state().to_dict(), indent=2))
    return 0


def cmd_devices() -> int:
    print(list_audio_devices(load_config()))
    return 0


def cmd_doctor() -> int:
    config = load_config()
    ok = True
    print(f"backend: {config.backend} (local whisper.cpp)")
    if config.removed_backend:
        print(
            f"note: config still says backend = \"{config.configured_backend}\". "
            "That cloud backend is not used. Set backend = \"whisper\"."
        )
    if config.ignored_legacy:
        print("unused legacy settings: " + ", ".join(config.ignored_legacy))
    print(f"language: {config.language}")
    print(f"model: {config.model}")
    path = model_file(config)
    if model_is_usable(path):
        print(f"model file: {path}")
    else:
        print(f"model file: MISSING {path}", file=sys.stderr)
        print("Run: blabla download-model", file=sys.stderr)
        ok = False
    for label, resolver, configured in (
        ("whisper-server", resolve_whisper_server, config.whisper_server_bin),
        ("whisper-cli", resolve_whisper_cli, config.whisper_cli_bin),
        ("ffmpeg", resolve_ffmpeg, config.ffmpeg_bin),
        ("ffprobe", resolve_ffprobe, config.ffprobe_bin),
    ):
        try:
            print(f"{label}: {resolver(configured)}")
        except Exception as exc:
            print(f"{label}: ERROR — {exc}", file=sys.stderr)
            ok = False
    from blabla.backends.whisper_cpp import _health_ok

    if _health_ok(config.server_host, config.server_port):
        print(f"server: ready at http://{config.server_host}:{config.server_port}")
    else:
        print("server: stopped (the first dictation or `blabla warmup` loads the model)")
    print(f"audio_device: {config.audio_device}")
    print("delivery: clipboard")
    binary = helper_binary()
    print(f"helper: {binary if binary.is_file() else 'MISSING — run scripts/build-helper.sh'}")
    print(f"log: {log_path()}")
    return 0 if ok else 1


def cmd_download_model() -> int:
    try:
        download_model(load_config())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


def cmd_warmup() -> int:
    config = load_config()
    from blabla.backends import get_transcription_service

    service = get_transcription_service(config)
    started = time.perf_counter()
    try:
        init = service.ensure_server()  # type: ignore[attr-defined]
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if init == 0.0:
        print(f"Model already loaded ({time.perf_counter() - started:.2f}s to check).")
    else:
        print(f"Model loaded in {init:.2f}s. Later dictations reuse it.")
    return 0


def cmd_server_stop() -> int:
    print(stop_whisper_server())
    return 0


def cmd_start() -> int:
    with exclusive_action() as acquired:
        if not acquired:
            return 0
        if is_recording() or read_state().status == "recording":
            return 0
        config = load_config()
        try:
            start_recording(config)
        except Exception as exc:
            log.exception("Failed to start recording")
            set_status("error", "Start failed", error=str(exc), backend=config.backend, clear_target=True)
            mac_notify("BlaBla", f"Error: {exc}")
            print(str(exc), file=sys.stderr)
            return 1
        set_status(
            "recording",
            "Recording",
            started_at=time.time(),
            backend=config.backend,
            clear_timings=True,
        )
        print("recording")
    if os.environ.get("BLABLA_ROOT"):
        while is_recording():
            time.sleep(0.25)
    return 0


def cmd_stop() -> int:
    with exclusive_action() as acquired:
        if not acquired:
            return 0
        return _cmd_stop()


def _cmd_stop() -> int:
    config = load_config()
    state = read_state()
    started = state.started_at or time.time()
    try:
        audio_path = stop_recording() if is_recording() else current_audio()
        if not audio_path.exists():
            raise RuntimeError("No recording to stop")
    except Exception as exc:
        set_status("error", "Stop failed", error=str(exc), backend=config.backend)
        mac_notify("BlaBla", f"Error: {exc}")
        print(str(exc), file=sys.stderr)
        return 1

    stopped_at = time.perf_counter()
    duration = time.time() - started
    set_status(
        "processing",
        "Transcribing",
        started_at=started,
        duration_sec=duration,
        backend=config.backend,
        keep_started_at=True,
        clear_timings=True,
    )
    write_transcribe_pid()
    try:
        text, result, post_seconds = transcribe_recording(
            audio_path,
            config,
            on_progress=lambda message: _on_progress(message, config),
        )
        copy_to_clipboard(text)
        last_transcript_path().write_text(text, encoding="utf-8")
        _archive_recording(config)
        timings = Timings(
            recording_sec=duration,
            model_init_sec=result.model_init_seconds,
            transcription_sec=result.transcription_seconds,
            postprocess_sec=post_seconds,
            stop_to_insert_sec=time.perf_counter() - stopped_at,
        )
        _write_timings(timings)
        if config.whisper_mode == "cli":
            log.info("whisper_mode=cli, so model load is included in transcription_sec")
        log.info("%s chars=%d delivery=clipboard", timings.log_line(), len(text))
        set_status(
            "done",
            "Copied to clipboard",
            started_at=started,
            ended_at=time.time(),
            duration_sec=duration,
            chars=len(text),
            backend=config.backend,
            timings=timings.as_dict(),
            keep_started_at=True,
        )
        mac_notify("BlaBla", _notify_body(text, config))
        if sys.stdout.isatty():
            print(text)
        time.sleep(4)
        if read_state().status == "done":
            set_status("idle", "Ready", backend=config.backend, clear_target=True, clear_timings=True)
        return 0
    except KeyboardInterrupt:
        set_status("idle", "Cancelled", backend=config.backend, clear_target=True, clear_timings=True)
        print("Cancelled", file=sys.stderr)
        return 130
    except Exception as exc:
        log.exception("Transcription failed")
        _archive_recording(config)
        set_status(
            "error",
            "Transcription failed",
            started_at=started,
            duration_sec=duration,
            error=str(exc),
            backend=config.backend,
            keep_started_at=True,
        )
        mac_notify("BlaBla", f"Failed: {exc}")
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        clear_transcribe_pid()


def cmd_toggle() -> int:
    state = read_state()
    if is_recording() or state.status == "recording":
        return cmd_stop()
    if state.status == "processing":
        return 0
    return cmd_start()


def cmd_transcribe(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: blabla transcribe FILE", file=sys.stderr)
        return 2
    path = Path(argv[1]).expanduser()
    if not path.is_file():
        print(f"No audio file at {path}", file=sys.stderr)
        return 1
    config = load_config()
    stopped_at = time.perf_counter()
    try:
        text, result, post_seconds = transcribe_recording(path, config)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    from blabla.audio import audio_duration_seconds

    try:
        recorded = audio_duration_seconds(path, config)
    except Exception:
        recorded = 0.0
    timings = Timings(
        recording_sec=recorded,
        model_init_sec=result.model_init_seconds,
        transcription_sec=result.transcription_seconds,
        postprocess_sec=post_seconds,
        stop_to_insert_sec=time.perf_counter() - stopped_at,
    )
    _write_timings(timings)
    log.info("%s chars=%d", timings.log_line(), len(text))
    print(text)
    return 0


def cmd_test_mic() -> int:
    config = load_config()
    ffmpeg = resolve_ffmpeg(config.ffmpeg_bin)
    out = current_audio().with_name("mic-test.flac")
    ensure_dirs()
    device = f":{config.audio_device}"
    print(f"Recording 3s from audio_device={config.audio_device} ({device})…")
    proc = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "avfoundation",
            "-i",
            device,
            "-t",
            "3",
            "-ac",
            "1",
            "-ar",
            str(config.sample_rate),
            "-sample_fmt",
            "s16",
            "-c:a",
            "flac",
            str(out),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print((proc.stderr or proc.stdout or "ffmpeg failed").strip(), file=sys.stderr)
        print(
            "Enable Microphone for BlaBla (widget) or Terminal (this command) "
            "in System Settings → Privacy & Security → Microphone.",
            file=sys.stderr,
        )
        return 1
    mean_db, max_db = measure_volume(out, config)
    print(f"Saved: {out}")
    print(f"mean_volume: {mean_db:.1f} dB")
    print(f"max_volume:  {max_db:.1f} dB")
    if max_db <= -50:
        print(
            "SILENT — with the lid closed use an external microphone, confirm the input level "
            "in System Settings → Sound → Input, and grant Microphone access.",
            file=sys.stderr,
        )
        return 1
    print("OK — mic is picking up audio.")
    return 0


def cmd_reset() -> int:
    if is_recording():
        try:
            stop_recording()
        except Exception:
            pid_path().unlink(missing_ok=True)
    cancel_transcription()
    set_status("idle", "Ready", clear_target=True, clear_timings=True)
    print("reset")
    return 0


def _notify_body(text: str, config: Config) -> str:
    if not config.notify_preview:
        return f"Copied {len(text)} characters"
    return text if len(text) <= 80 else text[:77] + "…"


def _write_timings(timings: Timings) -> None:
    import json

    last_timings_path().write_text(json.dumps(timings.as_dict(), indent=2), encoding="utf-8")


def _warn_removed_backend(config: Config) -> None:
    if config.removed_backend:
        log.warning(
            "Configured backend %s has been removed. Using local whisper.cpp. "
            'Set backend = "whisper" in the config file.',
            config.configured_backend,
        )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(
            "Usage: blabla <status|state|devices|doctor|test-mic|start|stop|toggle|reset|"
            "download-model|warmup|server-stop|transcribe>",
            file=sys.stderr,
        )
        return 2

    cmd = argv[0]
    handlers = {
        "status": cmd_status,
        "state": cmd_state,
        "devices": cmd_devices,
        "doctor": cmd_doctor,
        "test-mic": cmd_test_mic,
        "start": cmd_start,
        "stop": cmd_stop,
        "toggle": cmd_toggle,
        "reset": cmd_reset,
        "download-model": cmd_download_model,
        "warmup": cmd_warmup,
        "server-stop": cmd_server_stop,
        "transcribe": lambda: cmd_transcribe(argv),
    }
    handler = handlers.get(cmd)
    if not handler:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        return 2

    ensure_dirs()
    ensure_path()
    try:
        config = ensure_user_files()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    logging.getLogger().setLevel(getattr(logging, config.log_level.upper()))
    if config.ffmpeg_bin:
        os.environ["FFMPEG_BIN"] = config.ffmpeg_bin
    if config.ffprobe_bin:
        os.environ["FFPROBE_BIN"] = config.ffprobe_bin
    if cmd in {"start", "stop", "toggle", "transcribe", "doctor", "warmup", "download-model"}:
        _warn_removed_backend(config)

    try:
        file_handler = logging.FileHandler(log_path())
        file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logging.getLogger().addHandler(file_handler)
    except OSError:
        pass

    return handler()


if __name__ == "__main__":
    raise SystemExit(main())
