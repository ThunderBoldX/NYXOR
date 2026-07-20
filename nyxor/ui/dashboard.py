from __future__ import annotations

import json

from datetime import datetime, timedelta
from typing import Any

from rich.markup import escape
from rich.text import Text
from textual.widgets import Button, ProgressBar, RichLog, Sparkline, Static

from nyxor.formatting import (
    age_text,
    format_duration,
    parse_progress,
    parse_iso,
    parse_queue_statuses,
)
from nyxor.localization import (
    localize_battery_status,
    localize_runtime_message,
    plural,
    tr,
)
from nyxor.paths import EVENTS_PATH, HISTORY_PATH, STATS_PATH
from nyxor.process_control import cleanup_stale_pid, process_running, read_state
from nyxor.storage import load_json, load_jsonl, load_queue

BRAND_NAME = tr("app.name", default="NYXOR")
BRAND_TAGLINE = tr("app.tagline", default="grinds while you sleep")


def _format_points(value: int) -> str:
    return f"{max(0, int(value)):,}".replace(",", " ")


def _state_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)

    try:
        return int(value)
    except (TypeError, ValueError):
        pass

    compact = str(value or "").replace(" ", "").replace(",", "")
    try:
        return int(compact)
    except ValueError:
        return 0


class DashboardMixin:
    def hero_markup(self, running: bool, state: dict[str, Any]) -> str:
            meta = state.get("_meta")
            meta = meta if isinstance(meta, dict) else {}

            telemetry = state.get("_telemetry")
            telemetry = telemetry if isinstance(telemetry, dict) else {}

            status = (
                f"[bold green]🟢 {tr('status.running')}[/bold green]"
                if running
                else f"[bold red]⚫ {tr('status.stopped')}[/bold red]"
            )

            account = escape(str(state.get("account") or "—"))
            raw_mode = str(state.get("mode") or "").strip()
            mode = escape(
                tr(f"modes.{raw_mode}", default=raw_mode or "—")
            )
            game = escape(str(state.get("game") or "—"))
            channel = escape(str(state.get("channel") or "—"))
            # NYXOR_CHANNEL_POINTS_DASHBOARD_V1
            points = escape(str(state.get("points") or "—"))
            points_session = escape(str(state.get("points_session") or "—"))
            points_bonus = escape(localize_runtime_message(state.get("points_bonus") or "—"))
            points_streak = escape(localize_runtime_message(state.get("points_streak") or "—"))
            points_moments = escape(str(state.get("points_moments") or "0"))
            points_raid = escape(localize_runtime_message(state.get("points_raid") or "—"))
            points_prediction = escape(
                localize_runtime_message(
                    state.get("points_prediction") or tr("common.disabled")
                )
            )
            points_pubsub = escape(localize_runtime_message(state.get("points_pubsub") or "—"))
            player = escape(localize_runtime_message(state.get("player") or "—"))
            viewers = escape(str(state.get("viewers") or telemetry.get("viewers") or "—"))

            raw_message = (
                meta.get("error")
                or state.get("message")
                or meta.get("message")
                or tr("status.waiting")
            )
            message = escape(localize_runtime_message(raw_message))

            uptime = format_duration(telemetry.get("uptime_seconds"))
            updated = age_text(meta.get("updated_at"))

            brand_width = 36
            brand_line = f"• {BRAND_NAME} •".center(brand_width)
            tagline_line = BRAND_TAGLINE.center(brand_width)

            return (
                f"[bold #E8E3F5]{brand_line}[/bold #E8E3F5]\n"
                f"[#B57BFF]{tagline_line}[/]\n"
                "[#7B2FFF]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]\n"
                f"[#B57BFF]{tr('labels.process')}:[/] {status}    "
                f"[#B57BFF]{tr('labels.uptime')}:[/] {uptime}\n"
                f"[#B57BFF]{tr('labels.account')}:[/] [bold]{account}[/bold]\n"
                f"[#B57BFF]{tr('labels.mode')}:[/] [bold]{mode}[/bold]\n"
                f"[#B57BFF]{tr('labels.game')}:[/] [bold #E8E3F5]{game}[/bold #E8E3F5]\n"
                f"[#B57BFF]{tr('labels.channel')}:[/] {channel}\n"
                f"[#B57BFF]Points:[/] [bold]{points}[/bold] "
                f"[dim]({points_session})[/dim]\n"
                f"[#B57BFF]{tr('labels.bonus')}:[/] {points_bonus}\n"
                f"[#B57BFF]{tr('labels.watch_streak')}:[/] {points_streak}\n"
                f"[#B57BFF]{tr('labels.moments')}:[/] {points_moments}\n"
                f"[#B57BFF]{tr('labels.raid')}:[/] {points_raid}\n"
                f"[#B57BFF]{tr('labels.prediction')}:[/] {points_prediction}\n"
                f"[#B57BFF]{tr('labels.pubsub')}:[/] {points_pubsub}\n"
                f"[#B57BFF]{tr('labels.player')}:[/] {player}\n"
                f"[#B57BFF]{tr('labels.viewers')}:[/] {viewers}\n"
                f"[#B57BFF]{tr('labels.status')}:[/] {message}\n"
                f"[dim]{tr('labels.updated')}: {updated}[/dim]"
            )

    def refresh_drop_card(self, state: dict[str, Any]) -> None:
            raw_drop_text = state.get("drop") or state.get("progress") or "—"
            drop_text = localize_runtime_message(raw_drop_text)
            progress = parse_progress(drop_text)

            heading = self.query_one("#drop-heading", Static)
            details = self.query_one("#drop-details", Static)
            bar = self.query_one("#drop-progress", ProgressBar)

            if str(state.get("mode") or "") == "points":
                balance = _state_int(
                    state.get("points_balance_value")
                    or state.get("points")
                )
                reward_title = str(
                    state.get("points_goal_title") or ""
                ).strip()
                reward_cost = _state_int(state.get("points_goal_cost"))

                heading.update(f"⭐ {tr('headings.channel_points')}")

                if reward_title and reward_cost > 0:
                    percent = max(
                        0.0,
                        min(100.0, balance / reward_cost * 100.0),
                    )
                    remaining = max(0, reward_cost - balance)
                    bar.update(total=100, progress=percent)

                    if remaining > 0:
                        footer = tr(
                            "drop.points_goal_remaining",
                            points=_format_points(remaining),
                        )
                    else:
                        footer = tr("drop.points_goal_ready")

                    details.update(
                        Text.from_markup(
                            f"[bold #E8E3F5]{escape(reward_title)}"
                            f"[/bold #E8E3F5]\n"
                            f"[#B57BFF]{_format_points(balance)}[/] "
                            f"[dim]/[/dim] "
                            f"[bold]{_format_points(reward_cost)} Points[/bold]\n"
                            f"[dim]{escape(footer)}[/dim]",
                            justify="left",
                        )
                    )
                else:
                    bar.update(total=100, progress=0)
                    details.update(
                        Text.from_markup(
                            f"[bold]{escape(drop_text)}[/bold]\n"
                            f"[dim]{tr('drop.points_goal_unavailable')}[/dim]",
                            justify="left",
                        )
                    )
                return

            if progress is None:
                bar.update(total=100, progress=0)
                heading.update(f"🎁 {tr('headings.active_drop')}")
                details.update(
                    f"[bold]{escape(drop_text)}[/bold]\n"
                    f"[dim]{tr('drop.progress_hint')}[/dim]"
                )
                return

            current, required = progress
            percent = max(0.0, min(100.0, current / required * 100.0))
            remaining = max(0, required - current)
            finish_at = datetime.now().astimezone() + timedelta(minutes=remaining)

            bar.update(total=100, progress=percent)
            heading.update(
                f"🎁 {tr('headings.active_drop')} — [bold]{percent:.0f}%[/bold]"
            )
            details.update(
                f"[bold]{escape(drop_text)}[/bold]\n"
                f"[yellow]{tr('labels.remaining')}:[/yellow] "
                f"{tr('drop.approximately', time=plural('units.minute', remaining))}\n"
                f"[yellow]{tr('labels.estimated_finish')}:[/yellow] "
                f"{tr('drop.finish_at', time=finish_at.strftime('%H:%M'))}"
            )

    def refresh_queue_card(self, state: dict[str, Any]) -> None:
            queue = load_queue()
            statuses = parse_queue_statuses(state.get("queue"), queue)

            labels = {
                "▶": f"[bold green]▶ {tr('status.farming')}[/bold green]",
                "✓": f"[green]✓ {tr('status.completed')}[/green]",
                "!": f"[red]🔒 {tr('status.not_linked')}[/red]",
                "•": f"[yellow]• {tr('status.queued')}[/yellow]",
            }

            lines = [f"[bold #E8E3F5]✦ {tr('headings.queue')}[/bold #E8E3F5]"]

            if not statuses:
                lines.append(f"[yellow]{tr('status.empty_queue')}[/yellow]")
            else:
                for index, (symbol, game) in enumerate(statuses[:8], start=1):
                    lines.append(
                        f"{index:>2}. [bold]{escape(game)}[/bold]  {labels.get(symbol, symbol)}"
                    )

                if len(statuses) > 8:
                    count = len(statuses) - 8
                    lines.append(
                        f"[dim]{tr('queue.more_games', count=count, games=plural('units.game', count))}[/dim]"
                    )

            self.query_one("#queue-card", Static).update("\n".join(lines))

    def refresh_health_card(self, running: bool, state: dict[str, Any]) -> None:
            meta = state.get("_meta")
            meta = meta if isinstance(meta, dict) else {}

            telemetry = state.get("_telemetry")
            telemetry = telemetry if isinstance(telemetry, dict) else {}

            success = bool(state.get("success"))
            http_status = state.get("http_status")
            last_success = age_text(telemetry.get("last_success_at"))

            error_text = str(meta.get("error") or state.get("message") or "")
            error_lower = error_text.lower()
            gql_ok = not any(
                marker in error_lower
                for marker in ("gql", "graphql", "persistedquery", "недоступ")
            )

            battery = telemetry.get("battery")
            battery_text = "—"

            if isinstance(battery, dict):
                percentage = battery.get("percentage")
                status_text = localize_battery_status(battery.get("status"))
                temperature = battery.get("temperature")

                battery_parts = []
                if percentage is not None:
                    battery_parts.append(f"{percentage}%")
                if status_text:
                    battery_parts.append(status_text)
                if temperature is not None:
                    battery_parts.append(f"{temperature} °C")

                if battery_parts:
                    battery_text = ", ".join(battery_parts)

            network = telemetry.get("network")
            network_text = "—"

            if isinstance(network, dict):
                ssid = network.get("ssid")
                ping_ms = network.get("ping_ms")
                ip = network.get("ip")

                parts = []
                if ssid:
                    parts.append(str(ssid))
                if ip:
                    parts.append(str(ip))
                if ping_ms is not None:
                    parts.append(f"{ping_ms} мс")

                if parts:
                    network_text = ", ".join(parts)

            send_text = (
                f"[green]✓ HTTP {escape(str(http_status or 204))}[/green]"
                if success
                else (
                    f"[red]✕ HTTP {escape(str(http_status))}[/red]"
                    if http_status
                    else "[dim]—[/dim]"
                )
            )

            process_text = (
                f"[green]{tr('status.alive')}[/green]"
                if running
                else f"[red]{tr('status.not_running')}[/red]"
            )
            gql_text = (
                f"[green]✓ {tr('status.normal')}[/green]"
                if gql_ok
                else f"[yellow]⚠ {tr('status.temporary_error')}[/yellow]"
            )
            wake_text = (
                f"[green]{tr('status.requested')}[/green]"
                if telemetry.get("wake_lock_requested")
                else "—"
            )

            health = (
                f"[bold #E8E3F5]✦ {tr('headings.system')}[/bold #E8E3F5]\n"
                f"[yellow]{tr('labels.process')}:[/yellow] {process_text}\n"
                f"[yellow]{tr('labels.watch_packet')}:[/yellow] {send_text}\n"
                f"[yellow]{tr('labels.last_http_204')}:[/yellow] {last_success}\n"
                f"[yellow]{tr('labels.twitch_gql')}:[/yellow] {gql_text}\n"
                f"[yellow]{tr('labels.wake_lock')}:[/yellow] {wake_text}\n"
                f"[yellow]{tr('labels.network')}:[/yellow] {escape(network_text)}\n"
                f"[yellow]{tr('labels.battery')}:[/yellow] {escape(battery_text)}"
            )

            self.query_one("#health-card", Static).update(health)

    def claims_summary(self) -> tuple[int, int, int]:
            items = load_jsonl(HISTORY_PATH, 1000)
            now = datetime.now().astimezone()
            today = now.date()
            week_start = today - timedelta(days=6)

            today_count = 0
            week_count = 0

            for item in items:
                timestamp = parse_iso(item.get("timestamp"))
                if timestamp is None:
                    continue

                local_date = timestamp.astimezone().date()

                if local_date == today:
                    today_count += 1
                if week_start <= local_date <= today:
                    week_count += 1

            return today_count, week_count, len(items)

    def refresh_stats_card(self, state: dict[str, Any]) -> None:
            telemetry = state.get("_telemetry")
            telemetry = telemetry if isinstance(telemetry, dict) else {}

            stats = state.get("_stats")
            stats = stats if isinstance(stats, dict) else load_json(STATS_PATH, {})
            stats = stats if isinstance(stats, dict) else {}

            today_claims, week_claims, all_claims = self.claims_summary()

            cycles = int(state.get("cycles") or 0)
            success_packets = int(stats.get("successful_packets") or 0)
            failed_packets = int(stats.get("failed_packets") or 0)
            switches = int(stats.get("switches") or 0)
            restarts = int(stats.get("restarts") or 0)

            content = (
                f"[bold #E8E3F5]✦ {tr('headings.statistics')}[/bold #E8E3F5]\n\n"
                f"[yellow]{tr('labels.drops')}:[/yellow]\n"
                f"{tr('stats.today_row', default='Сьогодні: {count}', count=today_claims)}\n"
                f"{tr('stats.seven_days_row', default='За 7 днів: {count}', count=week_claims)}\n"
                f"{tr('stats.total_row', default='Загалом: {count}', count=all_claims)}\n\n"
                f"[yellow]{tr('labels.packets')}:[/yellow]\n"
                f"✓ {success_packets}  |  ✕ {failed_packets}\n"
                f"{tr('stats.session_cycles_row', default='Циклів у сесії: {count}', count=cycles)}\n\n"
                f"[yellow]{tr('labels.switches')}:[/yellow] {switches}\n"
                f"[yellow]{tr('labels.auto_restarts')}:[/yellow] {restarts}\n"
                f"[yellow]{tr('labels.session_watch_time')}:[/yellow] "
                f"≈ {plural('units.minute', cycles)}\n"
                f"[dim]{tr('stats.graph_hint')}[/dim]"
            )

            self.query_one("#stats-content", Static).update(content)

            history = telemetry.get("packet_history")
            if not isinstance(history, list) or not history:
                history = [0]

            values = []
            for value_item in history[-40:]:
                try:
                    values.append(float(value_item))
                except (TypeError, ValueError):
                    values.append(0.0)

            self.query_one("#packet-sparkline", Sparkline).data = values

    def refresh_runtime(self) -> None:
            cleanup_stale_pid()
            running = process_running()
            state = read_state()

            self.query_one("#hero-card", Static).update(
                self.hero_markup(running, state)
            )

            self.refresh_drop_card(state)
            self.refresh_queue_card(state)
            self.refresh_health_card(running, state)
            self.refresh_stats_card(state)

            self.query_one("#start-nyxor", Button).disabled = running
            self.query_one("#stop-nyxor", Button).disabled = not running
            self.query_one("#restart-nyxor", Button).disabled = not running

            if self._last_running and not running and not self._stop_requested:
                meta = state.get("_meta")
                error = meta.get("error") if isinstance(meta, dict) else None

                if error:
                    self.notify(
                        str(error)[:160],
                        title=tr("notifications.stopped"),
                        severity="error",
                        timeout=8,
                    )

            if not running:
                self._stop_requested = False

            self._last_running = running

    def refresh_events(self) -> None:
            events = load_jsonl(EVENTS_PATH, 100)
            signature = json.dumps(events[-12:], ensure_ascii=False, sort_keys=True)

            if signature == self._last_events_signature:
                return

            self._last_events_signature = signature
            log = self.query_one("#live-events", RichLog)
            log.clear()

            if not events:
                log.write(f"[dim]{tr('status.events_empty', default='No events yet. Start NYXOR.')}[/dim]")
                return

            icons = {
                "start": "▶",
                "stop": "■",
                "packet": "✓",
                "packet_error": "✕",
                "switch_game": "🔄",
                "switch_channel": "📺",
                "claim": "🎁",
                "error": "⚠",
                "restart": "↻",
                "idle": "⏸",
            }

            for item in events[-8:]:
                timestamp = str(item.get("timestamp") or "")[11:19]
                event_type = str(item.get("type") or "event")
                icon = icons.get(event_type, "•")
                message = escape(localize_runtime_message(item.get("message") or event_type))
                log.write(f"[dim]{timestamp}[/dim]  {icon} {message}")

            log.scroll_end(animate=False)
