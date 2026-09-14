"""Shared HTTP setup, with an Android DNS fallback on the app's default network."""
from __future__ import annotations

import asyncio
import ipaddress
import socket

import aiohttp

_android = None


def configure_android(adapter) -> None:
    global _android
    _android = adapter


def connection_state() -> str:
    if _android is not None:
        try:
            state = str(_android.status())
            if state in {"offline", "captive", "no_internet", "available"}:
                return state
        except Exception:
            pass
    return "unknown"


def connection_blocker() -> str:
    state = connection_state()
    return state if state in {"offline", "captive", "no_internet"} else ""


class AndroidResolver(aiohttp.ThreadedResolver):
    async def resolve(self, host, port=0, family=socket.AF_INET):
        try:
            return await super().resolve(host, port, family)
        except socket.gaierror as original:
            if _android is None:
                raise
            # Java uses Android's application network context (including VPN).
            # Keep the original hostname for TLS/SNI and certificate validation.
            for attempt in range(2):
                try:
                    addresses = await asyncio.to_thread(_android.resolve, host)
                    results = []
                    for address in addresses:
                        address = str(address)
                        version = ipaddress.ip_address(address).version
                        af = socket.AF_INET6 if version == 6 else socket.AF_INET
                        if family not in (socket.AF_UNSPEC, af):
                            continue
                        results.append(dict(hostname=host, host=address, port=port,
                                            family=af, proto=0, flags=socket.AI_NUMERICHOST))
                    if results:
                        return results
                except Exception:
                    pass
                if attempt == 0:
                    await asyncio.sleep(2)
            raise original


def client_session(**kwargs):
    if _android is not None and "connector" not in kwargs:
        kwargs["connector"] = aiohttp.TCPConnector(resolver=AndroidResolver())
    return aiohttp.ClientSession(**kwargs)


def error_code(error) -> str:
    if isinstance(error, (aiohttp.ClientSSLError, aiohttp.ServerFingerprintMismatch)):
        return "tls"
    if isinstance(error, aiohttp.ClientResponseError):
        return "twitch_http"
    is_dns = isinstance(error, socket.gaierror) or isinstance(
        getattr(error, "os_error", None), socket.gaierror)
    if is_dns or isinstance(error, (aiohttp.ClientConnectionError, TimeoutError)):
        state = connection_blocker()
        if state:
            return state
        return "dns" if is_dns else "timeout" if isinstance(error, TimeoutError) else "connection"
    return ""


async def check_connection() -> dict:
    blocked = connection_blocker()
    if blocked:
        return {"status": blocked}
    try:
        async with client_session(timeout=aiohttp.ClientTimeout(total=12)) as session:
            # A token-free 401 proves DNS, TCP and TLS reached the Twitch API.
            async with session.get("https://id.twitch.tv/oauth2/validate", allow_redirects=False) as response:
                return {"status": "ok" if response.status == 401 else "twitch_http"}
    except Exception as error:
        return {"status": error_code(error) or "connection"}
