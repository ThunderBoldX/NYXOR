from __future__ import annotations

import asyncio
import secrets
import sys

import aiohttp
from rich.console import Console

from constants import COOKIES_PATH, ClientType
from nyxor_campaigns import get_cookie_value
from nyxor_miner import build_gql_headers, validate_account
from nyxor_player import touch_hls_stream


console = Console()


async def main(login: str) -> int:
    login = login.strip().removeprefix("@").strip("/")
    if not login:
        console.print("[red]Вкажи Twitch-логін каналу.[/red]")
        return 2

    client = ClientType.ANDROID_APP
    if not COOKIES_PATH.exists():
        console.print("[red]Не знайдено cookies.jar. Запусти python nyxor_auth.py[/red]")
        return 2

    jar = aiohttp.CookieJar()
    jar.load(COOKIES_PATH)
    cookies = jar.filter_cookies(client.CLIENT_URL)
    token = get_cookie_value(cookies, "auth-token")
    device_id = get_cookie_value(cookies, "unique_id") or secrets.token_hex(16)

    if not token:
        console.print("[red]У cookies.jar немає auth-token.[/red]")
        return 2

    timeout = aiohttp.ClientTimeout(sock_connect=20, total=45)
    async with aiohttp.ClientSession(
        timeout=timeout,
        cookie_jar=jar,
        headers={"User-Agent": client.USER_AGENT},
    ) as session:
        account = await validate_account(session, token)
        account_login = str(account.get("login") or "невідомо")
        headers = build_gql_headers(client, token, device_id)

        console.print(f"[cyan]Акаунт:[/cyan] [bold]{account_login}[/bold]")
        console.print(f"[cyan]Канал:[/cyan] [bold]{login}[/bold]")
        console.print("[cyan]Перевіряю PlaybackAccessToken → HLS → відеосегмент…[/cyan]")

        result = await touch_hls_stream(
            session,
            headers,
            login,
            user_agent=client.USER_AGENT,
        )

    if result.active:
        console.print(
            f"[bold green]✓ HLS-плеєр працює[/bold green] "
            f"([bold]{result.quality}[/bold], HTTP {result.http_status})"
        )
        return 0

    console.print(f"[bold red]✗ HLS-перевірка не пройшла:[/bold red] {result.detail}")
    return 1


if __name__ == "__main__":
    channel = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        raise SystemExit(asyncio.run(main(channel)))
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        console.print(f"[bold red]Помилка:[/bold red] {error}")
        raise SystemExit(1)
