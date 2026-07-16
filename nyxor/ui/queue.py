from __future__ import annotations

from textual.widgets import DataTable, Input

from nyxor.localization import tr
from nyxor.process_control import process_running
from nyxor.storage import load_queue, save_queue


class QueueMixin:
    def reload_queue(self, cursor_row: int | None = None) -> None:
            self.queue_games = load_queue()
            table = self.query_one("#queue-table", DataTable)
            table.clear()

            if not self.queue_games:
                table.add_row("—", tr("status.empty_queue"), tr("queue.add_below"), key="empty")
                return

            for index, game in enumerate(self.queue_games):
                status = f"🥇 {tr('status.first_priority')}" if index == 0 else tr("status.in_queue")
                table.add_row(str(index + 1), game, status, key=f"queue-{index}")

            target = cursor_row if cursor_row is not None else 0
            target = max(0, min(target, len(self.queue_games) - 1))
            table.move_cursor(row=target)

    def selected_queue_index(self) -> int | None:
            if not self.queue_games:
                return None

            row = int(self.query_one("#queue-table", DataTable).cursor_coordinate.row)

            if 0 <= row < len(self.queue_games):
                return row

            return None

    def queue_changed(self, message: str) -> None:
            self.refresh_runtime()

            if process_running():
                self.notify(
                    tr("queue.changed_restart", message=message),
                    title=tr("queue.changed"),
                    severity="warning",
                    timeout=7,
                )
            else:
                self.notify(message, title=tr("queue.saved"))

    def add_game(self) -> None:
            input_widget = self.query_one("#queue-game-input", Input)
            game = input_widget.value.strip()

            if not game:
                self.notify(tr("queue.enter_game"), severity="warning")
                input_widget.focus()
                return

            queue = load_queue()

            if game.casefold() in {item.casefold() for item in queue}:
                self.notify(tr("queue.already_exists"), severity="warning")
                return

            queue.append(game)
            save_queue(queue)
            input_widget.value = ""
            self.reload_queue(cursor_row=len(queue) - 1)
            self.queue_changed(tr("queue.added", game=game))

    def move_queue(self, direction: int) -> None:
            index = self.selected_queue_index()
            if index is None:
                return

            target = index + direction
            if target < 0 or target >= len(self.queue_games):
                return

            queue = list(self.queue_games)
            queue[index], queue[target] = queue[target], queue[index]
            save_queue(queue)
            self.reload_queue(cursor_row=target)
            self.queue_changed(tr("queue.order_updated"))

    def remove_queue_game(self) -> None:
            index = self.selected_queue_index()
            if index is None:
                return

            queue = list(self.queue_games)
            removed = queue.pop(index)
            save_queue(queue)
            self.reload_queue(cursor_row=max(0, index - 1))
            self.queue_changed(tr("queue.removed", game=removed))

    def action_queue_up(self) -> None:
            self.move_queue(-1)

    def action_queue_down(self) -> None:
            self.move_queue(1)

    def action_queue_remove(self) -> None:
            self.remove_queue_game()

    def on_input_submitted(self, event: Input.Submitted) -> None:
            if event.input.id == "queue-game-input":
                self.add_game()
