from __future__ import annotations

import asyncio
import base64
import json
import re
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from constants import COOKIES_PATH, ClientType, GQL_QUERIES
from nyxor_campaigns import get_cookie_value, gql_request
from nyxor_channels import fetch_channels, load_settings


WATCH_INTERVAL = 20
CHANNEL_REFRESH_CYCLES = 5

SETTINGS_PATTERN = (
    r'src="(https://[\w.]+/config/'
    r'settings\.[0-9a-f]{32}\.js)"'
)

SPADE_PATTERN = (
    r'"spade_?url"\s*:\s*"'
    r'(https://[.\w\-/]+)"'
)

console = Console()


def iso_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def run_termux_command(command: str) -> None:
    executable = shutil.which(command)

    if executable is None:
        return

    subprocess.run(
        [executable],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def build_gql_headers(
    client: Any,
    token: str,
    device_id: str,
) -> dict[str, str]:
    return {
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


def create_watch_payload(
    channel: dict[str, Any],
    user_id: str,
) -> dict[str, str]:
    """
    Build the same minimal minute-watched event shape used by the
    current Twitch Channel Points Miner.

    Twitch Spade can return HTTP 204 even when an event is not useful
    for viewer-crediting, so avoid unrelated fields and keep player=site.
    """

    properties: dict[str, Any] = {
        "channel_id": str(channel["channel_id"]),
        "broadcast_id": str(channel["stream_id"]),
        "player": "site",
        "user_id": str(user_id),
        "live": True,
        "channel": str(channel["login"]),
    }

    game = str(channel.get("game") or "").strip()
    game_id = str(channel.get("game_id") or "").strip()

    if game and game_id:
        properties["game"] = game
        properties["game_id"] = game_id

    event = [
        {
            "event": "minute-watched",
            "properties": properties,
        }
    ]

    compact = json.dumps(
        event,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    encoded = base64.b64encode(
        compact.encode("utf-8")
    ).decode("ascii")

    return {"data": encoded}


async def get_spade_url(
    session: aiohttp.ClientSession,
    login: str,
) -> str:
    page_variants = [
        (
            f"https://m.twitch.tv/{login}",
            ClientType.MOBILE_WEB.USER_AGENT,
        ),
        (
            f"https://www.twitch.tv/{login}",
            ClientType.WEB.USER_AGENT,
        ),
    ]

    for page_url, user_agent in page_variants:
        try:
            async with session.get(
                page_url,
                headers={
                    "User-Agent": user_agent,
                },
            ) as response:
                response.raise_for_status()
                page_html = await response.text()

        except (aiohttp.ClientError, asyncio.TimeoutError):
            continue

        # Twitch іноді екранує слеші у JavaScript.
        page_html = page_html.replace("\\/", "/")

        match = re.search(
            SPADE_PATTERN,
            page_html,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

        settings_match = re.search(
            SETTINGS_PATTERN,
            page_html,
            re.IGNORECASE,
        )

        if settings_match is None:
            continue

        settings_url = settings_match.group(1)

        async with session.get(
            settings_url,
            headers={
                "User-Agent": ClientType.WEB.USER_AGENT,
            },
        ) as response:
            response.raise_for_status()
            settings_js = await response.text()

        settings_js = settings_js.replace("\\/", "/")

        match = re.search(
            SPADE_PATTERN,
            settings_js,
            re.IGNORECASE,
        )

        if match:
            return match.group(1)

    raise RuntimeError(
        "Не вдалося отримати Twitch Spade URL"
    )


async def validate_account(
    session: aiohttp.ClientSession,
    token: str,
) -> dict[str, Any]:
    async with session.get(
        "https://id.twitch.tv/oauth2/validate",
        headers={
            "Authorization": f"OAuth {token}",
        },
    ) as response:
        if response.status == 401:
            raise RuntimeError(
                "Токен Twitch недійсний. "
                "Потрібно авторизуватися повторно."
            )

        response.raise_for_status()
        return await response.json()


async def send_watch(
    session: aiohttp.ClientSession,
    spade_url: str,
    channel: dict[str, Any],
    user_id: str,
) -> tuple[bool, int]:
    payload = create_watch_payload(
        channel,
        user_id,
    )

    try:
        async with session.post(
            spade_url,
            data=payload,
        ) as response:
            await response.read()

            return (
                response.status == 204,
                response.status,
            )

    except (
        aiohttp.ClientError,
        asyncio.TimeoutError,
    ):
        return False, 0


async def get_current_progress(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    channel_id: str,
) -> str:
    try:
        operation = (
            GQL_QUERIES["CurrentDrop"]
            .with_variables(
                {
                    "channelID": str(channel_id),
                }
            )
        )

        response = await gql_request(
            session,
            operation,
            headers,
        )

        current_session = (
            response
            .get("data", {})
            .get("currentUser", {})
            .get("dropCurrentSession")
        )

        if not current_session:
            return (
                "Twitch ще не показує активний Drop"
            )

        minutes = int(
            current_session.get(
                "currentMinutesWatched"
            )
            or 0
        )

        drop_id = str(
            current_session.get("dropID")
            or "невідомий"
        )

        return (
            f"Twitch підтвердив {minutes} хв "
            f"(Drop {drop_id[:8]}…)"
        )

    except Exception as error:
        return (
            "Перевірка прогресу недоступна: "
            f"{str(error)[:45]}"
        )


def select_best_channel(
    channels: list[dict[str, Any]],
    preferred_login: str,
    current_login: str = "",
) -> dict[str, Any] | None:
    if not channels:
        return None

    preferred_login = preferred_login.lower()
    current_login = current_login.lower()

    # Спочатку повертаємося до каналу,
    # який користувач вибрав вручну.
    if preferred_login:
        for channel in channels:
            if (
                str(channel.get("login") or "")
                .lower()
                == preferred_login
            ):
                return channel

    # Якщо поточний канал ще онлайн —
    # залишаємося на ньому.
    if current_login:
        for channel in channels:
            if (
                str(channel.get("login") or "")
                .lower()
                == current_login
            ):
                return channel

    # Інакше беремо перший канал:
    # список уже відсортований за глядачами.
    return channels[0]


def render_status(state: dict[str, Any]) -> Panel:
    grid = Table.grid(
        padding=(0, 1),
        expand=True,
    )

    grid.add_column(
        style="yellow",
        no_wrap=True,
    )
    grid.add_column()

    success = bool(state.get("success"))

    if success:
        send_status = (
            f"[green]✓ HTTP "
            f"{state.get('http_status', 204)}[/green]"
        )
    elif state.get("http_status") is None:
        send_status = "[dim]ще не надсилалось[/dim]"
    else:
        send_status = (
            f"[red]✗ HTTP "
            f"{state.get('http_status') or 'помилка'}"
            f"[/red]"
        )

    grid.add_row(
        "Акаунт:",
        f"[bold]{escape(str(state['account']))}[/bold]",
    )

    grid.add_row(
        "Гра:",
        f"[cyan]{escape(str(state['game']))}[/cyan]",
    )

    grid.add_row(
        "Канал:",
        f"[bold cyan]"
        f"{escape(str(state['channel']))}"
        f"[/bold cyan]",
    )

    grid.add_row(
        "Глядачі:",
        escape(str(state.get("viewers", 0))),
    )

    grid.add_row(
        "Надсилання:",
        send_status,
    )

    grid.add_row(
        "Циклів:",
        str(state.get("cycles", 0)),
    )

    grid.add_row(
        "Прогрес:",
        escape(str(state.get("progress", "—"))),
    )

    grid.add_row(
        "Наступний пакет:",
        f"{state.get('remaining', 0)} с",
    )

    grid.add_row(
        "Стан:",
        escape(str(state.get("message", "Підготовка"))),
    )

    return Panel(
        grid,
        title="⛏ NYXOR — RUNNING",
        subtitle="Ctrl+C — зупинити",
        border_style=(
            "green"
            if success
            else "cyan"
        ),
    )


async def countdown(
    seconds: float,
    live: Live,
    state: dict[str, Any],
) -> None:
    deadline = time.monotonic() + max(seconds, 0)

    while True:
        remaining = deadline - time.monotonic()

        if remaining <= 0:
            state["remaining"] = 0
            live.update(render_status(state))
            return

        state["remaining"] = int(remaining) + 1
        live.update(render_status(state))

        await asyncio.sleep(
            min(1.0, remaining)
        )


async def main() -> None:
    settings = load_settings()

    selected_game = settings.get("priority_game")
    preferred = settings.get("preferred_channel")

    if (
        not isinstance(selected_game, str)
        or not selected_game.strip()
    ):
        raise RuntimeError(
            "Гру не вибрано в termux_main.py"
        )

    selected_game = selected_game.strip()

    preferred_login = ""

    if isinstance(preferred, dict):
        preferred_login = str(
            preferred.get("login") or ""
        )

    client = ClientType.ANDROID_APP

    if not COOKIES_PATH.exists():
        raise RuntimeError(
            "Не знайдено cookies.jar"
        )

    cookie_jar = aiohttp.CookieJar()
    cookie_jar.load(COOKIES_PATH)

    cookies = cookie_jar.filter_cookies(
        client.CLIENT_URL
    )

    token = get_cookie_value(
        cookies,
        "auth-token",
    )

    device_id = (
        get_cookie_value(cookies, "unique_id")
        or secrets.token_hex(16)
    )

    if not token:
        raise RuntimeError(
            "У cookies.jar немає auth-token"
        )

    timeout = aiohttp.ClientTimeout(
        sock_connect=20,
        total=40,
    )

    async with aiohttp.ClientSession(
        timeout=timeout,
        cookie_jar=cookie_jar,
        headers={
            "User-Agent": client.USER_AGENT,
        },
    ) as session:
        account = await validate_account(
            session,
            token,
        )

        account_login = str(
            account.get("login") or "невідомо"
        )

        user_id = str(
            account.get("user_id") or ""
        )

        if not user_id:
            raise RuntimeError(
                "Twitch не повернув User ID"
            )

        gql_headers = build_gql_headers(
            client,
            token,
            device_id,
        )

        console.print(
            f"[cyan]📡 Шукаю активний канал для "
            f"[bold]{selected_game}[/bold]...[/cyan]"
        )

        _, channels = await fetch_channels(
            selected_game,
            verbose=False,
        )

        channel = select_best_channel(
            channels,
            preferred_login,
        )

        if channel is None:
            raise RuntimeError(
                "Зараз немає онлайн-каналів "
                "із Drops для вибраної гри"
            )

        console.print(
            f"[green]✓[/green] Канал: "
            f"[bold]{channel['display_name']}[/bold]"
        )

        console.print(
            "[cyan]🔗 Отримую Spade URL...[/cyan]"
        )

        spade_url = await get_spade_url(
            session,
            str(channel["login"]),
        )

        console.print(
            "[green]✓[/green] Майнер готовий\n"
        )

        state: dict[str, Any] = {
            "account": account_login,
            "game": selected_game,
            "channel": channel["display_name"],
            "viewers": channel.get("viewers", 0),
            "success": False,
            "http_status": None,
            "cycles": 0,
            "progress": "Очікування першого пакета",
            "remaining": 0,
            "message": "Запуск фарму",
        }

        run_termux_command("termux-wake-lock")

        try:
            with Live(
                render_status(state),
                console=console,
                refresh_per_second=2,
            ) as live:

                while True:
                    cycle_started = time.monotonic()

                    state["message"] = (
                        "Надсилаю minute-watched..."
                    )
                    state["remaining"] = 0
                    live.update(render_status(state))

                    success, http_status = (
                        await send_watch(
                            session,
                            spade_url,
                            channel,
                            user_id,
                        )
                    )

                    state["success"] = success
                    state["http_status"] = http_status
                    state["cycles"] += 1

                    if success:
                        state["message"] = (
                            "Пакет прийнято Twitch"
                        )
                    else:
                        state["message"] = (
                            "Пакет не прийнято — "
                            "оновлюю канал"
                        )

                    live.update(render_status(state))

                    # Twitch не завжди відразу оновлює
                    # CurrentDrop, тому чекаємо 20 секунд.
                    await countdown(
                        20,
                        live,
                        state,
                    )

                    state["progress"] = (
                        await get_current_progress(
                            session,
                            gql_headers,
                            str(channel["channel_id"]),
                        )
                    )

                    live.update(render_status(state))

                    need_refresh = (
                        not success
                        or state["cycles"]
                        % CHANNEL_REFRESH_CYCLES
                        == 0
                    )

                    if need_refresh:
                        state["message"] = (
                            "Перевіряю онлайн-канали..."
                        )
                        live.update(render_status(state))

                        try:
                            _, fresh_channels = (
                                await fetch_channels(
                                    selected_game,
                                    verbose=False,
                                )
                            )

                            fresh_channel = (
                                select_best_channel(
                                    fresh_channels,
                                    preferred_login,
                                    str(
                                        channel.get(
                                            "login"
                                        )
                                        or ""
                                    ),
                                )
                            )

                        except Exception:
                            fresh_channel = None

                        if fresh_channel is not None:
                            stream_changed = (
                                str(
                                    fresh_channel.get(
                                        "stream_id"
                                    )
                                )
                                != str(
                                    channel.get(
                                        "stream_id"
                                    )
                                )
                            )

                            login_changed = (
                                str(
                                    fresh_channel.get(
                                        "login"
                                    )
                                ).lower()
                                != str(
                                    channel.get(
                                        "login"
                                    )
                                ).lower()
                            )

                            if (
                                stream_changed
                                or login_changed
                            ):
                                channel = fresh_channel

                                state["channel"] = (
                                    channel[
                                        "display_name"
                                    ]
                                )

                                state["viewers"] = (
                                    channel.get(
                                        "viewers",
                                        0,
                                    )
                                )

                                state["message"] = (
                                    "Перемикаю канал..."
                                )

                                live.update(
                                    render_status(state)
                                )

                                spade_url = (
                                    await get_spade_url(
                                        session,
                                        str(
                                            channel[
                                                "login"
                                            ]
                                        ),
                                    )
                                )

                    elapsed = (
                        time.monotonic()
                        - cycle_started
                    )

                    state["message"] = (
                        "Фарм працює"
                    )

                    await countdown(
                        WATCH_INTERVAL - elapsed,
                        live,
                        state,
                    )

        finally:
            run_termux_command(
                "termux-wake-unlock"
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        console.print(
            "\n[yellow]⏹ Майнер зупинено[/yellow]"
        )

    except Exception as error:
        console.print()
        console.print(
            f"[bold red]❌ Помилка:[/bold red] "
            f"{error}"
        )
        raise SystemExit(1)
