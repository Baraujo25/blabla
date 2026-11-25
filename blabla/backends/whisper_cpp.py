from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

from blabla.audio import audio_duration_seconds, convert_to_wav
from blabla.bins import resolve_whisper_cli, resolve_whisper_server
from blabla.config import Config
from blabla.models import model_file, model_is_usable
from blabla.paths import (
    ensure_dirs,
    server_lock_path,
    server_log_path,
    server_state_path,
    work_dir,
)
from blabla.transcription import TranscriptionResult, whisper_language

log = logging.getLogger("blabla.whisper")

# whisper-server v1.9.6 ships a 600s socket timeout. setup.sh raises the
# pinned source to 3600s before building. Stay under that on the client.
_SERVER_DEADLINE_SEC = 3500.0


def encode_multipart(fields: dict[str, str], wav: bytes, boundary: str | None = None) -> tuple[str, bytes]:
    boundary = boundary or f"----blabla{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                f"{value}\r\n"
            ).encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
        + wav
        + b"\r\n"
    )
    chunks.append(f"--{boundary}--\r\n".encode())
    return boundary, b"".join(chunks)


def parse_inference_body(body: bytes, content_type: str = "") -> str:
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        return ""
    if "json" in content_type.lower() or text.startswith("{"):
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"whisper-server returned unreadable JSON: {text[:300]}") from exc
        if isinstance(payload, dict):
            if payload.get("error") and "text" not in payload:
                raise RuntimeError(str(payload["error"]))
            return str(payload.get("text", "")).strip()
    return text


def inference_timeout(duration_sec: float, config: Config) -> float:
    if config.transcribe_timeout_sec > 0:
        return min(_SERVER_DEADLINE_SEC, config.transcribe_timeout_sec)
    estimate = max(120.0, 30.0 + max(0.0, duration_sec) * 3.0)
    return min(_SERVER_DEADLINE_SEC, estimate)


