from __future__ import annotations

import asyncio
import json
import logging
import re
import shutil
import subprocess
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

# The Textual UI reads runtime/state.json and data/events.jsonl.
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
_last_device_poll = 0.0
_last_success_at: str | None = None
_packet_history: list[int] = []
_device_cache: dict[str, Any] = {
    "battery": None,
    "network": None,
}


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


def notifications_enabled() -> bool:
    return bool(load_settings().get("notifications_enabled", True))


def device_telemetry_enabled() -> bool:
    return bool(load_settings().get("device_telemetry", True))


def auto_restart_enabled() -> bool:
    return bool(load_settings().get("auto_restart", True))


def send_notification(title: str, content: str) -> None:
    if not notifications_enabled():
        return

    executable = shutil.which("termux-notification")
    if executable is None:
        return

    try:
        subprocess.run(
            [
                executable,
                "--id",
                "nyxor-termux",
                "--title",
                title,
                "--content",
                content,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_json_command(command: str, timeout: int = 5) -> dict[str, Any] | None:
    executable = shutil.which(command)
    if executable is None:
        return None

    try:
        result = subprocess.run(
            [executable],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

    return data if isinstance(data, dict) else None


def ping_ms() -> float | None:
    executable = shutil.which("ping")
    if executable is None:
        return None

    try:
        result = subprocess.run(
            [executable, "-c", "1", "-W", "2", "1.1.1.1"],
            capture_output=True,
            text=True,
            timeout=4,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    match = re.search(r"time[=<]\s*([\d.]+)\s*ms", result.stdout)
    return round(float(match.group(1)), 1) if match else None


def poll_device() -> None:
    global _last_device_poll, _device_cache

    now = time.monotonic()

    if now - _last_device_poll < 30:
        return

    _last_device_poll = now

    if not device_telemetry_enabled():
        _device_cache = {"battery": None, "network": None}
        return

    battery_raw = run_json_command("termux-battery-status")
    wifi_raw = run_json_command("termux-wifi-connectioninfo")

    battery = None
    if battery_raw:
        battery = {
            "percentage": battery_raw.get("percentage"),
            "status": battery_raw.get("status"),
            "temperature": battery_raw.get("temperature"),
            "health": battery_raw.get("health"),
        }

    network = {"ping_ms": ping_ms()}

    if wifi_raw:
        network.update(
            {
                "ssid": wifi_raw.get("ssid"),
                "ip": wifi_raw.get("ip"),
                "link_speed_mbps": wifi_raw.get("link_speed_mbps"),
                "rssi": wifi_raw.get("rssi"),
            }
        )

    _device_cache = {
        "battery": battery,
        "network": network,
    }


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
    poll_device()

    return {
        "session_started_at": SESSION_STARTED_AT,
        "uptime_seconds": int(time.monotonic() - SESSION_STARTED_MONOTONIC),
        "last_success_at": _last_success_at,
        "packet_history": list(_packet_history[-40:]),
        "wake_lock_requested": True,
        "viewers": state.get("viewers"),
        "battery": _device_cache.get("battery"),
        "network": _device_cache.get("network"),
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
        send_notification(f"🔄 {tr('notifications.game_switch')}", f"{_last_game} → {game}")

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
        send_notification(f"🎁 {tr('notifications.drop_received')}", f"{game or 'Twitch'}: {localize_runtime_message(claim)}")

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


def run_once() -> None:
    asyncio.run(core.main())


def main() -> None:
    attempt = 0
    update_stats(starts=1)
    send_notification("▶ NYXOR", "NYXOR запущено")

    while True:
        try:
            write_state(running=True, message=tr("notifications.started"))
            run_once()
            write_state(running=False, message=tr("events.finished"))
            return

        except KeyboardInterrupt:
            write_state(running=False, message=tr("events.stopped_by_user"))
            return

        except Exception as error:
            attempt += 1
            error_text = f"{type(error).__name__}: {error}"
            add_event("error", error_text)

            if should_stop_retrying(error) or not auto_restart_enabled():
                write_state(running=False, error=error_text)
                send_notification(f"❌ {tr('notifications.fatal_stop')}", localize_runtime_message(error_text)[:180])
                raise

            delay = min(30 * attempt, 300)
            update_stats(restarts=1)
            add_event(
                "restart",
                tr("events.restart_in", error=localize_runtime_message(error_text[:120]), time=plural("units.second", delay)),
            )
            send_notification(
                f"⚠ {tr('notifications.restarting')}",
                tr("events.restart_in", error=localize_runtime_message(error_text[:120]), time=plural("units.second", delay)),
            )

            for remaining in range(delay, 0, -1):
                write_state(
                    running=True,
                    error=error_text,
                    message=tr("events.restarting_in", time=plural("units.second", remaining)),
                    restart_in=remaining,
                )
                try:
                    time.sleep(1)
                except KeyboardInterrupt:
                    write_state(running=False, message=tr("events.stopped_by_user"))
                    return


def run_entrypoint() -> None:
    try:
        main()
    finally:
        current = load_json(STATE_PATH, {})
        meta = current.get("_meta") if isinstance(current, dict) else {}
        error = meta.get("error") if isinstance(meta, dict) else None
        message = meta.get("message") if isinstance(meta, dict) else None

        write_state(
            running=False,
            error=error,
            message=localize_runtime_message(message)
            or "NYXOR process finished",
        )
