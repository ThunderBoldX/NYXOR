from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.widgets import DataTable, RichLog

from nyxor.localization import localize_runtime_message, tr
from nyxor.paths import EVENTS_PATH, HISTORY_PATH
from nyxor.storage import load_jsonl


def _event_time(item: dict[str, Any]) -> str:
    timestamp = str(item.get("timestamp") or "")
    return timestamp[11:19] if len(timestamp) >= 19 else "--:--:--"


def _safe(value: Any, fallback: str = "—") -> str:
    text = str(value or "").strip()
    return text or fallback


def _packet_line(item: dict[str, Any]) -> str:
    timestamp = _event_time(item)
    event_type = str(item.get("type") or "")
    ok = event_type == "packet"

    icon = "[green]✓[/green]" if ok else "[red]✕[/red]"
    spade_status = _safe(item.get("http_status"), "0")
    hls_status = _safe(item.get("hls_http_status"), "")
    player = localize_runtime_message(item.get("player") or "")
    channel = escape(_safe(item.get("channel")))
    mode = escape(_safe(item.get("mode")))
    points = escape(_safe(item.get("points"), ""))

    if hls_status:
        hls_text = f"[cyan]HLS HTTP {escape(hls_status)}[/cyan]"
    elif player:
        hls_text = f"[cyan]{escape(player)}[/cyan]"
    else:
        hls_text = "[dim]HLS —[/dim]"

    spade_color = "green" if ok else "red"
    pieces = [
        f"[dim]{timestamp}[/dim]",
        icon,
        hls_text,
        f"[{spade_color}]Spade HTTP {escape(spade_status)}[/{spade_color}]",
        channel,
        mode,
    ]

    if points:
        pieces.append(f"[magenta]Points {points}[/magenta]")

    return "  ".join(pieces)


def _regular_event_line(item: dict[str, Any]) -> str:
    timestamp = _event_time(item)
    event_type = str(item.get("type") or "event")
    message = escape(
        localize_runtime_message(
            item.get("message") or event_type
        )
    )
    channel = escape(_safe(item.get("channel"), ""))
    source = escape(_safe(item.get("source"), ""))

    styles = {
        "claim": ("🎁", "green"),
        "switch_game": ("🔄", "cyan"),
        "switch_channel": ("📺", "cyan"),
        "raid": ("📡", "cyan"),
        "moment": ("🎬", "green"),
        "prediction": ("🔮", "magenta"),
        "warning": ("⚠", "yellow"),
        "error": ("✕", "red"),
        "log_error": ("✕", "red"),
        "restart": ("↻", "yellow"),
        "idle": ("⏸", "dim"),
        "hls_error": ("✕", "red"),
        "points_error": ("✕", "red"),
    }

    icon, color = styles.get(event_type, ("•", "white"))
    suffix: list[str] = []

    if channel:
        suffix.append(channel)
    if source and source != "—":
        suffix.append(source)

    extra = f"  [dim]{' • '.join(suffix)}[/dim]" if suffix else ""

    return (
        f"[dim]{timestamp}[/dim]  "
        f"[{color}]{icon} {message}[/{color}]"
        f"{extra}"
    )


class HistoryMixin:
    def refresh_logs(self) -> None:
            events = load_jsonl(EVENTS_PATH, 600)

            # Startup/shutdown records are intentionally hidden from Journal.
            visible = [
                item
                for item in events
                if str(item.get("type") or "") not in {"start", "stop"}
            ]

            signature = json.dumps(
                visible[-300:],
                ensure_ascii=False,
                sort_keys=True,
            )

            if signature == self._last_log_text:
                return

            self._last_log_text = signature
            log = self.query_one("#nyxor-log", RichLog)
            log.clear()

            if not visible:
                log.write(
                    f"[dim]{tr('status.events_empty', default='Подій ще немає. Запусти NYXOR.')}[/dim]"
                )
                return

            for item in visible[-300:]:
                event_type = str(item.get("type") or "")

                if event_type in {"packet", "packet_error"}:
                    log.write(_packet_line(item))
                else:
                    log.write(_regular_event_line(item))

            log.scroll_end(animate=False)

    def refresh_history(self) -> None:
            items = load_jsonl(HISTORY_PATH, 300)
            signature = json.dumps(items[-100:], ensure_ascii=False, sort_keys=True)

            if signature == self._last_history_signature:
                return

            self._last_history_signature = signature
            table = self.query_one("#history-table", DataTable)
            table.clear()

            if not items:
                table.add_row("—", "—", tr("status.history_empty"), "—")
                return

            for item in reversed(items[-100:]):
                timestamp = str(item.get("timestamp") or "—").replace("T", " ")[:19]
                game = str(item.get("game") or "—")
                event = localize_runtime_message(
                    item.get("claim") or item.get("event") or "—"
                )
                channel = str(item.get("channel") or "—")
                table.add_row(timestamp, game, event, channel)

    def clear_file(self, path: Path, label: str) -> None:
            try:
                path.write_text("", encoding="utf-8")
            except OSError as error:
                self.notify(str(error), severity="error")
                return

            self.notify(tr("notifications.file_cleared", name=label))