class WhisperCppService:
    """Local whisper.cpp. The server keeps the model loaded between dictations."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        prompt: str,
        on_progress=None,
    ) -> TranscriptionResult:
        if self.config.whisper_mode == "cli":
            if on_progress:
                on_progress("Transcribing")
            return self._transcribe_cli(audio_path, language=language, prompt=prompt)
        if on_progress:
            on_progress("Loading model")
        init_seconds = self.ensure_server()
        if on_progress:
            on_progress("Transcribing")
        started = time.perf_counter()
        text = self._transcribe_server(audio_path, language=language, prompt=prompt)
        return TranscriptionResult(
            text=text,
            model_init_seconds=init_seconds,
            transcription_seconds=time.perf_counter() - started,
        )

    def ensure_server(self) -> float:
        """Return seconds spent loading the model. Zero when it is already resident."""
        import fcntl

        ensure_dirs()
        model = self._require_model()
        binary = resolve_whisper_server(self.config.whisper_server_bin)
        host = self.config.server_host
        port = self.config.server_port
        started = time.perf_counter()
        lock_handle = server_lock_path().open("a", encoding="utf-8")
        try:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            info = _read_server_state()
            if _server_matches(info, model, binary, host, port) and _health_ok(host, port):
                return 0.0
            if info and _pid_alive(int(info.get("pid", 0))):
                _terminate_pid(int(info["pid"]))
            if _port_open(host, port):
                raise RuntimeError(
                    f"{host}:{port} is already in use. Stop that program or set server_port "
                    "in the config file, then try again."
                )
            self._spawn_server(binary, model, host, port)
            self._wait_until_ready(host, port)
            return time.perf_counter() - started
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()

    def _transcribe_server(self, audio_path: Path, *, language: str, prompt: str) -> str:
        wav = self._wav_copy(audio_path)
        try:
            duration = _safe_duration(audio_path, self.config)
            timeout = inference_timeout(duration, self.config)
            if timeout >= _SERVER_DEADLINE_SEC - 1:
                log.warning(
                    "This recording may exceed the local server request limit. "
                    "If transcription fails, set whisper_mode = \"cli\"."
                )
            fields = {
                "response_format": "json",
                "temperature": "0.0",
                "temperature_inc": "0.2",
                "language": language,
                "no_timestamps": "true",
            }
            if prompt:
                fields["prompt"] = prompt
                fields["carry_initial_prompt"] = "true"
            boundary, body = encode_multipart(fields, wav.read_bytes())
            url = f"http://{self.config.server_host}:{self.config.server_port}/inference"
            request = urllib.request.Request(
                url,
                data=body,
                method="POST",
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = response.read()
                    content_type = response.headers.get("Content-Type", "")
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
                raise RuntimeError(
                    f"whisper-server failed ({exc.code}). {detail}\n{_log_tail()}"
                ) from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(
                    "Could not reach the local whisper server. "
                    f"{exc.reason}\n{_log_tail()}"
                ) from exc
            return parse_inference_body(payload, content_type)
        finally:
            wav.unlink(missing_ok=True)

    def _transcribe_cli(self, audio_path: Path, *, language: str, prompt: str) -> TranscriptionResult:
        binary = resolve_whisper_cli(self.config.whisper_cli_bin)
        model = self._require_model()
        wav = self._wav_copy(audio_path)
        out_base = work_dir() / f"whisper-cli-{os.getpid()}"
        out_txt = out_base.with_suffix(".txt")
        out_txt.unlink(missing_ok=True)
        started = time.perf_counter()
        command = [
            binary,
            "-m",
            str(model),
            "-f",
            str(wav),
            "-l",
            language,
            "-t",
            str(self.config.whisper_threads),
            "-nt",
            "-otxt",
            "-of",
            str(out_base),
        ]
        if prompt:
            command.extend(["--prompt", prompt, "--carry-initial-prompt"])
        if not self.config.use_gpu:
            command.append("-ng")
        try:
            proc = subprocess.run(command, capture_output=True, text=True)
            if proc.returncode != 0 or not out_txt.is_file():
                detail = (proc.stderr or "").strip()
                raise RuntimeError(f"whisper-cli failed ({proc.returncode}).\n{detail[-1500:]}")
            text = out_txt.read_text(encoding="utf-8", errors="replace")
            return TranscriptionResult(
                text=text,
                model_init_seconds=0.0,
                transcription_seconds=time.perf_counter() - started,
            )
        finally:
            wav.unlink(missing_ok=True)
            out_txt.unlink(missing_ok=True)

    def _wav_copy(self, audio_path: Path) -> Path:
        dest = work_dir() / f"dictation-{os.getpid()}.wav"
        convert_to_wav(audio_path, dest, self.config)
        return dest

    def _require_model(self) -> Path:
        path = model_file(self.config)
        if model_is_usable(path):
            return path
        raise RuntimeError(
            f"Whisper model not found at {path}. "
            "Download it once with: blabla download-model"
        )

    def _spawn_server(self, binary: str, model: Path, host: str, port: int) -> None:
        public = work_dir() / "whisper-public"
        public.mkdir(parents=True, exist_ok=True)
        command = [
            binary,
            "-m",
            str(model),
            "--host",
            host,
            "--port",
            str(port),
            "-t",
            str(self.config.whisper_threads),
            "-l",
            whisper_language(self.config.language),
            "-nt",
            "--public",
            str(public),
        ]
        if not self.config.use_gpu:
            command.append("-ng")
        log_handle = server_log_path().open("a", encoding="utf-8")
        log_handle.write(
            f"\n--- start {time.strftime('%Y-%m-%d %H:%M:%S')} "
            f"model={model.name} port={port} ---\n"
        )
        log_handle.flush()
        proc = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log_handle.close()
        _write_server_state(
            {
                "pid": proc.pid,
                "port": port,
                "host": host,
                "model": str(model),
                "bin": binary,
            }
        )
        log.info("Started whisper-server pid=%s port=%s", proc.pid, port)

    def _wait_until_ready(self, host: str, port: int) -> None:
        info = _read_server_state()
        pid = int(info.get("pid", 0)) if info else 0
        deadline = time.time() + self.config.model_load_timeout_sec
        while time.time() < deadline:
            if _health_ok(host, port):
                return
            if pid and not _pid_alive(pid):
                raise RuntimeError(
                    "whisper-server exited while loading the model.\n" + _log_tail()
                )
            time.sleep(0.25)
        raise RuntimeError(
            "Timed out waiting for the local model to load. "
            f"See {server_log_path()}\n" + _log_tail()
        )


def stop_whisper_server() -> str:
    info = _read_server_state()
    if not info:
        return "Local transcription server is not running."
    pid = int(info.get("pid", 0))
    if pid and _pid_alive(pid):
        _terminate_pid(pid)
    server_state_path().unlink(missing_ok=True)
    return "Stopped the local transcription server. The next dictation loads the model again."


def _server_matches(info: dict | None, model: Path, binary: str, host: str, port: int) -> bool:
    if not info:
        return False
    try:
        pid = int(info.get("pid", 0))
    except (TypeError, ValueError):
        return False
    return (
        _pid_alive(pid)
        and info.get("model") == str(model)
        and info.get("bin") == binary
        and info.get("host") == host
        and int(info.get("port", -1)) == port
    )


def _read_server_state() -> dict | None:
    path = server_state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_server_state(payload: dict) -> None:
    path = server_state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def _health_ok(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/health"
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            body = response.read()
            return response.status == 200 and b'"ok"' in body
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _port_open(host: str, port: int) -> bool:
    import socket

    probe = "127.0.0.1" if host == "localhost" else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((probe, port)) == 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _terminate_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(50):
        if not _pid_alive(pid):
            return
        time.sleep(0.1)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        return


def _log_tail(lines: int = 20) -> str:
    path = server_log_path()
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = "\n".join(content[-lines:])
    return f"Last lines from {path.name}:\n{tail}" if tail else ""


def _safe_duration(path: Path, config: Config) -> float:
    try:
        return audio_duration_seconds(path, config)
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0.0
