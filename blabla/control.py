from __future__ import annotations

import fcntl
import os
import signal
import time
from contextlib import contextmanager
from typing import Iterator

from blabla.paths import data_dir, ensure_dirs, transcribe_pid_path


def write_transcribe_pid() -> None:
    transcribe_pid_path().write_text(str(os.getpid()), encoding="utf-8")


def clear_transcribe_pid() -> None:
    transcribe_pid_path().unlink(missing_ok=True)


@contextmanager
def exclusive_action() -> Iterator[bool]:
    """One start or stop at a time. A second click while this is held does nothing."""
    ensure_dirs()
    handle = (data_dir() / "action.lock").open("a+")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        yield False
        return
    try:
        yield True
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def cancel_transcription() -> bool:
    """Stop an in-flight transcription. The loaded model is left running."""
    path = transcribe_pid_path()
    if not path.exists():
        return False
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return False
    if pid == os.getpid():
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        path.unlink(missing_ok=True)
        return False
    except OSError:
        path.unlink(missing_ok=True)
        return False
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.05)
    else:
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    path.unlink(missing_ok=True)
    return True
