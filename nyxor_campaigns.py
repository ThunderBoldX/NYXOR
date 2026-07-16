from __future__ import annotations

import asyncio
import secrets
from typing import Any

import aiohttp
from rich.console import Console
from rich.table import Table

from constants import COOKIES_PATH, ClientType, GQL_QUERIES


GQL_URL = "https://gql.twitch.tv/gql"
console = Console()


def get_cookie_value(
    cookies: Any,
    name: str,
) -> str | None:
    cookie = cookies.get(name)
    return cookie.value if cookie is not None else None


def campaign_progress(campaign: dict[str, Any]) -> tuple[str, str]:
    drops = campaign.get("timeBasedDrops") or []

    if not drops:
        return "0%", campaign.get("name", "—")

    progresses: list[float] = []
    active_drop_name = "—"

    for drop in drops:
        required = int(drop.get("requiredMinutesWatched") or 0)
        self_data = drop.get("self") or {}

        current = int(self_data.get("currentMinutesWatched") or 0)
        claimed = bool(self_data.get("isClaimed"))

        if claimed:
            progress = 1.0
        elif required > 0:
            progress = min(current / required, 1.0)
        else:
            progress = 0.0

        progresses.append(progress)

        if (
            active_drop_name == "—"
            and not claimed
            and current < required
        ):
            active_drop_name = drop.get("name", "Невідомий Drop")

    if active_drop_name == "—":
        active_drop_name = "Усі Drops виконані"

    average = sum(progresses) / len(progresses)
    return f"{round(average * 100)}%", active_drop_name


async def gql_request(
    session: aiohttp.ClientSession,
    operation: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    async with session.post(
        GQL_URL,
        headers=headers,
        json=operation,
    ) as response:
        text = await response.text()

        if response.status != 200:
            raise RuntimeError(
                f"HTTP {response.status}: {text[:500]}"
            )

        data = await response.json(content_type=None)

        if isinstance(data, list):
            if not data:
                raise RuntimeError("Twitch повернув порожній список")
            data = data[0]

        if data.get("errors"):
            raise RuntimeError(
                f"GQL error: {data['errors']}"
            )

        return data


async def main() -> None:
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
        console.print(
            "[cyan]🔎 Отримую список Drops-кампаній...[/cyan]"
        )

        dashboard_response = await gql_request(
            session,
            GQL_QUERIES["Campaigns"],
            headers,
        )

        inventory_response = await gql_request(
            session,
            GQL_QUERIES["Inventory"],
            headers,
        )

    current_user = (
        dashboard_response
        .get("data", {})
        .get("currentUser")
    )

    if not current_user:
        raise RuntimeError(
            "Twitch не повернув currentUser"
        )

    campaigns = current_user.get("dropCampaigns") or []

    inventory = (
        inventory_response
        .get("data", {})
        .get("currentUser", {})
        .get("inventory")
        or {}
    )

    in_progress = inventory.get(
        "dropCampaignsInProgress"
    ) or []

    progress_by_id = {
        campaign.get("id"): campaign
        for campaign in in_progress
        if campaign.get("id")
    }

    active_campaigns = [
        campaign
        for campaign in campaigns
        if campaign.get("status") == "ACTIVE"
    ]

    active_campaigns.sort(
        key=lambda campaign: (
            campaign.get("game", {}).get("name", ""),
            campaign.get("name", ""),
        )
    )

    table = Table(
        title=f"🎁 Активні Twitch Drops: {len(active_campaigns)}",
        show_lines=True,
    )

    table.add_column("Гра", style="cyan")
    table.add_column("Кампанія")
    table.add_column("Наступний Drop")
    table.add_column("Прогрес", justify="center")
    table.add_column("Стан", justify="center")

    for campaign in active_campaigns:
        campaign_id = campaign.get("id")
        progress_campaign = progress_by_id.get(campaign_id)

        game_data = campaign.get("game") or {}
        game_name = (
            game_data.get("name")
            or game_data.get("displayName")
            or "Невідома гра"
        )

        campaign_name = campaign.get(
            "name",
            "Без назви",
        )

        if progress_campaign:
            progress, drop_name = campaign_progress(
                progress_campaign
            )
            state = "[green]У процесі[/green]"
        else:
            progress = "0%"
            drop_name = "Ще не розпочато"
            state = "[yellow]Доступна[/yellow]"

        table.add_row(
            game_name,
            campaign_name,
            drop_name,
            progress,
            state,
        )

    if active_campaigns:
        console.print(table)
    else:
        console.print(
            "[yellow]Активних Drops-кампаній зараз "
            "не знайдено.[/yellow]"
        )

    console.print(
        f"\n[green]✓[/green] Кампаній у поточному "
        f"Inventory: [bold]{len(in_progress)}[/bold]"
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Скасовано[/yellow]")
    except Exception as error:
        console.print(
            f"\n[bold red]❌ Помилка:[/bold red] {error}"
        )
        raise SystemExit(1)
