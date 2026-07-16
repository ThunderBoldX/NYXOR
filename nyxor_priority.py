from __future__ import annotations

import asyncio
import secrets
import sys
from typing import Any

import aiohttp
from rich.console import Console
from rich.table import Table

from constants import COOKIES_PATH, ClientType, GQL_QUERIES
from nyxor_campaigns import get_cookie_value, gql_request
from nyxor_channels import load_settings, save_settings


console = Console()


def game_name(campaign: dict[str, Any]) -> str:
    game = campaign.get("game") or {}
    return str(game.get("name") or game.get("displayName") or "Невідома гра")


async def fetch_active_games() -> list[dict[str, Any]]:
    client = ClientType.ANDROID_APP

    if not COOKIES_PATH.exists():
        raise RuntimeError("Не знайдено cookies.jar")

    jar = aiohttp.CookieJar()
    jar.load(COOKIES_PATH)
    cookies = jar.filter_cookies(client.CLIENT_URL)

    token = get_cookie_value(cookies, "auth-token")
    device_id = get_cookie_value(cookies, "unique_id") or secrets.token_hex(16)

    if not token:
        raise RuntimeError("У cookies.jar немає auth-token")

    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip",
        "Accept-Language": "en-US",
        "Authorization": f"OAuth {token}",
        "Cache-Control": "no-cache",
        "Client-Id": client.CLIENT_ID,
        "Client-Session-Id": secrets.token_hex(8),
        "Content-Type": "application/json",
        "Origin": str(client.CLIENT_URL),
        "Pragma": "no-cache",
        "Referer": str(client.CLIENT_URL),
        "User-Agent": client.USER_AGENT,
        "X-Device-Id": device_id,
    }

    timeout = aiohttp.ClientTimeout(sock_connect=20, total=40)

    async with aiohttp.ClientSession(timeout=timeout, cookie_jar=jar) as session:
        response = await gql_request(session, GQL_QUERIES["Campaigns"], headers)

    current_user = response.get("data", {}).get("currentUser")
    if not current_user:
        raise RuntimeError("Twitch не повернув currentUser")

    grouped: dict[str, dict[str, Any]] = {}

    for campaign in current_user.get("dropCampaigns") or []:
        if campaign.get("status") != "ACTIVE":
            continue

        name = game_name(campaign)
        self_data = campaign.get("self") or {}
        linked = bool(self_data.get("isAccountConnected") or not campaign.get("accountLinkURL"))

        entry = grouped.setdefault(
            name,
            {"name": name, "campaigns": 0, "drops": 0, "linked": False},
        )
        entry["campaigns"] += 1
        entry["drops"] += len(campaign.get("timeBasedDrops") or [])
        entry["linked"] = bool(entry["linked"] or linked)

    return sorted(grouped.values(), key=lambda item: item["name"].lower())


def current_priority(settings: dict[str, Any]) -> list[str]:
    value = settings.get("priority_games")
    if isinstance(value, list):
        result = [str(game).strip() for game in value if str(game).strip()]
        if result:
            return result

    old_value = settings.get("priority_game")
    if isinstance(old_value, str) and old_value.strip():
        return [old_value.strip()]

    return []


def save_priority(games: list[str]) -> None:
    settings = load_settings()
    settings["priority_games"] = games

    if games:
        settings["priority_game"] = games[0]
    else:
        settings.pop("priority_game", None)

    save_settings(settings)


def display_games(games: list[dict[str, Any]], priority: list[str]) -> None:
    positions = {name.lower(): index + 1 for index, name in enumerate(priority)}

    table = Table(title="🎮 Активні ігри з Twitch Drops", show_lines=True)
    table.add_column("№", justify="right", style="yellow")
    table.add_column("Гра", style="cyan")
    table.add_column("Кампаній", justify="right")
    table.add_column("Drops", justify="right")
    table.add_column("Прив'язка", justify="center")
    table.add_column("Пріоритет", justify="center")

    for index, game in enumerate(games, start=1):
        position = positions.get(game["name"].lower())
        table.add_row(
            str(index),
            game["name"],
            str(game["campaigns"]),
            str(game["drops"]),
            "[green]готово[/green]" if game["linked"] else "[red]немає[/red]",
            f"[bold green]{position}[/bold green]" if position else "—",
        )

    console.print(table)


def parse_numbers(raw: str, games: list[dict[str, Any]]) -> list[str]:
    numbers: list[int] = []

    for part in raw.replace(" ", "").split(","):
        if not part:
            continue

        try:
            number = int(part)
        except ValueError as error:
            raise ValueError(f"«{part}» — не номер") from error

        if not 1 <= number <= len(games):
            raise ValueError(f"Номера {number} немає у таблиці")

        if number not in numbers:
            numbers.append(number)

    return [games[number - 1]["name"] for number in numbers]


async def main() -> None:
    console.print("[cyan]🔎 Отримую активні Drops-ігри...[/cyan]")

    games = await fetch_active_games()
    priority = current_priority(load_settings())

    if not games:
        console.print("[yellow]Активних Drops-ігор не знайдено.[/yellow]")
        return

    display_games(games, priority)

    console.print()
    console.print("[bold]Введи номери ігор у потрібному порядку.[/bold]")
    console.print("Наприклад: [cyan]12,5,31[/cyan] — спочатку №12, потім №5, потім №31.")
    console.print("[dim]Enter — залишити як є; 0 — очистити список.[/dim]")

    raw = ",".join(sys.argv[1:]).strip()
    if not raw:
        raw = input("\nПріоритети: ").strip()

    if not raw:
        console.print("[yellow]Список не змінено.[/yellow]")
        return

    if raw == "0":
        save_priority([])
        console.print("[green]✅ Список пріоритетів очищено.[/green]")
        return

    selected = parse_numbers(raw, games)
    save_priority(selected)

    console.print()
    console.print("[green]✅ Пріоритети збережено:[/green]")
    for index, game in enumerate(selected, start=1):
        console.print(f"  [bold]{index}.[/bold] {game}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Скасовано[/yellow]")
    except Exception as error:
        console.print(f"\n[bold red]❌ Помилка:[/bold red] {error}")
        raise SystemExit(1)
