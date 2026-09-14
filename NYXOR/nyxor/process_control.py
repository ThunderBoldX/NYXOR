from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from nyxor.paths import PID_PATH, STATE_PATH
from nyxor.storage import load_json


def read_pid() -> int | None:
    try:
        return int(PID_PATH.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None

def process_running(pid: int | None = None) -> bool:
    pid = pid if pid is not None else read_pid()

    if not pid or pid <= 1:
        return False

    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False

    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
        fields = stat.split()
        if len(fields) >= 3 and fields[2] == "Z":
            return False
    except OSError:
        pass

    return True

def cleanup_stale_pid() -> None:
    pid = read_pid()
    if pid is not None and not process_running(pid):
        PID_PATH.unlink(missing_ok=True)

def read_state() -> dict[str, Any]:
    data = load_json(STATE_PATH, {})
    return data if isinstance(data, dict) else {}
