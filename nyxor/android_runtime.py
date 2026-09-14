"""Embedded Android runtime. All mutations run on one asyncio event loop."""
from __future__ import annotations

import asyncio
import concurrent.futures
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

_loop = None
_thread = None
_init_lock = threading.Lock()
_miner = None
_auth_task = None
_auth = {"status": "idle"}
_error = ""
_account = ""
_last_request_error = ""


def initialize(directory: str, network=None) -> None:
    global _loop, _thread
    with _init_lock:
        if _loop is not None:
            return
        root = Path(directory)
        root.mkdir(parents=True, exist_ok=True)
        os.environ["NYXOR_DATA_DIR"] = str(root)
        os.chdir(root)
        from nyxor.paths import ensure_directories
        ensure_directories()
        from nyxor.network import configure_android
        configure_android(network)
        _loop = asyncio.new_event_loop()
        _thread = threading.Thread(target=_loop.run_forever, name="NYXOR", daemon=True)
        _thread.start()


def request(payload: str) -> str:
    if _loop is None:
        return json.dumps({"ok": False, "error": "NYXOR is starting"})
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("Invalid request")
        future = asyncio.run_coroutine_threadsafe(dispatch(data), _loop)
        result = future.result(timeout=35)
        return json.dumps({"ok": True, "data": result}, ensure_ascii=False, default=str)
    except concurrent.futures.TimeoutError:
        future.cancel()
        return json.dumps({"ok": False, "error": "Connection timed out. Please retry."})
    except Exception as error:
        return json.dumps({"ok": False, "error": str(error)[:240]}, ensure_ascii=False)


def snapshot() -> dict:
    from nyxor.network import connection_state
    from constants import COOKIES_PATH
    from nyxor.paths import STATE_PATH, HISTORY_PATH, EVENTS_PATH, STATS_PATH
    from nyxor.storage import load_json, load_jsonl, load_settings, load_queue, load_streamers
    settings = load_settings()
    result = {
        "network": connection_state(),
        "running": _miner is not None and not _miner.done(),
        "authenticated": COOKIES_PATH.exists(), "account": _account,
        "auth": dict(_auth), "error": _error,
        "state": load_json(STATE_PATH, {}), "stats": load_json(STATS_PATH, {}),
        "queue": load_queue(), "streamers": load_streamers(),
        "points_games": settings.get("points_games", []),
        "history": load_jsonl(HISTORY_PATH, 100)[::-1],
        "events": load_jsonl(EVENTS_PATH, 60)[::-1],
        "settings": {"language": settings.get("language", "uk"),
                     "launch_on_boot": settings.get("launch_on_boot", False),
                     "points_order": settings.get("points_order", "popular"),
                     "auto_restart": settings.get("auto_restart", True),
                     "channel_points": settings.get("channel_points", {})},
    }
    from nyxor.android_status import notification_status
    result["notification"] = notification_status(result)
    result["watched"] = account_history()
    return result


def account_history():
    from constants import COOKIES_PATH, ClientType
    from nyxor.channel_history import read_history
    import aiohttp
    if not COOKIES_PATH.exists():
        return []
    try:
        jar = aiohttp.CookieJar()
        jar.load(COOKIES_PATH)
        cookie = jar.filter_cookies(ClientType.ANDROID_APP.CLIENT_URL).get("persistent")
        return read_history(cookie.value) if cookie else []
    except Exception:
        return []


async def mine() -> None:
    global _error
    from nyxor.worker import runtime as worker
    from nyxor.storage import load_settings
    # Android supplies the foreground service, wake lock and notification.
    worker.core.run_termux_command = lambda command: None
    worker.send_notification = lambda *args, **kwargs: None
    worker.poll_device = lambda: None
    worker.SESSION_STARTED_MONOTONIC = time.monotonic()
    worker.update_stats(starts=1)
    attempt = 0
    try:
        while True:
            try:
                from nyxor.network import connection_blocker
                if connection_blocker():
                    worker.write_state(running=True, message="Очікуємо інтернет")
                    await asyncio.sleep(5)
                    continue
                _error = ""
                worker.write_state(running=True, message="NYXOR працює")
                await worker.core.main()
                break
            except asyncio.CancelledError:
                raise
            except Exception as error:
                _error = str(error)[:200]
                worker.add_event("error", _error)
                if worker.should_stop_retrying(error) or not load_settings().get("auto_restart", True):
                    break
                attempt += 1
                worker.update_stats(restarts=1)
                worker.write_state(running=True, error=_error, message="Повторне підключення…")
                await asyncio.sleep(min(30 * attempt, 300))
    finally:
        worker.write_state(running=False, error=_error or None, message="NYXOR зупинено")


async def stop() -> None:
    global _miner
    if _miner is not None and not _miner.done():
        _miner.cancel()
        try:
            await _miner
        except asyncio.CancelledError:
            pass
    _miner = None


