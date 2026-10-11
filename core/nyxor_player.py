from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, replace
from typing import Any
from urllib.parse import urljoin

import aiohttp

from nyxor_campaigns import gql_request


PLAYBACK_ACCESS_TOKEN_HASH = (
    "ed230aa1e33e07eebb8928504583da78a5173989fadfb1ac94be06a04f3cdbe9"
)
USHER_URL = "https://usher.ttvnw.net/api/v2/channel/hls/{login}.m3u8"
DEFAULT_PULSE_INTERVAL = 20.0
PLAYLIST_LEASE_SECONDS = 300.0
MAX_MEDIA_SEGMENTS = 30


@dataclass(slots=True)
class PlaybackLease:
    login: str = ""
    url: str = ""
    quality: str = "—"
    updated_monotonic: float = 0.0

    def clear(self) -> None:
        self.url = ""
        self.updated_monotonic = 0.0


@dataclass(slots=True, frozen=True)
class PlaybackStatus:
    login: str = ""
    active: bool = False
    quality: str = "—"
    http_status: int | None = None
    detail: str = "очікування"
    updated_monotonic: float = 0.0
    segments_checked: int = 0
    segments_total: int = 0

    @property
    def age(self) -> float:
        if self.updated_monotonic <= 0:
            return float("inf")
        return max(0.0, time.monotonic() - self.updated_monotonic)

    def display_text(self) -> str:
        if self.active:
            quality = f" · {self.quality}" if self.quality and self.quality != "—" else ""
            return f"✓ HLS активний{quality}"
        if self.login:
            return f"✗ HLS: {self.detail}"
        return "—"


def _playback_operation(login: str) -> dict[str, Any]:
    return {
        "operationName": "PlaybackAccessToken",
        "variables": {
            "login": login,
            "isLive": True,
            "isVod": False,
            "vodID": "",
            "playerType": "site",
            "platform": "web",
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": PLAYBACK_ACCESS_TOKEN_HASH,
            }
        },
    }


def _clean_playlist_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _attribute_value(line: str, name: str) -> str:
    marker = f"{name}="
    start = line.find(marker)
    if start < 0:
        return ""

    value = line[start + len(marker) :]
    if value.startswith('"'):
        end = value.find('"', 1)
        return value[1:end] if end > 0 else value.strip('"')

    return value.split(",", 1)[0].strip()


def parse_master_playlist(text: str, base_url: str) -> tuple[str, str]:
    """Return the lowest non-audio HLS variant and a readable quality label."""

    lines = _clean_playlist_lines(text)
    variants: list[tuple[int, int, str, str]] = []

    for index, line in enumerate(lines):
        if not line.startswith("#EXT-X-STREAM-INF:"):
            continue

        uri = ""
        for following in lines[index + 1 :]:
            if not following.startswith("#"):
                uri = following
                break

        if not uri:
            continue

        name = (
            _attribute_value(line, "NAME")
            or _attribute_value(line, "VIDEO")
            or _attribute_value(line, "RESOLUTION")
            or "unknown"
        )
        lowered = f"{line} {name}".casefold()
        is_audio_only = "audio_only" in lowered or "audio only" in lowered

        try:
            bandwidth = int(_attribute_value(line, "BANDWIDTH") or 0)
        except ValueError:
            bandwidth = 0

        # Prefer a real video rendition. If Twitch only returns audio, it remains
        # available as a last-resort candidate.
        audio_rank = 1 if is_audio_only else 0
        variants.append(
            (
                audio_rank,
                bandwidth if bandwidth > 0 else 2**31 - 1,
                name,
                urljoin(base_url, uri),
            )
        )

    if not variants:
        raise RuntimeError("master playlist не містить HLS-якостей")

    variants.sort(key=lambda item: (item[0], item[1]))
    _, _, quality, url = variants[0]
    return url, quality


def parse_media_playlist(text: str, base_url: str) -> str:
    """Return the newest media segment URL from an HLS media playlist."""

    segments = [
        urljoin(base_url, line)
        for line in _clean_playlist_lines(text)
        if not line.startswith("#")
    ]
    if not segments:
        raise RuntimeError("media playlist не містить сегментів")
    return segments[-1]


