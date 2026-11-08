from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import time

import aiohttp

from nyxor.storage import atomic_write_json, load_json

BOOLEAN_OPTIONS = ("auto_restart", "energy_saver")
POINT_OPTIONS = ("enabled", "auto_claim_bonus", "follow_raids", "claim_moments")
LOCAL_NETS = tuple(ipaddress.ip_network(net) for net in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


def preferences(data):
    """Validate the entire profile before modifying a single setting."""
    if not isinstance(data, dict):
        raise ValueError("Invalid profile")
    result = {}
    for key in ("queue", "streamers", "points_games"):
        items = data.get(key)
        if not isinstance(items, list) or len(items) > 100 or any(
            not isinstance(item, str) or not item.strip() or len(item) > 160 for item in items
        ):
            raise ValueError("Invalid list in device settings")
        if key == "streamers" and any(not re.fullmatch(r"[A-Za-z0-9_]{1,25}", item) for item in items):
            raise ValueError("Invalid streamer in device settings")
        result[key] = list(dict.fromkeys(item.strip() for item in items))
    order = data.get("points_order")
    if order not in ("popular", "quiet"):
        raise ValueError("Invalid viewing order")
    result["points_order"] = order
    for key in BOOLEAN_OPTIONS + POINT_OPTIONS:
        if type(data.get(key)) is not bool:
            raise ValueError("Invalid device preference")
        result[key] = data[key]
    return result


def public_snapshot(snapshot):
    settings = snapshot.get("settings", {})
    points = settings.get("channel_points", {})
    return {
        "running": bool(snapshot.get("any_running") or snapshot.get("running")),
        "profile": preferences({
            **{key: snapshot.get(key, []) for key in ("queue", "streamers", "points_games")},
            "points_order": settings.get("points_order", "popular"),
            **{key: bool(settings.get(key, key == "auto_restart")) for key in BOOLEAN_OPTIONS},
            **{key: bool(points.get(key, key in ("enabled", "auto_claim_bonus"))) for key in POINT_OPTIONS},
        }),
    }


class PhoneLink:
    def __init__(self, root, snapshot):
        self.file = root / "device-link.json"
        self.snapshot = snapshot
        self.code = load_json(self.file, "")
        self.peer = None
        self.seen = 0
        self.lock = asyncio.Lock()

    @staticmethod
    def parse(code):
        if not isinstance(code, str):
            raise ValueError("Invalid pairing code")
        match = re.fullmatch(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})#([a-f0-9]{64})", code.strip())
        if not match:
            raise ValueError("Invalid pairing code")
        address, port, key = match.groups()
        ip = ipaddress.IPv4Address(address)
        if not any(ip in network for network in LOCAL_NETS) or not 1024 <= int(port) <= 65535:
            raise ValueError("Only local network addresses are supported")
        return f"http://{address}:{port}/nyxor/v1", bytes.fromhex(key)

    def status(self):
        return {"linked": bool(self.code), "peer": self.peer if time.monotonic() - self.seen < 45 else None}

    async def exchange(self, code):
        url, key = self.parse(code)
        body = json.dumps(public_snapshot(await self.snapshot()), ensure_ascii=False).encode()
        nonce = f"{int(time.time())}.{secrets.token_hex(16)}"
        sign = lambda label, payload: hmac.new(key, f"{label}:{nonce}:".encode() + payload, hashlib.sha256).hexdigest()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=4)) as session:
            async with session.post(url, data=body, allow_redirects=False, headers={
                "X-Nyxor-Nonce": nonce, "X-Nyxor-Mac": sign("phone", body),
            }) as response:
                response.raise_for_status()
                chunks = bytearray()
                async for chunk in response.content.iter_chunked(8192):
                    chunks.extend(chunk)
                    if len(chunks) > 64000:
                        raise ValueError("Device response too large")
                raw = bytes(chunks)
                if not hmac.compare_digest(sign("pc", raw), response.headers.get("X-Nyxor-Mac", "")):
                    raise ValueError("Could not verify paired PC")
        payload = json.loads(raw)
        return {"running": payload["running"] is True, "profile": preferences(payload["profile"])}

    async def handle(self, data):
        async with self.lock:
            if data["action"] == "device_pair":
                code = str(data.get("code", "")).strip()
                peer = await self.exchange(code)
                atomic_write_json(self.file, code)
                self.code, self.peer, self.seen = code, peer, time.monotonic()
            elif data["action"] == "device_unlink":
                self.file.unlink(missing_ok=True)
                self.code, self.peer, self.seen = "", None, 0
            return self.status()

    async def heartbeat(self):
        while True:
            async with self.lock:
                if self.code:
                    try:
                        self.peer = await self.exchange(self.code)
                        self.seen = time.monotonic()
                    except (aiohttp.ClientError, ValueError, KeyError, TypeError, TimeoutError, OSError):
                        pass
            await asyncio.sleep(12)
