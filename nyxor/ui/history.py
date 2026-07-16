from __future__ import annotations

import json
from pathlib import Path

from textual.widgets import DataTable, RichLog

from nyxor.formatting import tail_text
from nyxor.localization import localize_runtime_message, tr
from nyxor.paths import HISTORY_PATH, LOG_PATH
from nyxor.storage import load_jsonl


class HistoryMixin:
    def refresh_logs(self) -> None:
            text = tail_text(LOG_PATH)

            if text == self._last_log_text:
                return

            self._last_log_text = text
            log = self.query_one("#nyxor-log", RichLog)
            log.clear()

            for line in text.splitlines():
                log.write(localize_runtime_message(line))

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
                event = localize_runtime_message(item.get("claim") or item.get("event") or "—")
                channel = str(item.get("channel") or "—")
                table.add_row(timestamp, game, event, channel)

    def clear_file(self, path: Path, label: str) -> None:
            try:
                path.write_text("", encoding="utf-8")
            except OSError as error:
                self.notify(str(error), severity="error")
                return

            self.notify(tr("notifications.file_cleared", name=label))
