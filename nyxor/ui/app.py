from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    RichLog,
    Select,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from nyxor.localization import current_locale, tr
from nyxor.paths import (
    HISTORY_PATH,
    LOG_PATH,
    ensure_directories,
)
from nyxor.process_control import cleanup_stale_pid, process_running
from nyxor.storage import load_settings
from nyxor.ui.dashboard import DashboardMixin
from nyxor.ui.history import HistoryMixin
from nyxor.ui.process import ProcessMixin
from nyxor.ui.queue import QueueMixin
from nyxor.ui.settings import SettingsMixin
from nyxor.ui.styles import NYXOR_CSS


BRAND_NAME = tr("app.name", default="NYXOR")
BRAND_TAGLINE = tr("app.tagline", default="grinds while you sleep")


class NyxorApp(
    DashboardMixin,
    QueueMixin,
    ProcessMixin,
    HistoryMixin,
    SettingsMixin,
    App,
):
    TITLE = BRAND_NAME
    SUB_TITLE = BRAND_TAGLINE
    CSS = NYXOR_CSS

    BINDINGS = [
        ("s", "start_nyxor", tr("actions.start")),
        ("x", "stop_nyxor", tr("actions.stop")),
        ("ctrl+r", "restart_nyxor", tr("actions.restart")),
        ("u", "queue_up", tr("actions.move_up")),
        ("j", "queue_down", tr("actions.move_down")),
        ("delete", "queue_remove", tr("actions.remove")),
        ("q", "quit", tr("actions.close_ui")),
    ]

    def __init__(self) -> None:
            super().__init__()
            ensure_directories()
            cleanup_stale_pid()

            self.queue_games: list[str] = []
            self._last_log_text = ""
            self._last_history_signature = ""
            self._last_events_signature = ""
            self._last_running = process_running()
            self._stop_requested = False

    def compose(self) -> ComposeResult:
            settings = load_settings()

            yield Header(show_clock=True)

            with TabbedContent(initial="dashboard"):
                with TabPane(f"🏠 {tr('tabs.home')}", id="dashboard"):
                    with VerticalScroll(id="dashboard-scroll"):
                        yield Static(tr("status.loading_nyxor"), id="hero-card", classes="card")

                        with Vertical(id="drop-card", classes="card"):
                            yield Static(f"🎁 {tr('headings.active_drop')}", id="drop-heading")
                            yield ProgressBar(
                                total=100,
                                show_eta=False,
                                id="drop-progress",
                            )
                            yield Static(tr("status.waiting_data"), id="drop-details")

                        yield Static(f"📋 {tr('headings.queue')}", id="queue-card", classes="card")
                        yield Static(f"📡 {tr('headings.system')}", id="health-card", classes="card")

                        with Vertical(id="stats-card", classes="card"):
                            yield Static(f"📊 {tr('headings.statistics')}", id="stats-content")
                            yield Sparkline([0], id="packet-sparkline")

                        with Vertical(id="events-card", classes="card"):
                            yield Static(f"[bold #E8E3F5]📝 {tr('headings.events')}[/bold #E8E3F5]")
                            yield RichLog(
                                id="live-events",
                                wrap=True,
                                highlight=True,
                                markup=True,
                            )

                        with Horizontal(id="dashboard-actions"):
                            yield Button(f"▶ {tr('actions.start')}", id="start-nyxor", variant="success")
                            yield Button(f"■ {tr('actions.stop')}", id="stop-nyxor", variant="error")
                            yield Button(f"↻ {tr('actions.restart')}", id="restart-nyxor", variant="warning")

                with TabPane(f"🎮 {tr('tabs.queue')}", id="queue-pane"):
                    yield DataTable(id="queue-table")
                    with Horizontal(id="queue-input-row"):
                        yield Input(
                            placeholder=tr("queue.game_placeholder"),
                            id="queue-game-input",
                        )
                        yield Button(f"＋ {tr('actions.add')}", id="queue-add", variant="primary")
                    with Horizontal(id="queue-actions"):
                        yield Button(f"↑ {tr('actions.move_up')}", id="queue-up")
                        yield Button(f"↓ {tr('actions.move_down')}", id="queue-down")
                        yield Button(f"✕ {tr('actions.remove')}", id="queue-remove", variant="error")

                with TabPane(f"🎁 {tr('tabs.history')}", id="history-pane"):
                    yield DataTable(id="history-table")
                    with Horizontal(id="history-actions"):
                        yield Button(tr("actions.refresh"), id="history-refresh")
                        yield Static("", classes="history-actions-spacer")
                        yield Button(
                            tr("actions.clear"),
                            id="history-clear",
                            variant="error",
                        )

                with TabPane(f"📜 {tr('tabs.journal')}", id="logs-pane"):
                    yield RichLog(
                        id="nyxor-log",
                        wrap=True,
                        highlight=True,
                        markup=False,
                    )
                    with Horizontal(id="journal-actions"):
                        yield Button(tr("actions.refresh"), id="logs-refresh")
                        yield Static("", classes="journal-actions-spacer")
                        yield Button(
                            tr("actions.clear"),
                            id="logs-clear",
                            variant="error",
                        )

                with TabPane(f"⚙ {tr('tabs.settings')}", id="settings-pane"):
                    with Horizontal(classes="settings-row"):
                        yield Label(tr("settings.language"))
                        yield Select(
                            [
                                (tr("settings.language_uk"), "uk"),
                                (tr("settings.language_en"), "en"),
                            ],
                            value=current_locale(),
                            allow_blank=False,
                            id="language-select",
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(tr("settings.android_notifications"))
                        yield Switch(
                            value=bool(settings.get("notifications_enabled", True)),
                            id="notifications-switch",
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(tr("settings.auto_restart"))
                        yield Switch(
                            value=bool(settings.get("auto_restart", True)),
                            id="restart-switch",
                        )

                    with Horizontal(classes="settings-row"):
                        yield Label(tr("settings.device_telemetry"))
                        yield Switch(
                            value=bool(settings.get("device_telemetry", True)),
                            id="telemetry-switch",
                        )

                    yield Static("", id="system-info")

            yield Footer()

    def on_mount(self) -> None:
            queue_table = self.query_one("#queue-table", DataTable)
            queue_table.cursor_type = "row"
            queue_table.zebra_stripes = True
            queue_table.add_columns(tr("table.number"), tr("table.game"), tr("table.status"))

            history_table = self.query_one("#history-table", DataTable)
            history_table.cursor_type = "row"
            history_table.zebra_stripes = True
            history_table.add_columns(tr("table.time"), tr("table.game"), tr("table.event"), tr("table.channel"))

            self.reload_queue()
            self.refresh_all()
            self.refresh_system_info()

            self.set_interval(1.0, self.refresh_runtime)
            self.set_interval(3.0, self.refresh_events)
            self.set_interval(4.0, self.refresh_logs)
            self.set_interval(5.0, self.refresh_history)

    def refresh_all(self) -> None:
            self.refresh_runtime()
            self.refresh_events()
            self.refresh_history()
            self.refresh_logs()

    def on_button_pressed(self, event: Button.Pressed) -> None:
            button_id = event.button.id

            if button_id == "start-nyxor":
                self.action_start_nyxor()
            elif button_id == "stop-nyxor":
                self.action_stop_nyxor()
            elif button_id == "restart-nyxor":
                self.action_restart_nyxor()
            elif button_id == "queue-add":
                self.add_game()
            elif button_id == "queue-up":
                self.action_queue_up()
            elif button_id == "queue-down":
                self.action_queue_down()
            elif button_id == "queue-remove":
                self.action_queue_remove()
            elif button_id == "logs-refresh":
                self._last_log_text = ""
                self.refresh_logs()
            elif button_id == "logs-clear":
                self.clear_file(LOG_PATH, tr("system.journal_name"))
                self._last_log_text = ""
                self.refresh_logs()
            elif button_id == "history-refresh":
                self._last_history_signature = ""
                self.refresh_history()
            elif button_id == "history-clear":
                self.clear_file(HISTORY_PATH, tr("system.history_name"))
                self._last_history_signature = ""
                self.refresh_history()
