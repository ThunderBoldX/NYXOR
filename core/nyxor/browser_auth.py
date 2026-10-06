"""Desktop-only Twitch browser context. No credentials cross the UI boundary."""
from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
from pathlib import Path

import aiohttp

HEADER_NAMES = frozenset({"authorization", "client-id", "client-integrity", "client-version",
                          "client-session-id", "x-device-id", "device-id", "accept-language"})


class BrowserAuthError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__({"browser_expired": "Twitch session expired. Connect Twitch again in Settings.",
                          "browser_account_changed": "Twitch account changed. Stop farming and reconnect in Settings.",
                          "browser_invalid": "Twitch session could not be restored. Connect Twitch again in Settings.",
                          "browser_catalog": "Twitch did not confirm Drops access. Reconnect in Settings.",
                          "browser_rejected": "Twitch did not confirm this login. Reconnect in Settings."}.get(code, code))


def context_path():
    from constants import COOKIES_PATH
    return COOKIES_PATH.with_name("browser-session.json")


def validate_context(data):
    from constants import ClientType
    try:
        if not isinstance(data, dict) or set(data) != {"headers", "user_agent", "expires_at"}:
            raise ValueError
        expiry = data["expires_at"]
        if type(expiry) not in (float, int) or not math.isfinite(expiry) or not time.time() + 30 < expiry < time.time() + 86400:
            raise ValueError
        headers = data["headers"]
        if not isinstance(headers, dict) or not set(headers) <= HEADER_NAMES:
            raise ValueError
        for value in (data["user_agent"], *headers.values()):
            if not isinstance(value, str) or not re.fullmatch(r"[\x20-\x7e]{1,16384}", value):
                raise ValueError
        if (len(data["user_agent"]) > 1024 or headers.get("client-id") != ClientType.WEB.CLIENT_ID
                or not re.fullmatch(r"OAuth [A-Za-z0-9_-]{1,512}", headers.get("authorization", ""))
                or not headers.get("client-integrity") or not (headers.get("x-device-id") or headers.get("device-id"))):
            raise ValueError
        if len(json.dumps(data)) > 50000:
            raise ValueError
        return data
    except (TypeError, ValueError, KeyError):
        raise BrowserAuthError("browser_invalid") from None


def request_headers(data):
    return {**data["headers"], "user-agent": data["user_agent"], "origin": "https://www.twitch.tv",
            "referer": "https://www.twitch.tv/", "content-type": "application/json"}


def stored_client():
    from constants import COOKIES_PATH, ClientType
    if os.environ.get("NYXOR_PLATFORM") == "desktop" and COOKIES_PATH.exists():
        try:
            jar = aiohttp.CookieJar()
            jar.load(COOKIES_PATH)
            marker = jar.filter_cookies(ClientType.WEB.CLIENT_URL).get("nyxor-client")
            if marker and marker.value == ClientType.WEB.CLIENT_ID:
                return ClientType.WEB
        except Exception:
            pass
    return ClientType.ANDROID_APP


async def import_context(data, *, renewal=False):
    """Validate both identity and real protected catalog before replacing a login."""
    from constants import COOKIES_PATH, ClientType, GQL_QUERIES
    from nyxor.network import client_session
    data = validate_context(data)
    token = data["headers"]["authorization"][6:]
    # A dummy jar makes validation independent of the currently saved account.
    async with client_session(cookie_jar=aiohttp.DummyCookieJar(), timeout=aiohttp.ClientTimeout(total=20)) as session:
        async with session.get("https://id.twitch.tv/oauth2/validate", headers={"Authorization": f"OAuth {token}"}, allow_redirects=False) as response:
            if response.status != 200:
                raise BrowserAuthError("browser_rejected")
            account = await response.json()
        if account.get("client_id") != ClientType.WEB.CLIENT_ID or not re.fullmatch(r"[0-9]+", str(account.get("user_id", ""))):
            raise BrowserAuthError("browser_rejected")
        if renewal:
            jar = aiohttp.CookieJar()
            jar.load(COOKIES_PATH)
            cookies = jar.filter_cookies(ClientType.WEB.CLIENT_URL)
            if (not cookies.get("persistent") or cookies["persistent"].value != str(account["user_id"])
                    or not cookies.get("auth-token") or cookies["auth-token"].value != token):
                raise BrowserAuthError("browser_account_changed")
        async with session.post("https://gql.twitch.tv/gql", json=GQL_QUERIES["Campaigns"], headers=request_headers(data), allow_redirects=False) as response:
            if response.status != 200:
                raise BrowserAuthError("browser_rejected")
            result = await response.json()
        if isinstance(result, list) and len(result) == 1:
            result = result[0]
        if not isinstance(result, dict) or result.get("errors"):
            raise BrowserAuthError("browser_catalog")
        user = (result.get("data") or {}).get("currentUser") or {}
        if not isinstance(user.get("dropCampaigns"), list):
            raise BrowserAuthError("browser_catalog")
    # Persist the context first: on failure the previous cookie file survives.
    previous = context_path().read_bytes() if context_path().exists() else None
    atomic_save(context_path(), data)
    if not renewal:
        try:
            jar = aiohttp.CookieJar()
            jar.update_cookies({"auth-token": token, "persistent": str(account["user_id"]),
                                "unique_id": data["headers"].get("x-device-id") or data["headers"]["device-id"],
                                "nyxor-client": ClientType.WEB.CLIENT_ID}, ClientType.WEB.CLIENT_URL)
            fd, temporary = tempfile.mkstemp(prefix=".nyxor-cookie-", dir=COOKIES_PATH.parent)
            os.close(fd)
            try:
                jar.save(Path(temporary))
                os.replace(temporary, COOKIES_PATH)
            finally:
                Path(temporary).unlink(missing_ok=True)
        except Exception:
            if previous is None:
                context_path().unlink(missing_ok=True)
            else:
                atomic_save(context_path(), json.loads(previous))
            raise BrowserAuthError("browser_invalid") from None
    return str(account.get("login") or "")


def atomic_save(path, data):
    fd, temporary = tempfile.mkstemp(prefix=".nyxor-browser-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


async def apply_context(_session, _context, params):
    """Refresh every GQL request; do not send browser secrets to other hosts."""
    from constants import ClientType
    if str(params.url) != "https://gql.twitch.tv/gql" or params.headers.get("Client-Id") != ClientType.WEB.CLIENT_ID:
        return
    # Import validation supplies its own complete context, not the saved one.
    if "Client-Integrity" in params.headers:
        return
    try:
        data = json.loads(context_path().read_text(encoding="utf-8"))
        if data["expires_at"] <= time.time():
            raise BrowserAuthError("browser_expired")
        if data["headers"]["authorization"] != params.headers.get("Authorization"):
            raise BrowserAuthError("browser_account_changed")
        for name in (*HEADER_NAMES, "user-agent", "origin", "referer"):
            params.headers.popall(name, None)
        params.headers.update(request_headers(data))
    except BrowserAuthError:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise BrowserAuthError("browser_invalid") from None


async def reject_redirect(_session, _context, params):
    if str(params.url) == "https://gql.twitch.tv/gql" and "Client-Integrity" in params.headers:
        raise BrowserAuthError("browser_rejected")
