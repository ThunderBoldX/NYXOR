from __future__ import annotations

import asyncio
import logging
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone, timedelta
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
from nyxor_miner import (
    WATCH_INTERVAL,
    build_gql_headers,
    get_spade_url,
    select_best_channel,
    send_watch,
    validate_account,
)


from nyxor_points import ChannelPointsTracker, update_channel_points
from nyxor_player import TwitchHLSPlayer
from nyxor_rewards import TwitchRewardsEngine

# NYXOR_CHANNEL_POINTS_PATCH_V1
STATE_REFRESH_CYCLES = 1
NO_TARGET_RETRY = 90
DETAIL_FETCH_DELAY = 0.30
STREAMER_CHECK_DELAY = 0.20
GQL_RETRY_DELAYS = (1.5, 3.0, 5.0)
GQL_FAILURE_WAIT = 15
DETAIL_CACHE: dict[str, dict[str, Any]] = {}
console = Console()
logger = logging.getLogger("NYXOR")


def parse_time(value: Any, fallback: datetime) -> datetime:
    if not isinstance(value, str) or not value:
        return fallback

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return fallback


def load_priority_games(settings: dict[str, Any]) -> list[str]:
    value = settings.get("priority_games")

    if isinstance(value, list):
        result = []
        for game in value:
            name = str(game).strip()
            if name and name not in result:
                result.append(name)
        if result:
            return result

    old_value = settings.get("priority_game")
    if isinstance(old_value, str) and old_value.strip():
        return [old_value.strip()]

    return []



def load_streamer_channels(settings: dict[str, Any]) -> list[str]:
    value = settings.get("streamer_channels")
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()

    for item in value:
        if isinstance(item, dict):
            login = str(item.get("login") or item.get("name") or "")
        else:
            login = str(item or "")

        login = login.strip().removeprefix("@").strip().strip("/")
        folded = login.casefold()

        if login and folded not in seen:
            seen.add(folded)
            result.append(login)

    return result

def preferred_channels(settings: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}

    mapping = settings.get("preferred_channels")
    if isinstance(mapping, dict):
        for game, channel in mapping.items():
            if isinstance(channel, dict):
                login = str(channel.get("login") or "").strip()
            else:
                login = str(channel or "").strip()

            if login:
                result[str(game)] = login

    old = settings.get("preferred_channel")
    if isinstance(old, dict):
        game = str(old.get("game") or "").strip()
        login = str(old.get("login") or "").strip()
        if game and login:
            result.setdefault(game, login)

    return result


def campaign_game_name(campaign: dict[str, Any]) -> str:
    game = campaign.get("game") or {}
    return str(game.get("name") or game.get("displayName") or "Невідома гра")