async def authenticate() -> None:
    global _auth, _account
    import aiohttp
    from nyxor.network import client_session, connection_blocker
    from constants import COOKIES_PATH, ClientType
    from yarl import URL
    client = ClientType.ANDROID_APP
    _auth = {"status": "connecting"}
    blocked = connection_blocker()
    if blocked:
        _auth = {"status": "error", "error_code": blocked, "message": ""}
        return
    jar = aiohttp.CookieJar()
    try:
        async with client_session(cookie_jar=jar, timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post("https://id.twitch.tv/oauth2/device", data={"client_id": client.CLIENT_ID, "scopes": ""}) as response:
                response.raise_for_status()
                data = await response.json()
            verification = str(data["verification_uri"])
            if URL(verification).host != "www.twitch.tv" and URL(verification).host != "twitch.tv":
                raise RuntimeError("Unexpected Twitch verification address")
            interval = max(5, int(data.get("interval", 5)))
            expires = max(1, int(data.get("expires_in", 1800)))
            _auth = {"status": "pending", "code": data["user_code"], "url": verification,
                     "expires_at": time.time() + expires}
            deadline = time.monotonic() + expires
            while time.monotonic() < deadline:
                await asyncio.sleep(interval)
                async with session.post("https://id.twitch.tv/oauth2/token", data={
                    "client_id": client.CLIENT_ID, "device_code": data["device_code"],
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                }) as response:
                    result = await response.json()
                    if response.status == 200:
                        token = result["access_token"]
                        break
                    reason = str(result.get("message") or result.get("error") or "")
                    if "slow_down" in reason:
                        interval += 5
                    elif "authorization_pending" not in reason:
                        raise RuntimeError("Twitch відхилив або прострочив код. Спробуй ще раз.")
            else:
                raise RuntimeError("Час дії коду минув. Спробуй ще раз.")
            async with session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {token}"}) as response:
                response.raise_for_status()
                validation = await response.json()
            if validation.get("client_id") != client.CLIENT_ID or not validation.get("user_id"):
                raise RuntimeError("Twitch не підтвердив акаунт")
            jar.update_cookies({"auth-token": token, "persistent": str(validation["user_id"]),
                                "unique_id": secrets.token_hex(16)}, client.CLIENT_URL)
            jar.save(COOKIES_PATH)
            _account = str(validation.get("login") or "")
            _auth = {"status": "connected"}
    except asyncio.CancelledError:
        _auth = {"status": "idle"}
        raise
    except Exception as error:
        from nyxor.network import error_code
        code = error_code(error)
        _auth = {"status": "error", "error_code": code,
                 "message": "" if code else str(error)[:160]}


async def dispatch(data: dict):
    global _miner, _auth_task, _auth, _error, _account
    from constants import COOKIES_PATH
    from nyxor.storage import load_queue, load_streamers, save_queue, save_streamers, load_settings, save_settings
    action = data.get("action", "snapshot")
    if action == "snapshot":
        return snapshot()
    if action == "check_connection":
        from nyxor.network import check_connection
        return await check_connection()
    if action == "start":
        if not COOKIES_PATH.exists():
            raise ValueError("Спочатку підключи Twitch у налаштуваннях")
        if not load_queue() and not load_streamers() and not load_settings().get("points_games"):
            raise ValueError("Додай гру або стрімера")
        if _miner is None or _miner.done():
            _error = ""
            _miner = asyncio.create_task(mine())
    elif action == "stop":
        await stop()
    elif action == "auth":
        if _miner is not None and not _miner.done():
            raise ValueError("Зупини фарм перед зміною акаунта")
        if _auth_task is None or _auth_task.done():
            _auth_task = asyncio.create_task(authenticate())
            await asyncio.sleep(0)
    elif action == "logout":
        await stop()
        if _auth_task is not None and not _auth_task.done():
            _auth_task.cancel()
            try:
                await _auth_task
            except asyncio.CancelledError:
                pass
        COOKIES_PATH.unlink(missing_ok=True)
        from nyxor.paths import STATE_PATH
        from nyxor.storage import atomic_write_json
        atomic_write_json(STATE_PATH, {})
        _auth, _account = {"status": "idle"}, ""
    elif action in {"queue", "streamers", "points_games"}:
        items = data.get("items")
        if not isinstance(items, list) or len(items) > 100:
            raise ValueError("Invalid list")
        if any(not isinstance(item, str) or not item.strip() or len(item) > 160 for item in items):
            raise ValueError("Invalid name")
        items = list(dict.fromkeys(item.strip() for item in items))
        if action == "streamers" and any(not re.fullmatch(r"[A-Za-z0-9_]{1,25}", item) for item in items):
            raise ValueError("Введи Twitch-логін без пробілів")
        if action == "points_games":
            settings = load_settings()
            settings["points_games"] = items
            save_settings(settings)
        else:
            (save_queue if action == "queue" else save_streamers)(items)
    elif action == "settings":
        settings = load_settings()
        changes = data.get("values")
        if not isinstance(changes, dict):
            raise ValueError("Invalid settings")
        for key, value in changes.items():
            if key == "language" and value in {"uk", "en"}:
                settings[key] = value
                os.environ["NYXOR_LANG"] = value
            elif key in {"auto_restart", "launch_on_boot"} and isinstance(value, bool):
                settings[key] = value
            elif key == "points_order" and value in {"popular", "quiet"}:
                settings[key] = value
            elif key in {"enabled", "auto_claim_bonus", "follow_raids", "claim_moments"} and isinstance(value, bool):
                settings.setdefault("channel_points", {})[key] = value
            else:
                raise ValueError("Unsupported setting")
        save_settings(settings)
    elif action == "directory":
        from nyxor.game_search import _load_twitch_token
        from nyxor.points_selection import category_channels
        from nyxor.network import client_session
        import aiohttp
        game = str(data.get("game") or "")[:160]
        if not game:
            raise ValueError("Select a game")
        token, client = _load_twitch_token()
        async with client_session(timeout=aiohttp.ClientTimeout(total=20)) as session:
            return await category_channels(session, {"Authorization": "Bearer " + token, "Client-Id": client.CLIENT_ID}, game,
                                           load_settings().get("points_order", "popular"))
    elif action == "search":
        from nyxor.game_search import search_game_categories
        query = str(data.get("query") or "")[:100]
        return [{"id": item.id, "name": item.name} for item in await search_game_categories(query)]
    else:
        raise ValueError("Unknown action")
    if action in {"queue", "streamers", "points_games", "settings"} and _miner is not None and not _miner.done():
        from nyxor_core import settings_changed
        settings_changed()
    return snapshot()
