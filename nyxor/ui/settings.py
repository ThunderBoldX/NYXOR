from __future__ import annotations

import sys

from rich.markup import escape
from textual.widgets import Select, Static, Switch

from nyxor.localization import current_locale, set_locale, tr
from nyxor.paths import BASE_DIR, CORE_PATH, WORKER_PATH
from nyxor.storage import load_settings, save_settings


class SettingsMixin:
    def refresh_system_info(self) -> None:
            import shutil

            wake_status = (
                "[green]✓[/green]"
                if shutil.which("termux-wake-lock")
                else f"[yellow]{tr('health.not_found')}[/yellow]"
            )
            battery_status = (
                "[green]✓[/green]"
                if shutil.which("termux-battery-status")
                else f"[yellow]{tr('health.api_missing')}[/yellow]"
            )
            wifi_status = (
                "[green]✓[/green]"
                if shutil.which("termux-wifi-connectioninfo")
                else f"[yellow]{tr('health.api_missing')}[/yellow]"
            )

            info = (
                f"[bold #E8E3F5]{tr('headings.components')}[/bold #E8E3F5]\n\n"
                f"[yellow]{tr('labels.python')}:[/yellow] {escape(sys.version.split()[0])}\n"
                f"[yellow]{tr('labels.project')}:[/yellow] {escape(str(BASE_DIR))}\n"
                f"[yellow]nyxor_core.py:[/yellow] "
                f"{'[green]✓[/green]' if CORE_PATH.exists() else '[red]✕[/red]'}\n"
                f"[yellow]nyxor_worker.py:[/yellow] "
                f"{'[green]✓[/green]' if WORKER_PATH.exists() else '[red]✕[/red]'}\n"
                f"[yellow]termux-wake-lock:[/yellow] {wake_status}\n"
                f"[yellow]termux-battery-status:[/yellow] {battery_status}\n"
                f"[yellow]termux-wifi-connectioninfo:[/yellow] {wifi_status}\n\n"
                f"[dim]{tr('system.scroll_hint')}[/dim]"
            )

            self.query_one("#system-info", Static).update(info)

    def on_select_changed(self, event: Select.Changed) -> None:
            if event.select.id != "language-select":
                return

            selected = str(event.value)

            if selected not in {"uk", "en"}:
                return

            settings = load_settings()
            settings["language"] = selected
            save_settings(settings)
            set_locale(selected)

            self.notify(
                tr("settings.language_restart"),
                title=tr("settings.language"),
                timeout=8,
            )

    def on_switch_changed(self, event: Switch.Changed) -> None:
            settings = load_settings()

            mapping = {
                "notifications-switch": "notifications_enabled",
                "restart-switch": "auto_restart",
                "telemetry-switch": "device_telemetry",
            }

            setting_name = mapping.get(event.switch.id)
            if setting_name is None:
                return

            settings[setting_name] = bool(event.value)
            save_settings(settings)
            self.notify(tr("settings.saved"))
