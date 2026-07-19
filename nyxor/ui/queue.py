from __future__ import annotations

import asyncio
from textual.widgets import DataTable, Input

from nyxor.game_search import (
    GameCategory,
    GameSearchError,
    normalize_query,
    search_game_categories,
)
from nyxor.localization import tr
from nyxor.process_control import process_running
from nyxor.storage import load_queue, save_queue


SEARCH_DEBOUNCE_SECONDS = 0.35
SUGGESTION_LIMIT = 10


class QueueMixin:
    game_suggestions: list[GameCategory]
    _game_search_task: asyncio.Task[None] | None
    _game_add_task: asyncio.Task[None] | None

    def _ensure_game_search_state(self) -> None:
        if not hasattr(self, "game_suggestions"):
            self.game_suggestions = []
        if not hasattr(self, "_game_search_task"):
            self._game_search_task = None
        if not hasattr(self, "_game_add_task"):
            self._game_add_task = None

    def _suggestions_table(self) -> DataTable:
        return self.query_one("#game-suggestions", DataTable)

    def hide_game_suggestions(self) -> None:
        self._ensure_game_search_state()
        self.game_suggestions = []
        table = self._suggestions_table()
        table.clear()
        table.display = False

    def _show_game_search_message(self, message: str) -> None:
        self._ensure_game_search_state()
        self.game_suggestions = []
        table = self._suggestions_table()
        table.clear()
        table.add_row(message, key="game-search-message")
        table.display = True

    def _render_game_suggestions(self, categories: list[GameCategory]) -> None:
        self._ensure_game_search_state()
        self.game_suggestions = list(categories)
        table = self._suggestions_table()
        table.clear()

        if not categories:
            table.add_row(tr("queue.no_suggestions"), key="game-search-empty")
            table.display = True
            return

        for index, category in enumerate(categories):
            table.add_row(category.name, key=f"game-suggestion-{index}")

        table.display = True
        table.move_cursor(row=0)

    def _cancel_game_search(self) -> None:
        self._ensure_game_search_state()
        task = self._game_search_task
        if task is not None and not task.done():
            task.cancel()
        self._game_search_task = None

    def reload_queue(self, cursor_row: int | None = None) -> None:
        self.queue_games = load_queue()
        table = self.query_one("#queue-table", DataTable)
        table.clear()

        if not self.queue_games:
            table.add_row(
                "—",
                tr("status.empty_queue"),
                tr("queue.add_below"),
                key="empty",
            )
            return

        for index, game in enumerate(self.queue_games):
            status = (
                f"🥇 {tr('status.first_priority')}"
                if index == 0
                else tr("status.in_queue")
            )
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

    def _save_official_game(self, game: str) -> None:
        official_name = normalize_query(game)
        if not official_name:
            return

        queue = load_queue()
        if official_name.casefold() in {item.casefold() for item in queue}:
            self.notify(tr("queue.already_exists"), severity="warning")
            return

        self._cancel_game_search()
        queue.append(official_name)
        save_queue(queue)

        input_widget = self.query_one("#queue-game-input", Input)
        input_widget.value = ""
        self.hide_game_suggestions()
        self.reload_queue(cursor_row=len(queue) - 1)
        self.queue_changed(tr("queue.added", game=official_name))

    def _game_search_error_message(self, error: GameSearchError) -> str:
        key_by_code = {
            "auth_missing": "queue.search_auth_missing",
            "auth_invalid": "queue.search_auth_invalid",
            "rate_limited": "queue.search_rate_limited",
            "network": "queue.search_network_error",
            "twitch_error": "queue.search_twitch_error",
            "unknown": "queue.search_unknown_error",
        }
        return tr(key_by_code.get(error.code, "queue.search_unknown_error"))

    async def _search_games_after_delay(self, query: str) -> None:
        try:
            await asyncio.sleep(SEARCH_DEBOUNCE_SECONDS)
            input_widget = self.query_one("#queue-game-input", Input)
            if normalize_query(input_widget.value).casefold() != query.casefold():
                return

            self._show_game_search_message(tr("queue.searching"))
            categories = await search_game_categories(
                query,
                limit=SUGGESTION_LIMIT,
            )

            if normalize_query(input_widget.value).casefold() != query.casefold():
                return

            self._render_game_suggestions(categories)
        except asyncio.CancelledError:
            return
        except GameSearchError as error:
            self._show_game_search_message(self._game_search_error_message(error))
        finally:
            current = asyncio.current_task()
            if self._game_search_task is current:
                self._game_search_task = None

    def schedule_game_search(self, value: str) -> None:
        self._ensure_game_search_state()
        self._cancel_game_search()

        query = normalize_query(value)
        self.hide_game_suggestions()
        if len(query) < 2:
            return

        self._game_search_task = asyncio.create_task(
            self._search_games_after_delay(query)
        )

    async def _resolve_and_add_game(self, query: str) -> None:
        try:
            folded = query.casefold()
            exact = next(
                (
                    category
                    for category in self.game_suggestions
                    if category.name.casefold() == folded
                ),
                None,
            )

            if exact is not None:
                self._save_official_game(exact.name)
                return

            self._show_game_search_message(tr("queue.searching"))
            categories = await search_game_categories(query, limit=SUGGESTION_LIMIT)
            exact = next(
                (
                    category
                    for category in categories
                    if category.name.casefold() == folded
                ),
                None,
            )

            if exact is not None:
                self._save_official_game(exact.name)
                return

            self._render_game_suggestions(categories)
            if categories:
                self.notify(
                    tr("queue.choose_suggestion"),
                    severity="warning",
                    timeout=6,
                )
                self._suggestions_table().focus()
            else:
                self.notify(tr("queue.no_suggestions"), severity="warning")
        except asyncio.CancelledError:
            return
        except GameSearchError as error:
            message = self._game_search_error_message(error)
            self._show_game_search_message(message)
            self.notify(message, severity="error", timeout=7)
        finally:
            current = asyncio.current_task()
            if self._game_add_task is current:
                self._game_add_task = None

    def add_game(self) -> None:
        self._ensure_game_search_state()
        input_widget = self.query_one("#queue-game-input", Input)
        query = normalize_query(input_widget.value)

        if not query:
            self.notify(tr("queue.enter_game"), severity="warning")
            input_widget.focus()
            return

        if len(query) < 2:
            self.notify(tr("queue.enter_more_characters"), severity="warning")
            input_widget.focus()
            return

        task = self._game_add_task
        if task is not None and not task.done():
            task.cancel()

        self._game_add_task = asyncio.create_task(
            self._resolve_and_add_game(query)
        )

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

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "queue-game-input":
            self.schedule_game_search(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "queue-game-input":
            self.add_game()
        elif event.input.id == "streamer-login-input":
            self.add_streamer()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.control.id != "game-suggestions":
            return

        self._ensure_game_search_state()
        index = int(event.cursor_row)
        if not 0 <= index < len(self.game_suggestions):
            return

        self._save_official_game(self.game_suggestions[index].name)

