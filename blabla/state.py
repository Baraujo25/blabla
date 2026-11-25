from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Any, Literal

from blabla.paths import ensure_dirs, state_path

Status = Literal["idle", "recording", "processing", "done", "error"]


@dataclass
class AppState:
    status: Status = "idle"
    message: str = "Ready"
    started_at: float | None = None
    ended_at: float | None = None
    duration_sec: float | None = None
    error: str | None = None
    chars: int | None = None
    backend: str | None = None
    target_app: str | None = None
    timings: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_state() -> AppState:
    ensure_dirs()
    path = state_path()
    if not path.exists():
        return AppState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppState(
            status=data.get("status", "idle"),
            message=data.get("message", "Ready"),
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            duration_sec=data.get("duration_sec"),
            error=data.get("error"),
            chars=data.get("chars"),
            backend=data.get("backend"),
            target_app=data.get("target_app"),
            timings=_timings(data.get("timings")),
        )
    except (json.JSONDecodeError, OSError, TypeError):
        return AppState(status="error", message="Bad state", error="state.json unreadable")


def write_state(state: AppState) -> None:
    ensure_dirs()
    path = state_path()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    tmp.replace(path)


def set_status(
    status: Status,
    message: str,
    *,
    started_at: float | None = None,
    ended_at: float | None = None,
    duration_sec: float | None = None,
    error: str | None = None,
    chars: int | None = None,
    backend: str | None = None,
    target_app: str | None = None,
    timings: dict[str, float] | None = None,
    keep_started_at: bool = False,
    clear_target: bool = False,
    clear_timings: bool = False,
) -> AppState:
    current = read_state()
    state = AppState(
        status=status,
        message=message,
        started_at=(
            started_at
            if started_at is not None
            else (current.started_at if keep_started_at else None)
        ),
        ended_at=ended_at,
        duration_sec=(
            duration_sec
            if duration_sec is not None
            else (current.duration_sec if keep_started_at else None)
        ),
        error=error,
        chars=chars if chars is not None else (current.chars if keep_started_at else None),
        backend=backend if backend is not None else (current.backend if keep_started_at else None),
        target_app=None if clear_target else (target_app if target_app is not None else current.target_app),
        timings=None if clear_timings else (timings if timings is not None else (current.timings if keep_started_at else None)),
    )
    write_state(state)
    return state


def format_elapsed(started_at: float | None) -> str:
    if not started_at:
        return "0:00"
    elapsed = max(0, int(time.time() - started_at))
    minutes, seconds = divmod(elapsed, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def widget_label(state: AppState | None = None) -> str:
    """Compact label for simple-bar."""
    state = state or read_state()
    if state.status == "recording":
        return f"REC {format_elapsed(state.started_at)}"
    if state.status == "processing":
        msg = state.message or ""
        if "/" in msg:
            tail = msg.rsplit(" ", 1)[-1]
            if "/" in tail:
                return f"… {tail}"
        return "…"
    if state.status == "done":
        chars = state.chars or 0
        return f"✓ {chars}"
    if state.status == "error":
        return "!"
    return "BlaBla"


def _timings(value: object) -> dict[str, float] | None:
    if not isinstance(value, dict):
        return None
    parsed: dict[str, float] = {}
    for key, item in value.items():
        try:
            parsed[str(key)] = float(item)
        except (TypeError, ValueError):
            return None
    return parsed