def parse_media_segments(text: str, base_url: str) -> list[str]:
    """Read the bounded live segment window, not a single newest fragment."""
    lines = _clean_playlist_lines(text)
    if not lines or lines[0] != "#EXTM3U" or "#EXT-X-ENDLIST" in lines:
        raise RuntimeError("media playlist не є активним HLS-стрімом")
    result = []
    awaiting_segment = False
    for line in lines:
        if line.startswith("#EXTINF:"):
            awaiting_segment = True
        elif not line.startswith("#") and awaiting_segment:
            uri = urljoin(base_url, line)
            if not uri.startswith(("https://", "http://")):
                raise RuntimeError("media playlist містить непідтримувану адресу")
            result.append(uri)
            awaiting_segment = False
    if not result:
        raise RuntimeError("media playlist не містить сегментів")
    return list(dict.fromkeys(result[-MAX_MEDIA_SEGMENTS:]))


async def _touch_segment(session, segment_url, request_headers) -> int:
    status = 0
    try:
        async with session.head(segment_url, headers=request_headers, allow_redirects=True,
                                timeout=aiohttp.ClientTimeout(total=12)) as response:
            status = response.status
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    if status == 200:
        return status
    # HEAD-unsupported edges get a bounded fallback; never download a full video.
    headers = {**request_headers, "Range": "bytes=0-1023"}
    async with session.get(segment_url, headers=headers, allow_redirects=True,
                           timeout=aiohttp.ClientTimeout(total=12)) as response:
        await response.content.read(1024)
        return response.status


async def _read_text_response(response: aiohttp.ClientResponse) -> str:
    raw = await response.read()
    return raw.decode(response.charset or "utf-8", errors="replace")


async def fetch_playback_token(
    session: aiohttp.ClientSession,
    gql_headers: dict[str, str],
    login: str,
) -> tuple[str, str]:
    response = await gql_request(
        session,
        _playback_operation(login),
        gql_headers,
    )
    token_data = (
        response.get("data", {})
        .get("streamPlaybackAccessToken")
    )
    if not isinstance(token_data, dict):
        raise RuntimeError("Twitch не повернув PlaybackAccessToken")

    signature = str(token_data.get("signature") or "")
    value = str(token_data.get("value") or "")
    if not signature or not value:
        raise RuntimeError("PlaybackAccessToken порожній")

    return signature, value


