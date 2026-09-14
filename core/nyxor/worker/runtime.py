from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.console import Console

import nyxor_core as core
from nyxor.localization import localize_runtime_message, plural, tr


from nyxor.paths import (
    DATA_DIR,
    EVENTS_PATH,
    HISTORY_PATH,
    RUNTIME_DIR,
    SETTINGS_PATH,
    STATE_PATH,
    STATS_PATH,
    ensure_directories,
)

APP_NAME = "NYXOR"
APP_TAGLINE = "grinds while you sleep"

EVENTS_MAX_BYTES = 2_000_000
EVENTS_KEEP_LINES = 4_000


class _DiscardWriter:
    """A tiny file-like sink used by Rich in background-worker mode."""

    encoding = "utf-8"

    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        return None

    def isatty(self) -> bool:
        return False


ensure_directories()

# The Android runtime reads state and events from private app storage.
# Printing a full Rich table every 20 seconds only bloats nyxor.log.
core.console = Console(
    file=_DiscardWriter(),
    force_terminal=False,
    color_system=None,
    width=120,
)

_original_render_status = core.render_status

SESSION_STARTED_MONOTONIC = time.monotonic()
SESSION_STARTED_AT = datetime.now().astimezone().isoformat(timespec="seconds")

_last_state: dict[str, Any] = {}
_last_game = ""
_last_channel = ""
_last_claim = ""
_last_message = ""
_last_success_at: str | None = None
_packet_history: list[int] = []


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return default


def atomic_write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_settings() -> dict[str, Any]:
    data = load_json(SETTINGS_PATH, {})
    return data if isinstance(data, dict) else {}


def load_stats() -> dict[str, Any]:
    data = load_json(
        STATS_PATH,
        {
            "starts": 0,
            "restarts": 0,
            "successful_packets": 0,
            "failed_packets": 0,
            "switches": 0,
            "channel_switches": 0,
            "claims": 0,
        },
    )
    return data if isinstance(data, dict) else {}


def update_stats(**changes: int) -> dict[str, Any]:
    stats = load_stats()

    for key, amount in changes.items():
        stats[key] = int(stats.get(key) or 0) + int(amount)

    atomic_write_json(STATS_PATH, stats)
    return stats


def _trim_jsonl(
    path: Path,
    *,
    max_bytes: int,
    keep_lines: int,
) -> None:
    try:
        if not path.exists() or path.stat().st_size <= max_bytes:
            return

        lines = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        kept = lines[-keep_lines:]
        temporary = path.with_suffix(path.suffix + ".trim")

        temporary.write_text(
            ("\n".join(kept) + "\n") if kept else "",
            encoding="utf-8",
        )
        temporary.replace(path)
    except OSError:
        pass


def append_jsonl(path: Path, item: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")

    if path == EVENTS_PATH:
        _trim_jsonl(
            path,
            max_bytes=EVENTS_MAX_BYTES,
            keep_lines=EVENTS_KEEP_LINES,
        )


def add_event(event_type: str, message: str, **extra: Any) -> None:
    item = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "type": event_type,
        "message": message,
    }
    item.update(extra)
    append_jsonl(EVENTS_PATH, item)


