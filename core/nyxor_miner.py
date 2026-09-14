from __future__ import annotations

import asyncio
import base64
import json
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any

import aiohttp
from nyxor.network import client_session
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




