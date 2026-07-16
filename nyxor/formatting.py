from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from nyxor.localization import plural, tr


ANSI_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
PROGRESS_RE = re.compile(
    r"(?P<current>\d+)\s*/\s*(?P<required>\d+)\s*(?:хв|min|m)?",
    re.IGNORECASE,
)
QUEUE_ITEM_RE = re.compile(
    r"(?P<symbol>[▶✓!•])\s+(?P<name>.*?)(?=(?:\s{2,}[▶✓!•]\s+)|$)"
)


def clean_terminal_text(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = text.replace("\r", "\n")
    return CONTROL_RE.sub("", text)

def tail_text(path: Path, max_bytes: int = 100_000, max_lines: int = 160) -> str:
    if not path.exists():
        return tr("status.journal_empty")

    try:
        size = path.stat().st_size
        with path.open("rb") as file:
            if size > max_bytes:
                file.seek(size - max_bytes)
            raw = file.read()
    except OSError as error:
        return tr("errors.journal_read", error=error)

    text = clean_terminal_text(raw.decode("utf-8", errors="replace"))
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-max_lines:]) or tr("status.journal_empty")

def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"

    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"

def age_text(timestamp: Any) -> str:
    dt = parse_iso(timestamp)
    if dt is None:
        return "—"

    now = datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()

    seconds = max(0, int((now - dt).total_seconds()))

    if seconds < 5:
        return tr("relative_time.just_now")
    if seconds < 60:
        time_text = plural("units.second", seconds)
    elif seconds < 3600:
        time_text = plural("units.minute", seconds // 60)
    else:
        time_text = plural("units.hour", seconds // 3600)

    return tr("relative_time.ago", time=time_text)

def parse_progress(drop_text: Any) -> tuple[int, int] | None:
    match = PROGRESS_RE.search(str(drop_text or ""))
    if match is None:
        return None

    current = int(match.group("current"))
    required = int(match.group("required"))

    if required <= 0:
        return None

    return current, required

def parse_queue_statuses(queue_text: Any, fallback: list[str]) -> list[tuple[str, str]]:
    text = str(queue_text or "").strip()
    matches = [
        (match.group("symbol"), match.group("name").strip())
        for match in QUEUE_ITEM_RE.finditer(text)
    ]

    if matches:
        return matches

    return [("•", game) for game in fallback]