class _EventLogHandler(logging.Handler):
    """Mirror useful NYXOR logger records into the structured Journal."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage().strip()
        except Exception:
            return

        if not message:
            return

        if record.levelno < logging.INFO:
            lowered = message.casefold()
            if not any(
                marker in lowered
                for marker in (
                    "error",
                    "failed",
                    "failure",
                    "помил",
                    "недоступ",
                )
            ):
                return

        if record.levelno >= logging.ERROR:
            event_type = "log_error"
        elif record.levelno >= logging.WARNING:
            event_type = "warning"
        else:
            event_type = "event"

        add_event(
            event_type,
            message[:700],
            source=record.name,
            level=record.levelname,
        )


def configure_event_logging() -> None:
    logger = logging.getLogger("NYXOR")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not any(
        isinstance(handler, _EventLogHandler)
        for handler in logger.handlers
    ):
        logger.addHandler(_EventLogHandler())


configure_event_logging()
















def meaningful_claim(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"", "-", "—", "None", "0"}:
        return ""
    return text


def append_history(state: dict[str, Any], claim: str) -> None:
    item = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "game": state.get("game"),
        "channel": state.get("channel"),
        "drop": state.get("drop") or state.get("progress"),
        "claim": claim,
    }
    append_jsonl(HISTORY_PATH, item)


def telemetry_payload(state: dict[str, Any]) -> dict[str, Any]:

    return {
        "session_started_at": SESSION_STARTED_AT,
        "uptime_seconds": int(time.monotonic() - SESSION_STARTED_MONOTONIC),
        "last_success_at": _last_success_at,
        "packet_history": list(_packet_history[-40:]),
        "viewers": state.get("viewers"),
    }


def write_state(
    state: dict[str, Any] | None = None,
    *,
    running: bool,
    error: str | None = None,
    message: str | None = None,
    restart_in: int | None = None,
) -> None:
    global _last_state

    if state is not None:
        _last_state = dict(state)

    output = dict(_last_state)
    output["_meta"] = {
        "running": running,
        "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "error": error,
        "message": message,
        "restart_in": restart_in,
        "started_at": SESSION_STARTED_AT,
    }
    output["_telemetry"] = telemetry_payload(output)
    output["_stats"] = load_stats()

    atomic_write_json(STATE_PATH, output)


def patched_render_status(state: dict[str, Any]):
    global _last_game, _last_channel, _last_claim
    global _last_message, _last_success_at, _packet_history

    game = str(state.get("game") or "").strip()
    channel = str(state.get("channel") or "").strip()
    claim = meaningful_claim(state.get("claim"))
    message = localize_runtime_message(state.get("message") or "").strip()

    if state.get("success"):
        now_iso = datetime.now().astimezone().isoformat(timespec="seconds")

        if state.get("cycles") != _last_state.get("cycles"):
            _last_success_at = now_iso
            _packet_history.append(1)
            update_stats(successful_packets=1)
            add_event(
                "packet",
                tr("events.packet_ok", status=state.get("http_status") or 204),
                game=game,
                channel=channel,
                mode=state.get("mode"),
                http_status=state.get("http_status") or 204,
                hls_http_status=state.get("player_http_status"),
                player=state.get("player"),
                points=state.get("points"),
                points_session=state.get("points_session"),
            )

    elif state.get("http_status") and state.get("cycles") != _last_state.get("cycles"):
        _packet_history.append(0)
        update_stats(failed_packets=1)
        add_event(
            "packet_error",
            tr("events.packet_error", status=state.get("http_status")),
            game=game,
            channel=channel,
            mode=state.get("mode"),
            http_status=state.get("http_status") or 0,
            hls_http_status=state.get("player_http_status"),
            player=state.get("player"),
            points=state.get("points"),
            points_session=state.get("points_session"),
        )

    if _last_game and game and game != "—" and game != _last_game:
        update_stats(switches=1)
        add_event(
            "switch_game",
            f"{_last_game} → {game}",
            game=game,
            channel=channel,
        )

    if (
        _last_channel
        and channel
        and channel != "—"
        and channel != _last_channel
        and game == _last_game
    ):
        update_stats(channel_switches=1)
        add_event(
            "switch_channel",
            f"{_last_channel} → {channel}",
            game=game,
            channel=channel,
        )

    if claim and claim != _last_claim:
        append_history(state, claim)
        update_stats(claims=1)
        add_event(
            "claim",
            f"{game or 'Twitch'}: {claim}",
            game=game,
            channel=channel,
        )

    points_bonus = str(state.get("points_bonus") or "").strip()
    if points_bonus and any(
        marker in points_bonus.casefold()
        for marker in ("помил", "error", "failed")
    ):
        previous_points_bonus = str(
            _last_state.get("points_bonus") or ""
        ).strip()

        if points_bonus != previous_points_bonus:
            add_event(
                "points_error",
                points_bonus,
                game=game,
                channel=channel,
                source="Channel Points",
            )

    player_text = str(state.get("player") or "").strip()
    if player_text.startswith("✗"):
        previous_player = str(_last_state.get("player") or "").strip()

        if player_text != previous_player:
            add_event(
                "hls_error",
                player_text,
                game=game,
                channel=channel,
                hls_http_status=state.get("player_http_status"),
                source="HLS",
            )

    if (
        message
        and message != _last_message
        and any(word in message.lower() for word in ("помил", "недоступ", "немає", "чекаю"))
    ):
        add_event(
            "idle" if "чекаю" in message.lower() or "немає" in message.lower() else "error",
            message,
            game=game,
            channel=channel,
        )

    if game and game != "—":
        _last_game = game

    if channel and channel != "—":
        _last_channel = channel

    if claim:
        _last_claim = claim

    if message:
        _last_message = message

    write_state(state, running=True)
    return _original_render_status(state)


core.render_status = patched_render_status


def should_stop_retrying(error: Exception) -> bool:
    text = str(error).lower()
    fatal_markers = (
        "токен twitch недійсний",
        "auth-token",
        "cookies.jar",
        "авторизац",
        "unauthorized",
        "oauth",
    )
    return any(marker in text for marker in fatal_markers)






