"""Offline smoke tests for narrow Termux layouts and both UI languages."""
import os
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from textual.widgets import Button, TabbedContent, Static
from nyxor.ui.app import NyxorApp


DEMO = {
    "mode": "drops", "account": "Demo account", "game": "Rust", "channel": "SharedStreamer",
    "message": "HLS активний; пакет прийнято Twitch", "drop": "Neon Crate — 45/60 хв",
    "points": "12 450", "points_session": "+320", "points_bonus": "—", "success": True,
    "queue": "▶ Rust  • Warframe", "_telemetry": {"uptime_seconds": 3720},
    "active_drops": [
        {"campaign_id": "a", "campaign": "Rust · Community Drops", "drop_id": "a1", "drop": "Neon Crate", "current": 45, "required": 60},
        {"campaign_id": "b", "campaign": "Rust · Creator Weekend", "drop_id": "b1", "drop": "Nightfall Hoodie", "current": 45, "required": 120},
    ],
}


class UiTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_and_wide_layouts_in_both_languages(self):
        for locale in ("uk", "en"):
            for width in (40, 80, 120):
                with self.subTest(locale=locale, width=width), ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, {"NYXOR_LANG": locale, "TERM": "xterm-256color", "COLORTERM": "truecolor"}))
                    os.environ.pop("NO_COLOR", None)
                    stack.enter_context(patch("nyxor.ui.settings.save_settings"))
                    stack.enter_context(patch("nyxor.ui.dashboard.read_state", return_value=DEMO.copy()))
                    stack.enter_context(patch("nyxor.ui.dashboard.process_running", return_value=True))
                    app = NyxorApp()
                    async with app.run_test(size=(width, 44)) as pilot:
                        await pilot.pause()
                        self.assertIn("SharedStreamer", str(app.query_one("#hero-card", Static).render()))
                        self.assertIn("Nightfall Hoodie", str(app.query_one("#campaigns-card", Static).render()))
                        self.assertFalse(app.query_one("#drop-card").display)
                        self.assertTrue(app.query_one("#start-nyxor", Button).disabled)
                        for name in ("start-nyxor", "stop-nyxor", "restart-nyxor"):
                            region = app.query_one("#" + name).region
                            self.assertGreater(region.width, 0)
                            self.assertLessEqual(region.right, width)
                            self.assertLessEqual(region.bottom, 44)
                        output = os.environ.get("NYXOR_PREVIEW_DIR")
                        if output and locale == "uk":
                            Path(output).mkdir(parents=True, exist_ok=True)
                            app.save_screenshot(f"nyxor-{width}.svg", path=output)
                            svg = Path(output) / f"nyxor-{width}.svg"
                            svg.write_text(svg.read_text(encoding="utf-8").replace(
                                "font-family: Fira Code, monospace;", "font-family: Consolas, monospace;"
                            ), encoding="utf-8")
                        for pane in ("queue-pane", "streamers-pane", "history-pane", "logs-pane", "settings-pane", "dashboard"):
                            app.query_one(TabbedContent).active = pane
                            await pilot.pause()
                        app.refresh_campaigns_card({"mode": "points"})
                        app.refresh_drop_card({"mode": "points", "points_balance_value": 50,
                                               "points_goal_title": "Reward", "points_goal_cost": 100})
                        self.assertFalse(app.query_one("#campaigns-card").display)
                        self.assertTrue(app.query_one("#drop-card").display)
                        self.assertIn("Reward", str(app.query_one("#drop-details", Static).render()))


if __name__ == "__main__":
    unittest.main()