async def touch_hls_stream(
    session: aiohttp.ClientSession,
    gql_headers: dict[str, str],
    login: str,
    *,
    user_agent: str,
    lease: PlaybackLease | None = None,
) -> PlaybackStatus:
    login = login.strip().lower()
    if not login:
        return PlaybackStatus()

    try:
        lease = lease if lease is not None else PlaybackLease()
        request_headers = {
            "User-Agent": user_agent,
            "Accept": "application/vnd.apple.mpegurl, application/x-mpegURL, */*",
            "Origin": "https://www.twitch.tv",
            "Referer": f"https://www.twitch.tv/{login}",
        }

        if lease.login != login or not lease.url or time.monotonic() - lease.updated_monotonic >= PLAYLIST_LEASE_SECONDS:
            signature, token = await fetch_playback_token(session, gql_headers, login)
            master_url = USHER_URL.format(login=login)
            master_params = {
                "sig": signature, "token": token, "platform": "web",
                "allow_source": "true", "allow_audio_only": "false",
                "p": str(random.randint(1, 9_999_999)), "player_backend": "mediaplayer",
                "playlist_include_framerate": "true", "reassignments_supported": "true",
                "supported_codecs": "h264",
            }
            async with session.get(master_url, params=master_params, headers=request_headers,
                                   timeout=aiohttp.ClientTimeout(total=20)) as response:
                master_status = response.status
                master_text = await _read_text_response(response)
                master_base = str(response.url)
            if master_status != 200:
                raise RuntimeError(f"master playlist HTTP {master_status}")
            variant_url, quality = parse_master_playlist(master_text, master_base)
            lease.login, lease.url, lease.quality = login, variant_url, quality
            lease.updated_monotonic = time.monotonic()

        async with session.get(
            lease.url,
            headers={**request_headers, "Connection": "close"},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as response:
            media_status = response.status
            media_text = await _read_text_response(response)
            media_url = str(response.url)

        if media_status != 200:
            lease.clear()
            raise RuntimeError(f"media playlist HTTP {media_status}")

        segments = parse_media_segments(media_text, media_url)
        statuses = []
        for offset in range(0, len(segments), 3):
            statuses.extend(await asyncio.gather(*[
                _touch_segment(session, uri, request_headers) for uri in segments[offset:offset + 3]
            ]))
        checked = sum(status in (200, 206) for status in statuses)
        if checked != len(segments):
            failed = next(status for status in statuses if status not in (200, 206))
            lease.clear()
            return PlaybackStatus(login=login, detail=f"відеосегмент HTTP {failed}", http_status=failed,
                updated_monotonic=time.monotonic(), segments_checked=checked, segments_total=len(segments))

        return PlaybackStatus(
            login=login,
            active=True,
            quality=lease.quality,
            http_status=statuses[-1],
            detail="active",
            updated_monotonic=time.monotonic(),
            segments_checked=checked,
            segments_total=len(segments),
        )

    except asyncio.CancelledError:
        raise
    except Exception as error:
        message = str(error).replace("\n", " ").strip() or type(error).__name__
        return PlaybackStatus(
            login=login,
            active=False,
            quality="—",
            http_status=None,
            detail=message[:72],
            updated_monotonic=time.monotonic(),
        )


class TwitchHLSPlayer:
    """Maintains one lightweight HLS playback heartbeat for the selected channel."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        gql_headers: dict[str, str],
        *,
        user_agent: str,
        pulse_interval: float = DEFAULT_PULSE_INTERVAL,
    ) -> None:
        self._session = session
        self._gql_headers = gql_headers
        self._user_agent = user_agent
        self._pulse_interval = max(10.0, pulse_interval)
        self._login = ""
        self._status = PlaybackStatus()
        self._changed = asyncio.Event()
        self._stopping = False
        self._task: asyncio.Task[None] | None = None
        self._lease = PlaybackLease()
        self._revision = 0
        self._broadcast_id = ""

    def set_power_saver(self, enabled: bool) -> None:
        # Watch credit is core work. Reduce discovery/UI load, not playback coverage.
        interval = DEFAULT_PULSE_INTERVAL
        if interval != self._pulse_interval:
            self._pulse_interval = interval
            self._changed.set()

    @property
    def status(self) -> PlaybackStatus:
        return replace(self._status)

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stopping = False
            self._task = asyncio.create_task(
                self._run(),
                name="nyxor-hls-player",
            )

    async def stop(self) -> None:
        self._stopping = True
        self._changed.set()
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def set_channel(self, login: str, broadcast_id: str = "") -> None:
        normalized = login.strip().lower()
        if normalized == self._login and broadcast_id == self._broadcast_id:
            return
        self._login = normalized
        self._broadcast_id = broadcast_id
        self.invalidate()

    def invalidate(self) -> None:
        self._revision += 1
        self._lease = PlaybackLease()
        self._status = PlaybackStatus(login=self._login)
        self._changed.set()

    async def clear(self) -> None:
        await self.set_channel("")

    async def ensure_active(
        self,
        login: str,
        *,
        timeout: float = 30.0,
        max_age: float = 45.0,
        broadcast_id: str = "",
    ) -> PlaybackStatus:
        await self.set_channel(login, broadcast_id)
        current = self.status
        if (
            current.login == self._login
            and current.active
            and current.age <= max_age
        ):
            return current

        # Wake the background loop and wait for one fresh result.
        baseline = current.updated_monotonic
        self._changed.set()
        deadline = time.monotonic() + max(1.0, timeout)

        while time.monotonic() < deadline:
            current = self.status
            if (
                current.login == self._login
                and current.updated_monotonic > baseline
            ):
                return current
            await asyncio.sleep(0.2)

        return self.status

    async def _run(self) -> None:
        while not self._stopping:
            self._changed.clear()
            login = self._login
            revision = self._revision
            pulse_started = time.monotonic()

            if not login:
                try:
                    await self._changed.wait()
                except asyncio.CancelledError:
                    raise
                continue

            result = await touch_hls_stream(
                self._session,
                self._gql_headers,
                login,
                user_agent=self._user_agent,
                lease=self._lease,
            )
            if login == self._login and revision == self._revision:
                self._status = result

            try:
                await asyncio.wait_for(
                    self._changed.wait(),
                    timeout=max(0.01, self._pulse_interval - (time.monotonic() - pulse_started)),
                )
            except asyncio.TimeoutError:
                pass