def drop_self_data(
    campaign_id: str,
    drop: dict[str, Any],
    inventory_drops: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    key = (campaign_id, str(drop.get("id") or ""))
    inventory_self = inventory_drops.get(key)

    # Inventory зазвичай має свіжіший прогрес, ніж загальний dashboard.
    if isinstance(inventory_self, dict) and inventory_self:
        return inventory_self

    own = drop.get("self")
    return own if isinstance(own, dict) else {}


def walk_dicts(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_dicts(child)


async def gql_request_retry(
    session: aiohttp.ClientSession,
    operation: dict[str, Any],
    headers: dict[str, str],
    *,
    attempts: int = 4,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            return await gql_request(session, operation, headers)
        except Exception as error:
            last_error = error

            if attempt >= attempts - 1:
                break

            delay = GQL_RETRY_DELAYS[
                min(attempt, len(GQL_RETRY_DELAYS) - 1)
            ]
            await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error


def extract_campaign_details(
    response: dict[str, Any],
    campaign_id: str,
) -> dict[str, Any] | None:
    direct = (
        response.get("data", {})
        .get("user", {})
        .get("dropCampaign")
    )

    if isinstance(direct, dict):
        return direct

    # Fallback на випадок невеликої зміни структури відповіді Twitch.
    for item in walk_dicts(response.get("data", {})):
        if (
            str(item.get("id") or "") == campaign_id
            and "timeBasedDrops" in item
        ):
            return item

    return None



def sanitize_campaign_details(
    details: dict[str, Any],
) -> dict[str, Any]:
    """Cache only structural drop data; progress comes from Inventory."""
    sanitized = dict(details)
    sanitized.pop("self", None)

    drops: list[dict[str, Any]] = []
    for raw_drop in details.get("timeBasedDrops") or []:
        if not isinstance(raw_drop, dict):
            continue
        drop = dict(raw_drop)
        drop.pop("self", None)
        drops.append(drop)

    sanitized["timeBasedDrops"] = drops
    return sanitized

def merge_campaign_data(
    summary: dict[str, Any],
    details: dict[str, Any] | None,
) -> dict[str, Any]:
    if not details:
        return summary

    merged = dict(summary)

    for key, value in details.items():
        if value is not None:
            merged[key] = value

    # Summary краще зберігає статус/зв'язок акаунта, коли details
    # повертає ці поля як None або взагалі їх не містить.
    if not merged.get("game"):
        merged["game"] = summary.get("game") or {}
    if not isinstance(merged.get("self"), dict):
        merged["self"] = summary.get("self") or {}
    if not merged.get("status"):
        merged["status"] = summary.get("status")
    if not merged.get("startAt"):
        merged["startAt"] = summary.get("startAt")
    if not merged.get("endAt"):
        merged["endAt"] = summary.get("endAt")

    return merged


async def fetch_campaign_snapshot(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    user_id: str = "",
    priority_games: list[str] | None = None,
) -> tuple[
    list[dict[str, Any]],
    dict[tuple[str, str], dict[str, Any]],
    dict[str, datetime],
]:
    dashboard_response = await gql_request_retry(
        session,
        GQL_QUERIES["Campaigns"],
        headers,
    )

    inventory_response = await gql_request_retry(
        session,
        GQL_QUERIES["Inventory"],
        headers,
    )

    current_user = (
        dashboard_response.get("data", {}).get("currentUser")
    )
    if not current_user:
        raise RuntimeError("Twitch не повернув currentUser")

    campaign_summaries = current_user.get("dropCampaigns") or []

    inventory = (
        inventory_response
        .get("data", {})
        .get("currentUser", {})
        .get("inventory")
        or {}
    )

    inventory_drops: dict[tuple[str, str], dict[str, Any]] = {}
    inventory_campaigns: dict[str, dict[str, Any]] = {}
    claimed_benefits: dict[str, datetime] = {}

    # Після claim завершена кампанія часто зникає з
    # dropCampaignsInProgress. gameEventDrops лишається історією нагород.
    for awarded in inventory.get("gameEventDrops") or []:
        if not isinstance(awarded, dict):
            continue

        benefit = awarded.get("benefit") or {}
        if not isinstance(benefit, dict):
            benefit = {}

        benefit_id = str(
            awarded.get("id")
            or benefit.get("id")
            or ""
        )
        awarded_at = (
            awarded.get("lastAwardedAt")
            or benefit.get("lastAwardedAt")
        )

        if benefit_id and isinstance(awarded_at, str):
            claimed_benefits[benefit_id] = parse_time(
                awarded_at,
                datetime.min.replace(tzinfo=timezone.utc),
            )

    for campaign in inventory.get("dropCampaignsInProgress") or []:
        if not isinstance(campaign, dict):
            continue

        campaign_id = str(campaign.get("id") or "")
        if campaign_id:
            inventory_campaigns[campaign_id] = campaign

        for drop in campaign.get("timeBasedDrops") or []:
            drop_id = str(drop.get("id") or "")
            self_data = drop.get("self") or {}

            if campaign_id and drop_id and isinstance(self_data, dict):
                inventory_drops[(campaign_id, drop_id)] = self_data

    wanted_games = set(priority_games or [])
    campaigns: list[dict[str, Any]] = []

    for summary in campaign_summaries:
        if not isinstance(summary, dict):
            continue

        campaign_id = str(summary.get("id") or "")
        game_name = campaign_game_name(summary)
        details: dict[str, Any] | None = None

        # Inventory може відразу дати повну структуру для кампанії,
        # прогрес якої вже починався.
        inventory_campaign = inventory_campaigns.get(campaign_id)
        if inventory_campaign and inventory_campaign.get("timeBasedDrops"):
            details = inventory_campaign

        # ViewerDropsDashboard повертає лише оболонку кампанії. Повний
        # timeBasedDrops отримуємо через DropCampaignDetails, як upstream TDM.
        should_load_details = (
            bool(campaign_id)
            and summary.get("status") == "ACTIVE"
            and (not wanted_games or game_name in wanted_games)
        )

        if should_load_details:
            cached = DETAIL_CACHE.get(campaign_id)
            if cached is not None:
                details = cached
            elif user_id:
                operation = GQL_QUERIES["CampaignDetails"].with_variables(
                    {
                        "channelLogin": str(user_id),
                        "dropID": campaign_id,
                    }
                )

                try:
                    response = await gql_request_retry(
                        session,
                        operation,
                        headers,
                    )
                    fetched = extract_campaign_details(
                        response,
                        campaign_id,
                    )
                    if fetched is not None:
                        cached_details = sanitize_campaign_details(fetched)
                        DETAIL_CACHE[campaign_id] = cached_details
                        details = cached_details
                except Exception:
                    # Не валимо весь майнер через одну volatile GQL-відповідь.
                    # На наступному циклі незакешована кампанія спробується ще раз.
                    pass

                await asyncio.sleep(DETAIL_FETCH_DELAY)

        campaigns.append(merge_campaign_data(summary, details))

    return campaigns, inventory_drops, claimed_benefits


def build_game_states(
    campaigns: list[dict[str, Any]],
    inventory_drops: dict[tuple[str, str], dict[str, Any]],
    claimed_benefits: dict[str, datetime],
) -> dict[str, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    states: dict[str, dict[str, Any]] = {}

    for campaign in campaigns:
        if campaign.get("status") != "ACTIVE":
            continue

        campaign_id = str(campaign.get("id") or "")
        game_name = campaign_game_name(campaign)
        campaign_self = campaign.get("self") or {}
        linked = bool(
            campaign_self.get("isAccountConnected")
            or not campaign.get("accountLinkURL")
        )

        campaign_start = parse_time(
            campaign.get("startAt"),
            datetime.min.replace(tzinfo=timezone.utc),
        )
        campaign_end = parse_time(
            campaign.get("endAt"),
            datetime.max.replace(tzinfo=timezone.utc),
        )

        state = states.setdefault(
            game_name,
            {
                "game": game_name,
                "campaigns": 0,
                "total": 0,
                "claimed": 0,
                "linked": False,
                "mineable": [],
                "ready": [],
                "future": [],
            },
        )

        state["campaigns"] += 1
        state["linked"] = bool(state["linked"] or linked)

        for drop in campaign.get("timeBasedDrops") or []:
            required = int(drop.get("requiredMinutesWatched") or 0)
            if required <= 0:
                continue

            drop_id = str(drop.get("id") or "")
            self_data = drop_self_data(
                campaign_id,
                drop,
                inventory_drops,
            )

            current = int(
                self_data.get("currentMinutesWatched") or 0
            )

            drop_start = parse_time(
                drop.get("startAt"),
                campaign_start,
            )
            drop_end = parse_time(
                drop.get("endAt"),
                campaign_end,
            )

            # Якщо Twitch повернув self — він є джерелом істини.
            # Коли self відсутній (типово після повного claim),
            # визначаємо завершення через gameEventDrops/benefitEdges.
            has_self = bool(self_data) or isinstance(
                drop.get("self"),
                dict,
            )
            claimed = bool(self_data.get("isClaimed"))

            if not has_self:
                awarded_dates: list[datetime] = []

                for edge in drop.get("benefitEdges") or []:
                    if not isinstance(edge, dict):
                        continue

                    benefit = edge.get("benefit") or {}
                    if not isinstance(benefit, dict):
                        benefit = {}

                    benefit_id = str(
                        benefit.get("id")
                        or edge.get("id")
                        or ""
                    )

                    if benefit_id in claimed_benefits:
                        awarded_dates.append(
                            claimed_benefits[benefit_id]
                        )

                if awarded_dates and all(
                    drop_start <= awarded_at < drop_end
                    for awarded_at in awarded_dates
                ):
                    claimed = True

            if claimed:
                current = required

            info = {
                "campaign_id": campaign_id,
                "campaign": str(campaign.get("name") or "Без назви"),
                "drop_id": drop_id,
                "drop": str(drop.get("name") or "Невідомий Drop"),
                "current": current,
                "required": required,
                "remaining": max(required - current, 0),
                "claimed": claimed,
                "starts_at": drop_start,
                "ends_at": drop_end,
                "linked": linked,
                "claim_id": (
                    str(self_data.get("dropInstanceID"))
                    if self_data.get("dropInstanceID")
                    else ""
                ),
            }

            state["total"] += 1

            if claimed:
                state["claimed"] += 1
                continue

            if current >= required:
                state["ready"].append(info)
                continue

            if linked and drop_start <= now < drop_end:
                state["mineable"].append(info)
            elif linked and now < drop_start:
                state["future"].append(info)

    for state in states.values():
        state["mineable"].sort(
            key=lambda item: (
                item["remaining"],
                item["ends_at"],
            )
        )
        state["ready"].sort(key=lambda item: item["ends_at"])
        state["future"].sort(key=lambda item: item["starts_at"])
        state["finished"] = (
            state["total"] > 0
            and state["claimed"] >= state["total"]
        )

    return states


async def claim_one(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    claim_id: str,
) -> tuple[bool, str]:
    operation = GQL_QUERIES["ClaimDrop"].with_variables(
        {"input": {"dropInstanceID": claim_id}}
    )

    response = await gql_request_retry(session, operation, headers)
    data = response.get("data", {})
    claim_data = data.get("claimDropRewards") or {}
    status = str(claim_data.get("status") or "UNKNOWN")

    return (
        status in (
            "ELIGIBLE_FOR_ALL",
            "DROP_INSTANCE_ALREADY_CLAIMED",
        ),
        status,
    )


async def claim_ready_drops(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    user_id: str,
    campaigns: list[dict[str, Any]],
    inventory_drops: dict[tuple[str, str], dict[str, Any]],
) -> list[str]:
    now = datetime.now(timezone.utc)
    messages: list[str] = []

    for campaign in campaigns:
        campaign_id = str(campaign.get("id") or "")
        game_name = campaign_game_name(campaign)
        campaign_end = parse_time(
            campaign.get("endAt"),
            datetime.max.replace(tzinfo=timezone.utc),
        )

        if now >= campaign_end + timedelta(hours=24):
            continue

        for drop in campaign.get("timeBasedDrops") or []:
            required = int(drop.get("requiredMinutesWatched") or 0)
            if required <= 0:
                continue

            drop_id = str(drop.get("id") or "")
            self_data = drop_self_data(
                campaign_id,
                drop,
                inventory_drops,
            )

            current = int(
                self_data.get("currentMinutesWatched") or 0
            )
            claimed = bool(self_data.get("isClaimed"))

            if claimed or current < required:
                continue

            claim_id = str(
                self_data.get("dropInstanceID")
                or f"{user_id}#{campaign_id}#{drop_id}"
            )

            try:
                success, status = await claim_one(
                    session,
                    headers,
                    claim_id,
                )
            except Exception as error:
                messages.append(
                    f"{game_name}: claim помилка {str(error)[:35]}"
                )
                continue

            drop_name = str(drop.get("name") or "Drop")

            if success:
                messages.append(
                    f"✅ {game_name}: {drop_name}"
                )
            else:
                messages.append(
                    f"⚠ {game_name}: {drop_name} ({status})"
                )

    return messages


async def fetch_channels_retry(
    game: str,
    *,
    attempts: int = 4,
) -> list[dict[str, Any]]:
    last_error: Exception | None = None

    for attempt in range(attempts):
        try:
            _, channels = await fetch_channels(
                game,
                verbose=False,
            )
            return channels
        except Exception as error:
            last_error = error

            if attempt >= attempts - 1:
                break

            delay = GQL_RETRY_DELAYS[
                min(attempt, len(GQL_RETRY_DELAYS) - 1)
            ]
            await asyncio.sleep(delay)

    if last_error is not None:
        raise last_error

    return []


def extract_live_streamer_channel(
    response: dict[str, Any],
    requested_login: str,
) -> dict[str, Any] | None:
    """Convert GetStreamInfo into the channel shape used by send_watch()."""
    data = response.get("data")
    if not isinstance(data, dict):
        return None

    direct_user = data.get("user")
    candidates: list[dict[str, Any]] = []
    if isinstance(direct_user, dict):
        candidates.append(direct_user)

    candidates.extend(
        item
        for item in walk_dicts(data)
        if isinstance(item, dict) and item is not direct_user
    )

    wanted = requested_login.casefold()

    for user in candidates:
        login = str(user.get("login") or "").strip()
        channel_id = str(user.get("id") or "").strip()
        stream = user.get("stream")

        if not login or not channel_id or not isinstance(stream, dict):
            continue
        if wanted and login.casefold() != wanted:
            continue

        stream_id = str(stream.get("id") or "").strip()
        if not stream_id:
            continue

        settings = user.get("broadcastSettings")
        if not isinstance(settings, dict):
            settings = {}

        game_data = settings.get("game")
        if not isinstance(game_data, dict):
            game_data = stream.get("game")
        if not isinstance(game_data, dict):
            game_data = {}

        try:
            viewers = int(stream.get("viewersCount") or 0)
        except (TypeError, ValueError):
            viewers = 0

        game_name = str(
            game_data.get("name")
            or game_data.get("displayName")
            or "Без категорії"
        )

        return {
            "stream_id": stream_id,
            "channel_id": channel_id,
            "login": login,
            "display_name": str(user.get("displayName") or login),
            "game": game_name,
            "game_id": str(game_data.get("id") or ""),
            "viewers": viewers,
            "title": str(
                settings.get("title")
                or stream.get("title")
                or "Без назви"
            ),
        }

    return None


async def fetch_streamer_channel(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    login: str,
) -> dict[str, Any] | None:
    operation = GQL_QUERIES["GetStreamInfo"].with_variables(
        {"channel": login}
    )
    response = await gql_request_retry(
        session,
        operation,
        headers,
        attempts=2,
    )
    return extract_live_streamer_channel(response, login)


async def pick_streamer_target(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    streamer_logins: list[str],
) -> dict[str, Any] | None:
    """Return the first online streamer in user-defined priority order."""
    for index, login in enumerate(streamer_logins):
        try:
            channel = await fetch_streamer_channel(
                session,
                headers,
                login,
            )
        except Exception:
            channel = None

        if channel is not None:
            return channel

        if index < len(streamer_logins) - 1:
            await asyncio.sleep(STREAMER_CHECK_DELAY)

    return None


def watch_mode_text(mode: str) -> str:
    if mode == "drops":
        return "Drops"
    if mode == "points":
        return "Channel Points"
    return "—"


async def pick_target(
    priority_games: list[str],
    states: dict[str, dict[str, Any]],
    preferred: dict[str, str],
    streamer_logins: list[str],
    current_game: str,
    current_login: str,
) -> tuple[str, dict[str, Any]] | None:
    for game in priority_games:
        state = states.get(game)

        if not state or not state.get("mineable"):
            continue

        try:
            channels = await fetch_channels_retry(game)
        except Exception:
            continue

        if not channels:
            continue

        channel = None

        if streamer_logins:
            channels_by_login = {
                str(item.get("login") or "").casefold(): item
                for item in channels
                if isinstance(item, dict) and item.get("login")
            }

            for configured_login in streamer_logins:
                channel = channels_by_login.get(configured_login.casefold())
                if channel is not None:
                    break

        if channel is None:
            channel = select_best_channel(
                channels,
                preferred.get(game, ""),
                current_login if current_game == game else "",
            )

        if channel is not None:
            return game, channel

    return None


def queue_text(
    priority_games: list[str],
    states: dict[str, dict[str, Any]],
    current_game: str,
) -> str:
    parts: list[str] = []

    for game in priority_games:
        state = states.get(game)

        if game == current_game:
            prefix = "▶"
        elif state and state.get("finished"):
            prefix = "✓"
        elif state and not state.get("linked"):
            prefix = "!"
        else:
            prefix = "•"

        parts.append(f"{prefix} {game}")

    return "  ".join(parts)


def active_drop_text(
    state: dict[str, Any] | None,
) -> str:
    if not state:
        return "—"

    mineable = state.get("mineable") or []
    if mineable:
        drop = mineable[0]
        return (
            f"{drop['drop']} — "
            f"{drop['current']}/{drop['required']} хв"
        )

    ready = state.get("ready") or []
    if ready:
        return f"{ready[0]['drop']} — очікує claim"

    if state.get("finished"):
        return "усі Drops отримано"

    if not state.get("linked"):
        return "акаунт гри не прив'язаний"

    future = state.get("future") or []
    if future:
        return "наступний Drop ще не стартував"

    return "немає доступного Drop"


def apply_rewards_snapshot(
    state: dict[str, Any],
    snapshot: dict[str, str],
) -> None:
    state["points_bonus"] = snapshot.get("bonus", "очікування")
    state["points_streak"] = snapshot.get("streak", "—")
    state["points_moments"] = snapshot.get("moments", "0")
    state["points_raid"] = snapshot.get("raid", "—")
    state["points_prediction"] = snapshot.get("prediction", "вимкнено")
    state["points_pubsub"] = snapshot.get("pubsub", "очікування")


def render_status(state: dict[str, Any]) -> Panel:
    grid = Table.grid(padding=(0, 1), expand=True)
    grid.add_column(style="yellow", no_wrap=True)
    grid.add_column()

    http_status = state.get("http_status")
    if state.get("success"):
        send_text = f"[green]✓ HTTP {http_status}[/green]"
    elif http_status is None:
        send_text = "[dim]ще не надсилалось[/dim]"
    else:
        send_text = f"[red]✗ HTTP {http_status or 'помилка'}[/red]"

    grid.add_row("Акаунт:", f"[bold]{escape(str(state['account']))}[/bold]")
    grid.add_row("Ігри:", escape(str(state.get("queue", "—"))))
    grid.add_row("Режим:", escape(watch_mode_text(str(state.get("mode") or ""))))
    grid.add_row("Гра:", f"[cyan]{escape(str(state.get('game', '—')))}[/cyan]")
    grid.add_row("Канал:", f"[bold cyan]{escape(str(state.get('channel', '—')))}[/bold cyan]")
    grid.add_row("Channel Points:", f"[bold magenta]{escape(str(state.get('points', '—')))}[/bold magenta]")
    grid.add_row("За сесію:", escape(str(state.get('points_session', '—'))))
    grid.add_row("Бонус:", escape(str(state.get('points_bonus', '—'))))
    grid.add_row("Watch Streak:", escape(str(state.get('points_streak', '—'))))
    grid.add_row("Moments:", escape(str(state.get('points_moments', '0'))))
    grid.add_row("Рейд:", escape(str(state.get('points_raid', '—'))))
    grid.add_row("Prediction:", escape(str(state.get('points_prediction', 'вимкнено'))))
    grid.add_row("PubSub:", escape(str(state.get('points_pubsub', 'очікування'))))
    grid.add_row("Плеєр:", escape(str(state.get("player", "—"))))
    grid.add_row("Drop:", escape(str(state.get("drop", "—"))))
    grid.add_row("Надсилання:", send_text)
    grid.add_row("Циклів:", str(state.get("cycles", 0)))
    grid.add_row("Claim:", escape(str(state.get("claim", "—"))))
    grid.add_row("Наступна дія:", f"{state.get('remaining', 0)} с")
    grid.add_row("Стан:", escape(str(state.get("message", "Підготовка"))))

    return Panel(
        grid,
        title="⛏ NYXOR — GAMES + STREAMERS",
        border_style="green" if state.get("success") else "cyan",
    )


async def wait_live(
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
        await asyncio.sleep(min(1.0, remaining))


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


async def main() -> None:
    settings = load_settings()
    priority_games = load_priority_games(settings)
    streamer_logins = load_streamer_channels(settings)

    if not priority_games and not streamer_logins:
        raise RuntimeError(
            "Списки ігор і стримерів порожні. "
            "Додай хоча б одну гру або Twitch-канал у NYXOR."
        )

    preferred = preferred_channels(settings)
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
        raise RuntimeError("У cookies.jar немає auth-token")

    timeout = aiohttp.ClientTimeout(sock_connect=20, total=40)

    async with aiohttp.ClientSession(
        timeout=timeout,
        cookie_jar=jar,
        headers={"User-Agent": client.USER_AGENT},
    ) as session:
        account = await validate_account(session, token)
        account_login = str(account.get("login") or "невідомо")
        user_id = str(account.get("user_id") or "")

        if not user_id:
            raise RuntimeError("Twitch не повернув User ID")

        gql_headers = build_gql_headers(
            client,
            token,
            device_id,
        )

        points_settings = settings.get("channel_points") or {}
        points_enabled = bool(points_settings.get("enabled", True))
        points_auto_claim = bool(
            points_settings.get("auto_claim_bonus", True)
        )
        points_tracker = ChannelPointsTracker()
        rewards = TwitchRewardsEngine(
            session,
            gql_headers,
            auth_token=token,
            user_id=user_id,
            tracker=points_tracker,
            settings=points_settings,
        )

        state: dict[str, Any] = {
            "account": account_login,
            "queue": "  ".join(priority_games),
            "mode": "",
            "game": "—",
            "channel": "—",
            "points": "—" if points_enabled else "вимкнено",
            "points_balance_value": 0,
            "points_goal_title": "",
            "points_goal_cost": 0,
            "points_session": "—",
            "points_bonus": "очікування",
            "points_streak": "—",
            "points_moments": "0",
            "points_raid": "—",
            "points_prediction": (
                "очікування"
                if rewards.prediction.enabled
                else "вимкнено"
            ),
            "points_pubsub": "очікування",
            "player": "—",
            "player_http_status": None,
            "drop": "—",
            "success": False,
            "http_status": None,
            "cycles": 0,
            "claim": "—",
            "remaining": 0,
            "message": "Завантажую кампанії...",
        }

        current_mode = ""
        current_game = ""
        current_channel: dict[str, Any] | None = None
        spade_url = ""
        states: dict[str, dict[str, Any]] = {}
        raid_override_login = ""
        raid_override_misses = 0
        player = TwitchHLSPlayer(
            session,
            gql_headers,
            user_agent=client.USER_AGENT,
        )
        await player.start()

        run_termux_command("termux-wake-lock")

        try:
            with Live(
                render_status(state),
                console=console,
                refresh_per_second=2,
            ) as live:
                while True:
                    cycle_started = time.monotonic()

                    state["message"] = "Оновлюю кампанії та claim..."
                    live.update(render_status(state))

                    try:
                        if priority_games:
                            campaigns, inventory_drops, claimed_benefits = (
                                await fetch_campaign_snapshot(
                                    session,
                                    gql_headers,
                                    user_id,
                                    priority_games,
                                )
                            )

                            claim_messages = await claim_ready_drops(
                                session,
                                gql_headers,
                                user_id,
                                campaigns,
                                inventory_drops,
                            )

                            if claim_messages:
                                state["claim"] = claim_messages[-1]

                                # Після claim перечитуємо стан, щоб відкрити наступний Drop.
                                campaigns, inventory_drops, claimed_benefits = (
                                    await fetch_campaign_snapshot(
                                        session,
                                        gql_headers,
                                        user_id,
                                        priority_games,
                                    )
                                )

                            states = build_game_states(
                                campaigns,
                                inventory_drops,
                                claimed_benefits,
                            )
                        else:
                            states = {}

                        state["queue"] = queue_text(
                            priority_games,
                            states,
                            current_game if current_mode == "drops" else "",
                        )

                        drop_target = await pick_target(
                            priority_games,
                            states,
                            preferred,
                            streamer_logins,
                            current_game if current_mode == "drops" else "",
                            (
                                str(current_channel.get("login") or "")
                                if current_channel and current_mode == "drops"
                                else ""
                            ),
                        )

                        if drop_target is not None:
                            # Drops always win over raids and ordinary point farming.
                            raid_override_login = ""
                            raid_override_misses = 0
                            drop_game, drop_channel = drop_target
                            target = ("drops", drop_game, drop_channel)
                        else:
                            new_raid_login = rewards.consume_raid_target()
                            if new_raid_login:
                                raid_override_login = new_raid_login
                                raid_override_misses = 0

                            points_channel = None
                            if raid_override_login:
                                try:
                                    points_channel = await fetch_streamer_channel(
                                        session,
                                        gql_headers,
                                        raid_override_login,
                                    )
                                except Exception:
                                    points_channel = None

                                if points_channel is None:
                                    raid_override_misses += 1
                                    if raid_override_misses >= 3:
                                        raid_override_login = ""
                                        raid_override_misses = 0
                                else:
                                    raid_override_misses = 0

                            if points_channel is None:
                                points_channel = await pick_streamer_target(
                                    session,
                                    gql_headers,
                                    streamer_logins,
                                )

                            if points_channel is None:
                                target = None
                            else:
                                target = (
                                    "points",
                                    str(points_channel.get("game") or "Без категорії"),
                                    points_channel,
                                )

                    except Exception as error:
                        # Twitch GQL / persisted queries іноді тимчасово падають.
                        # Не завершуємо майнер: якщо канал уже є, продовжуємо
                        # надсилати minute-watched зі старим станом.
                        error_text = str(error).replace("\n", " ")
                        if len(error_text) > 90:
                            error_text = error_text[:87] + "..."

                        state["message"] = (
                            "Twitch GQL тимчасово недоступний; "
                            f"повторю через цикл: {error_text}"
                        )
                        live.update(render_status(state))

                        if current_channel is None or not current_game or not spade_url:
                            await wait_live(
                                GQL_FAILURE_WAIT,
                                live,
                                state,
                            )
                            continue

                        target = (current_mode, current_game, current_channel)

                    if target is None:
                        current_mode = ""
                        current_game = ""
                        current_channel = None
                        spade_url = ""
                        await player.clear()
                        await rewards.set_channel(None, "")
                        apply_rewards_snapshot(state, rewards.snapshot())

                        state["mode"] = ""
                        state["game"] = "—"
                        state["channel"] = "—"
                        state["player"] = "—"
                        state["points_balance_value"] = 0
                        state["points_goal_title"] = ""
                        state["points_goal_cost"] = 0
                        state["drop"] = "Немає доступного Drop/каналу"
                        state["success"] = False
                        state["http_status"] = None
                        state["message"] = (
                            "Чекаю нові Drops або онлайн-стримера"
                        )

                        await wait_live(
                            NO_TARGET_RETRY,
                            live,
                            state,
                        )
                        continue

                    target_mode, target_game, target_channel = target

                    changed = (
                        current_channel is None
                        or current_game != target_game
                        or str(current_channel.get("stream_id"))
                        != str(target_channel.get("stream_id"))
                    )

                    if changed:
                        if target_mode == "drops":
                            state["message"] = (
                                f"Знайдено Drops. Перемикаюся на {target_game}..."
                            )
                        else:
                            state["message"] = (
                                "Активних Drops немає. "
                                f"Переходжу до {target_channel.get('login') or 'стримера'}..."
                            )
                        live.update(render_status(state))

                        spade_url = await get_spade_url(
                            session,
                            str(target_channel["login"]),
                        )

                        current_game = target_game
                        current_channel = target_channel
                        state["points_balance_value"] = 0
                        state["points_goal_title"] = ""
                        state["points_goal_cost"] = 0

                    current_mode = target_mode
                    current_game = target_game
                    current_channel = target_channel

                    current_state = (
                        states.get(current_game)
                        if current_mode == "drops"
                        else None
                    )
                    state["queue"] = queue_text(
                        priority_games,
                        states,
                        current_game if current_mode == "drops" else "",
                    )
                    state["mode"] = current_mode
                    state["game"] = current_game
                    state["channel"] = str(
                        current_channel.get("display_name")
                        or current_channel.get("login")
                        or "Невідомий канал"
                    )
                    state["viewers"] = int(current_channel.get("viewers") or 0)

                    channel_login = str(current_channel.get("login") or "")
                    await rewards.set_channel(current_channel, current_mode)
                    apply_rewards_snapshot(state, rewards.snapshot())
                    state["message"] = "Активую Twitch HLS-плеєр..."
                    live.update(render_status(state))

                    playback = await player.ensure_active(
                        channel_login,
                        timeout=30,
                    )
                    state["player"] = playback.display_text()
                    state["player_http_status"] = playback.http_status

                    if current_mode == "drops":
                        state["drop"] = active_drop_text(current_state)
                        state["message"] = "Надсилаю minute-watched для Drops..."
                    else:
                        state["drop"] = (
                            "Активних Drops немає — фармлю Channel Points"
                        )
                        state["message"] = (
                            "Надсилаю minute-watched для Channel Points..."
                        )
                    live.update(render_status(state))

                    success, http_status = await send_watch(
                        session,
                        spade_url,
                        current_channel,
                        user_id,
                    )

                    state["success"] = success
                    state["http_status"] = http_status
                    state["cycles"] += 1

                    if points_enabled:
                        try:
                            points_result = await update_channel_points(
                                session,
                                gql_headers,
                                login=channel_login,
                                channel_id=str(current_channel.get("channel_id") or ""),
                                tracker=points_tracker,
                                auto_claim=points_auto_claim,
                            )
                            state["points"] = f"{points_result.balance:,}".replace(",", " ")
                            state["points_balance_value"] = points_result.balance
                            state["points_goal_title"] = (
                                points_result.reward_title or ""
                            )
                            state["points_goal_cost"] = (
                                points_result.reward_cost or 0
                            )
                            delta = points_result.session_delta
                            delta_prefix = "+" if delta >= 0 else ""
                            state["points_session"] = (
                                f"{delta_prefix}{delta:,}".replace(",", " ")
                            )
                            state["points_bonus"] = points_result.bonus_status
                        except Exception as error:
                            state["points_bonus"] = f"помилка: {str(error)[:42]}"
                            logger.debug(
                                "Channel Points refresh failed: %s",
                                error,
                                exc_info=True,
                            )

                    apply_rewards_snapshot(state, rewards.snapshot())

                    if playback.active and success:
                        state["message"] = "HLS активний; пакет прийнято Twitch"
                    elif success:
                        state["message"] = (
                            "Пакет прийнято, але HLS ще не активний"
                        )
                    else:
                        state["message"] = "Пакет не прийнято; перевірю канал"

                    live.update(render_status(state))

                    elapsed = time.monotonic() - cycle_started
                    await wait_live(
                        WATCH_INTERVAL - elapsed,
                        live,
                        state,
                    )

        finally:
            await rewards.stop()
            await player.stop()
            run_termux_command("termux-wake-unlock")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]⏹ Майнер зупинено[/yellow]")
    except Exception as error:
        console.print(
            f"\n[bold red]❌ Помилка:[/bold red] {error}"
        )
        raise SystemExit(1)
