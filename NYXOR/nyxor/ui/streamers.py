from __future__ import annotations

import re

from textual.widgets import DataTable, Input

from nyxor.localization import tr
from nyxor.process_control import process_running
from nyxor.storage import load_streamers, normalize_streamer_login, save_streamers


_LOGIN_RE = re.compile(r"^[A-Za-z0-9_]{2,25}$")


class StreamersMixin:
    streamer_channels: list[str]

    def reload_streamers(self, cursor_row: int | None = None) -> None:
        self.streamer_channels = load_streamers()
        table = self.query_one("#streamers-table", DataTable)
        table.clear()

        if not self.streamer_channels:
            table.add_row(
                "—",
                tr("streamers.empty"),
                tr("streamers.add_below"),
                key="streamers-empty",
            )
            return

        for index, login in enumerate(self.streamer_channels):
            status = (
                f"🥇 {tr('status.first_priority')}"
                if index == 0
                else tr("streamers.in_list")
            )
            table.add_row(
                str(index + 1),
                login,
                status,
                key=f"streamer-{index}",
            )

        target = cursor_row if cursor_row is not None else 0
        target = max(0, min(target, len(self.streamer_channels) - 1))
        table.move_cursor(row=target)

    def selected_streamer_index(self) -> int | None:
        if not self.streamer_channels:
            return None

        row = int(
            self.query_one("#streamers-table", DataTable)
            .cursor_coordinate.row
        )

        if 0 <= row < len(self.streamer_channels):
            return row

        return None

    def streamers_changed(self, message: str) -> None:
        self.refresh_runtime()

        if process_running():
            self.notify(
                tr("streamers.changed_restart", message=message),
                title=tr("streamers.changed"),
                severity="warning",
                timeout=7,
            )
        else:
            self.notify(message, title=tr("streamers.saved"))

    def add_streamer(self) -> None:
        input_widget = self.query_one("#streamer-login-input", Input)
        login = normalize_streamer_login(input_widget.value)

        if not login:
            self.notify(tr("streamers.enter_login"), severity="warning")
            input_widget.focus()
            return

        if not _LOGIN_RE.fullmatch(login):
            self.notify(tr("streamers.invalid_login"), severity="warning")
            input_widget.focus()
            return

        streamers = load_streamers()

        if login.casefold() in {item.casefold() for item in streamers}:
            self.notify(tr("streamers.already_exists"), severity="warning")
            return

        streamers.append(login)
        save_streamers(streamers)
        input_widget.value = ""
        self.reload_streamers(cursor_row=len(streamers) - 1)
        self.streamers_changed(tr("streamers.added", login=login))

    def move_streamer(self, direction: int) -> None:
        index = self.selected_streamer_index()
        if index is None:
            return

        target = index + direction
        if target < 0 or target >= len(self.streamer_channels):
            return

        streamers = list(self.streamer_channels)
        streamers[index], streamers[target] = (
            streamers[target],
            streamers[index],
        )
        save_streamers(streamers)
        self.reload_streamers(cursor_row=target)
        self.streamers_changed(tr("streamers.order_updated"))

    def remove_streamer(self) -> None:
        index = self.selected_streamer_index()
        if index is None:
            return

        streamers = list(self.streamer_channels)
        removed = streamers.pop(index)
        save_streamers(streamers)
        self.reload_streamers(cursor_row=max(0, index - 1))
        self.streamers_changed(tr("streamers.removed", login=removed))

    def action_streamer_up(self) -> None:
        self.move_streamer(-1)

    def action_streamer_down(self) -> None:
        self.move_streamer(1)

    def action_streamer_remove(self) -> None:
        self.remove_streamer()
