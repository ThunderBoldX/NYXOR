from __future__ import annotations

import asyncio
import shutil
import subprocess
import time

import aiohttp

from constants import COOKIES_PATH, ClientType
import secrets


async def login() -> None:
    client = ClientType.ANDROID_APP
    jar = aiohttp.CookieJar()

    timeout = aiohttp.ClientTimeout(
        sock_connect=20,
        total=30,
    )

    async with aiohttp.ClientSession(
        cookie_jar=jar,
        timeout=timeout,
        headers={"User-Agent": client.USER_AGENT},
    ) as session:

        print("🔗 Підключення до Twitch...")

        # Twitch створює службовий unique_id.
        async with session.get(client.CLIENT_URL) as response:
            response.raise_for_status()
            await response.read()

        cookies = jar.filter_cookies(client.CLIENT_URL)

        if "unique_id" in cookies:
            device_id = cookies["unique_id"].value
        else:
            device_id = secrets.token_hex(16)

        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Accept-Language": "en-US",
            "Cache-Control": "no-cache",
            "Client-Id": client.CLIENT_ID,
            "Origin": str(client.CLIENT_URL),
            "Pragma": "no-cache",
            "Referer": str(client.CLIENT_URL),
            "User-Agent": client.USER_AGENT,
            "X-Device-Id": device_id,
        }

        payload = {
            "client_id": client.CLIENT_ID,
            "scopes": "",
        }

        async with session.post(
            "https://id.twitch.tv/oauth2/device",
            headers=headers,
            data=payload,
        ) as response:
            response.raise_for_status()
            device_data = await response.json()

        device_code = device_data["device_code"]
        user_code = device_data["user_code"]
        verification_uri = device_data["verification_uri"]
        interval = int(device_data.get("interval", 5))
        expires_in = int(device_data.get("expires_in", 1800))

        print()
        print("╭──────────── Авторизація Twitch ────────────╮")
        print(f"│ Код: {user_code:<36}│")
        print("╰────────────────────────────────────────────╯")
        print()
        print("Відкрий сторінку Twitch і підтвердь цей код.")
        print(f"Посилання: {verification_uri}")
        print()

        # Спробувати автоматично відкрити браузер Android.
        if shutil.which("termux-open-url"):
            subprocess.run(
                ["termux-open-url", verification_uri],
                check=False,
            )
            print("🌐 Сторінку активації відкрито у браузері.")
        else:
            print("⚠️ Автоматично відкрити браузер не вдалося.")

        print("⏳ Чекаю підтвердження входу...")

        token_payload = {
            "client_id": client.CLIENT_ID,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

        deadline = time.monotonic() + expires_in
        access_token: str | None = None

        while time.monotonic() < deadline:
            await asyncio.sleep(interval)

            async with session.post(
                "https://id.twitch.tv/oauth2/token",
                headers=headers,
                data=token_payload,
            ) as response:

                if response.status == 200:
                    token_data = await response.json()
                    access_token = token_data["access_token"]
                    break

                # 400 зазвичай означає, що користувач ще не підтвердив код.
                if response.status == 400:
                    continue

                error_text = await response.text()
                raise RuntimeError(
                    f"Помилка отримання токена: "
                    f"HTTP {response.status}: {error_text}"
                )

        if access_token is None:
            raise TimeoutError(
                "Час дії коду завершився. Запусти авторизацію ще раз."
            )

        # Перевірка токена та отримання ID користувача.
        async with session.get(
            "https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": f"OAuth {access_token}"},
        ) as response:
            response.raise_for_status()
            validation = await response.json()

        if validation.get("client_id") != client.CLIENT_ID:
            raise RuntimeError("Client ID отриманого токена не збігається.")

        user_id = str(validation["user_id"])
        login_name = validation.get("login", "невідомо")

        cookies = jar.filter_cookies(client.CLIENT_URL)
        cookies["auth-token"] = access_token
        cookies["persistent"] = user_id

        jar.update_cookies(cookies, client.CLIENT_URL)
        jar.save(COOKIES_PATH)

        print()
        print("✅ Авторизація успішна!")
        print(f"👤 Акаунт: {login_name}")
        print(f"🆔 User ID: {user_id}")
        print(f"💾 Сесію збережено: {COOKIES_PATH}")


def main() -> None:
    try:
        asyncio.run(login())
    except KeyboardInterrupt:
        print("\n❌ Авторизацію скасовано.")
    except Exception as error:
        print(f"\n❌ Помилка: {error}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
