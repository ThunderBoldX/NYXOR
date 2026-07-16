from __future__ import annotations

import asyncio
import json
import secrets
import sys
from pathlib import Path
from typing import Any, Iterator

import aiohttp
from rich.console import Console
from rich.table import Table

from constants import COOKIES_PATH, ClientType, GQL_QUERIES
from nyxor_campaigns import get_cookie_value, gql_request


SETTINGS_PATH = Path("nyxor_settings.json")
MAX_CHANNELS = 30

console = Console()


def load_settings() -> dict[str, Any]:
    if not SETTINGS_PATH.exists():
        return {}

    try:
        data = json.loads(
            SETTINGS_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}


def save_settings(settings: dict[str, Any]) -> None:
    SETTINGS_PATH.write_text(
        json.dumps(
            settings,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_selected_game() -> str:
    # Можна вручну передати гру:
    # python nyxor_channels.py "World of Warships"
    argument_game = " ".join(sys.argv[1:]).strip()

    if argument_game:
        return argument_game

    settings = load_settings()
    selected_game = settings.get("priority_game")

    if (
        not isinstance(selected_game, str)
        or not selected_game.strip()
    ):
        raise RuntimeError(
            "Пріоритетну гру не вибрано. "
            "Спочатку вибери її в termux_main.py."
        )

    return selected_game.strip()


def walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    """
    Проходить по всій відповіді Twitch.
    Це робить парсер стійкішим до невеликих змін структури GQL.
    """
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_dicts(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


def extract_slug(response: dict[str, Any]) -> str:
    for item in walk_dicts(response.get("data", {})):
        slug = item.get("slug")

        if isinstance(slug, str) and slug.strip():
            return slug.strip()

    raise RuntimeError(
        "Twitch не повернув slug для вибраної гри"
    )


def extract_channels(
    response: dict[str, Any],
    selected_game: str,
) -> list[dict[str, Any]]:
    channels: list[dict[str, Any]] = []
    seen_streams: set[str] = set()

    for node in walk_dicts(response.get("data", {})):
        broadcaster = node.get("broadcaster")
        stream_id = node.get("id")

        if not isinstance(broadcaster, dict):
            continue

        login = broadcaster.get("login")
        channel_id = broadcaster.get("id")

        if not login or not channel_id or not stream_id:
            continue

        stream_id = str(stream_id)

        # Через рекурсивний пошук той самий вузол
        # іноді може трапитися повторно.
        if stream_id in seen_streams:
            continue

        seen_streams.add(stream_id)

        display_name = (
            broadcaster.get("displayName")
            or login
        )

        game_data = node.get("game")

        if not isinstance(game_data, dict):
            game_data = {}

        game_name = (
            game_data.get("name")
            or game_data.get("displayName")
            or selected_game
        )

        viewers = node.get("viewersCount", 0)

        try:
            viewers = int(viewers or 0)
        except (TypeError, ValueError):
            viewers = 0

        title = node.get("title") or "Без назви"

        channels.append(
            {
                "stream_id": stream_id,
                "channel_id": str(channel_id),
                "login": str(login),
                "display_name": str(display_name),
                "game": str(game_name),
                "game_id": str(game_data.get("id") or ""),
                "viewers": viewers,
                "title": str(title),
            }
        )

    channels.sort(
        key=lambda channel: channel["viewers"],
        reverse=True,
    )

    return channels


async def fetch_channels(
    selected_game: str,
    verbose: bool = True,
) -> tuple[str, list[dict[str, Any]]]:
    client = ClientType.ANDROID_APP

    if not COOKIES_PATH.exists():
        raise RuntimeError("Не знайдено cookies.jar")

    jar = aiohttp.CookieJar()
    jar.load(COOKIES_PATH)

    cookies = jar.filter_cookies(client.CLIENT_URL)

    token = get_cookie_value(cookies, "auth-token")

    device_id = (
        get_cookie_value(cookies, "unique_id")
        or secrets.token_hex(16)
    )

    if not token:
        raise RuntimeError(
            "У cookies.jar немає auth-token"
        )

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

    timeout = aiohttp.ClientTimeout(
        sock_connect=20,
        total=40,
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        cookie_jar=jar,
    ) as session:

        if verbose:
            console.print(
                f"[cyan]🎮 Шукаю Twitch-категорію: "
                f"[bold]{selected_game}[/bold][/cyan]"
            )

        # Перетворюємо назву гри на Twitch slug.
        slug_response = await gql_request(
            session,
            GQL_QUERIES["SlugRedirect"].with_variables(
                {
                    "name": selected_game,
                }
            ),
            headers,
        )

        game_slug = extract_slug(slug_response)

        if verbose:
            console.print(
                f"[green]✓[/green] Twitch slug: "
                f"[bold]{game_slug}[/bold]"
            )

        if verbose:
            console.print(
                "[cyan]📡 Отримую онлайн-канали "
                "з увімкненими Drops...[/cyan]"
            )

        directory_query = (
            GQL_QUERIES["GameDirectory"]
            .with_variables(
                {
                    "limit": MAX_CHANNELS,
                    "slug": game_slug,
                    "options": {
                        "systemFilters": [
                            "DROPS_ENABLED"
                        ],
                        "sort": "VIEWER_COUNT",
                    },
                }
            )
        )

        directory_response = await gql_request(
            session,
            directory_query,
            headers,
        )

    channels = extract_channels(
        directory_response,
        selected_game,
    )

    return game_slug, channels


def display_channels(
    selected_game: str,
    channels: list[dict[str, Any]],
) -> None:
    table = Table(
        title=(
            f"📺 Drops-канали: {selected_game} "
            f"({len(channels)})"
        ),
        show_lines=True,
    )

    table.add_column(
        "№",
        justify="right",
        style="yellow",
        width=3,
    )

    table.add_column(
        "Канал",
        style="cyan",
        no_wrap=True,
    )

    table.add_column(
        "Глядачі",
        justify="right",
        style="green",
    )

    table.add_column(
        "Назва стріму",
        overflow="fold",
    )

    for number, channel in enumerate(
        channels,
        start=1,
    ):
        table.add_row(
            str(number),
            channel["display_name"],
            f'{channel["viewers"]:,}'.replace(",", " "),
            channel["title"],
        )

    console.print()
    console.print(table)


def choose_channel(
    selected_game: str,
    channels: list[dict[str, Any]],
) -> None:
    if not channels:
        return

    console.print()
    console.print(
        "[dim]Можна зберегти бажаний канал. "
        "Пізніше майнер автоматично переключиться, "
        "якщо він стане офлайн.[/dim]"
    )

    choice = input(
        "\nВведи номер каналу для збереження "
        "або Enter, щоб пропустити: "
    ).strip()

    if not choice:
        console.print(
            "[yellow]Канал поки не вибрано.[/yellow]"
        )
        return

    try:
        index = int(choice) - 1
    except ValueError:
        console.print(
            "[red]Потрібно ввести номер із таблиці.[/red]"
        )
        return

    if index < 0 or index >= len(channels):
        console.print(
            "[red]Такого номера в таблиці немає.[/red]"
        )
        return

    selected = channels[index]

    settings = load_settings()

    settings["priority_game"] = selected_game
    settings["preferred_channel"] = {
        "login": selected["login"],
        "display_name": selected["display_name"],
        "channel_id": selected["channel_id"],
        "stream_id": selected["stream_id"],
        "game": selected["game"],
        "game_id": selected["game_id"],
    }

    save_settings(settings)

    console.print()
    console.print(
        f"[green]✅ Канал збережено:[/green] "
        f"[bold]{selected['display_name']}[/bold]"
    )

    console.print(
        f"[dim]https://www.twitch.tv/"
        f"{selected['login']}[/dim]"
    )


async def main() -> None:
    selected_game = get_selected_game()

    game_slug, channels = await fetch_channels(
        selected_game
    )

    if not channels:
        console.print()
        console.print(
            "[yellow]⚠ Для цієї гри зараз не знайдено "
            "онлайн-каналів з Drops.[/yellow]"
        )
        console.print(
            f"[dim]Гра: {selected_game}, "
            f"slug: {game_slug}[/dim]"
        )
        return

    display_channels(
        selected_game,
        channels,
    )

    choose_channel(
        selected_game,
        channels,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]Скасовано[/yellow]"
        )

    except Exception as error:
        console.print()
        console.print(
            f"[bold red]❌ Помилка:[/bold red] {error}"
        )
        raise SystemExit(1)
