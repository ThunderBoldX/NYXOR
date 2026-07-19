from __future__ import annotations

import argparse
import asyncio
import secrets
import time
from datetime import datetime

import aiohttp

from constants import COOKIES_PATH, ClientType
from nyxor_campaigns import get_cookie_value
from nyxor_core import fetch_streamer_channel
from nyxor_channels import load_settings
from nyxor_miner import (
    build_gql_headers,
    get_spade_url,
    send_watch,
    validate_account,
)
from nyxor_player import TwitchHLSPlayer
from nyxor_points import ChannelPointsTracker, update_channel_points
from nyxor_rewards import TwitchRewardsEngine


async def run_probe(login: str, minutes: int) -> int:
    login = login.strip().lower()
    if not login:
        print("✗ Не передано логін стримера")
        return 2

    if not COOKIES_PATH.exists():
        print(f"✗ Не знайдено {COOKIES_PATH}")
        return 2

    client = ClientType.ANDROID_APP
    jar = aiohttp.CookieJar()
    jar.load(COOKIES_PATH)
    cookies = jar.filter_cookies(client.CLIENT_URL)

    token = get_cookie_value(cookies, "auth-token")
    device_id = get_cookie_value(cookies, "unique_id") or secrets.token_hex(16)

    if not token:
        print("✗ У cookies.jar немає auth-token")
        return 2

    timeout = aiohttp.ClientTimeout(sock_connect=20, total=40)

    async with aiohttp.ClientSession(
        timeout=timeout,
        cookie_jar=jar,
        headers={"User-Agent": client.USER_AGENT},
    ) as session:
        account = await validate_account(session, token)
        user_id = str(account.get("user_id") or "")
        account_login = str(account.get("login") or "—")

        gql_headers = build_gql_headers(client, token, device_id)
        channel = await fetch_streamer_channel(session, gql_headers, login)

        if channel is None:
            print(f"✗ Канал {login} зараз офлайн або недоступний")
            return 1

        spade_url = await get_spade_url(session, login)
        tracker = ChannelPointsTracker()
        settings = load_settings()
        points_settings = settings.get("channel_points")
        if not isinstance(points_settings, dict):
            points_settings = {}
        else:
            points_settings = dict(points_settings)

        # The diagnostic must never spend points or follow a raid.
        points_settings["follow_raids"] = False
        prediction_settings = points_settings.get("predictions")
        if not isinstance(prediction_settings, dict):
            prediction_settings = {}
        else:
            prediction_settings = dict(prediction_settings)
        prediction_settings["enabled"] = False
        points_settings["predictions"] = prediction_settings

        rewards = TwitchRewardsEngine(
            session,
            gql_headers,
            auth_token=token,
            user_id=user_id,
            tracker=tracker,
            settings=points_settings,
        )
        await rewards.set_channel(channel, "points")

        player = TwitchHLSPlayer(
            session,
            gql_headers,
            user_agent=client.USER_AGENT,
            pulse_interval=20,
        )
        await player.start()

        print(f"Акаунт: {account_login}")
        print(f"Канал: {login}")
        print(f"Тривалість тесту: {minutes} хв")
        print("Інтервал: 20 секунд")
        print()

        try:
            first = await update_channel_points(
                session,
                gql_headers,
                login=login,
                channel_id=str(channel.get("channel_id") or ""),
                tracker=tracker,
                auto_claim=True,
            )
            initial_balance = first.balance
            print(f"Початковий баланс: {initial_balance}")

            deadline = time.monotonic() + minutes * 60
            cycle = 0

            while time.monotonic() < deadline:
                cycle += 1
                playback = await player.ensure_active(
                    login,
                    timeout=30,
                    max_age=25,
                )

                success, status = await send_watch(
                    session,
                    spade_url,
                    channel,
                    user_id,
                )

                try:
                    result = await update_channel_points(
                        session,
                        gql_headers,
                        login=login,
                        channel_id=str(channel.get("channel_id") or ""),
                        tracker=tracker,
                        auto_claim=True,
                    )
                    balance_text = str(result.balance)
                    delta_text = (
                        f"+{result.session_delta}"
                        if result.session_delta >= 0
                        else str(result.session_delta)
                    )
                    bonus_text = result.bonus_status
                except Exception as error:
                    balance_text = "?"
                    delta_text = "?"
                    bonus_text = f"помилка: {str(error)[:50]}"

                now = datetime.now().strftime("%H:%M:%S")
                hls = (
                    f"OK {playback.quality}"
                    if playback.active
                    else f"FAIL {playback.detail}"
                )
                spade = f"HTTP {status}" if success else f"FAIL {status}"

                rewards_state = rewards.snapshot()
                bonus_text = rewards_state.get("bonus") or bonus_text
                print(
                    f"[{now}] #{cycle:02d} "
                    f"HLS={hls} | Spade={spade} | "
                    f"Points={balance_text} ({delta_text}) | "
                    f"Bonus={bonus_text} | "
                    f"Streak={rewards_state.get('streak')} | "
                    f"Moments={rewards_state.get('moments')} | "
                    f"PubSub={rewards_state.get('pubsub')}"
                )

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(20, remaining))

            final = await update_channel_points(
                session,
                gql_headers,
                login=login,
                channel_id=str(channel.get("channel_id") or ""),
                tracker=tracker,
                auto_claim=True,
            )

            print()
            print(f"Фінальний баланс: {final.balance}")
            print(f"Зміна за тест: {final.balance - initial_balance}")

            if final.balance > initial_balance:
                print("✓ Twitch зараховує Channel Points")
                return 0

            print(
                "✗ Баланс не змінився. Збережи весь цей вивід — "
                "він покаже, чи проблема у HLS, Spade або crediting Twitch."
            )
            return 1

        finally:
            await rewards.stop()
            await player.stop()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Перевірка Channel Points, коробочок і PubSub"
    )
    parser.add_argument("login", help="Логін онлайн-стримера")
    parser.add_argument(
        "--minutes",
        type=int,
        default=20,
        help="Тривалість тесту, типово 20 хвилин",
    )
    args = parser.parse_args()

    minutes = max(1, min(args.minutes, 60))
    return asyncio.run(run_probe(args.login, minutes))


if __name__ == "__main__":
    raise SystemExit(main())
