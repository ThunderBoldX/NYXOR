from __future__ import annotations

from textual.widgets import Select, Switch

from nyxor.localization import current_locale, set_locale, tr
from nyxor.storage import load_settings, save_settings


class SettingsMixin:
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
            if setting_name is not None:
                settings[setting_name] = bool(event.value)
                save_settings(settings)
                self.notify(tr("settings.saved"))
                return

            nested_mapping = {
                "points-enabled-switch": ("channel_points", "enabled"),
                "points-bonus-switch": ("channel_points", "auto_claim_bonus"),
                "points-raids-switch": ("channel_points", "follow_raids"),
                "points-moments-switch": ("channel_points", "claim_moments"),
                "points-predictions-switch": (
                    "channel_points",
                    "predictions",
                    "enabled",
                ),
            }
            path = nested_mapping.get(event.switch.id)
            if path is None:
                return

            current: dict = settings
            for key in path[:-1]:
                child = current.get(key)
                if not isinstance(child, dict):
                    child = {}
                    current[key] = child
                current = child

            current[path[-1]] = bool(event.value)
            save_settings(settings)
            self.notify(tr("settings.saved_restart"))
