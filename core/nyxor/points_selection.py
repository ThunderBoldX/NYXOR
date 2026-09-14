"""Selection for points farming, independent of Drops directory filters."""
import asyncio
import time
from nyxor_points import fetch_channel_points_context

_directories = {}
_contexts = {}
_scan_positions = {}


def point_games(settings):
    value = settings.get("points_games") or []
    return list(dict.fromkeys(item.strip() for item in value if isinstance(item, str) and item.strip())) if isinstance(value, list) else []


def channel_allowed(channel, logins, games):
    return (str(channel.get("login") or "").casefold() in {name.casefold() for name in logins}
            or str(channel.get("game") or "").casefold() in {name.casefold() for name in games})


def sorted_channels(channels, order):
    return sorted(channels, key=lambda c: ((-1 if order == "popular" else 1) * int(c.get("viewers") or 0), str(c.get("login") or "").casefold()))


async def category_channels(session, headers, game, order="popular"):
    key = (headers.get("Authorization"), game.casefold(), order)
    cached = _directories.get(key)
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    helix = {"Authorization": headers.get("Authorization", "").replace("OAuth ", "Bearer ", 1),
             "Client-Id": headers.get("Client-Id", "")}
    items, complete = {}, False
    try:
        async with asyncio.timeout(18):
            async with session.get("https://api.twitch.tv/helix/games", headers=helix, params={"name": game}) as response:
                response.raise_for_status()
                games = (await response.json()).get("data") or []
            exact = next((item for item in games if item.get("name", "").casefold() == game.casefold()), None)
            if exact is None:
                return dict(items=[], complete=True)
            cursor, seen = "", set()
            for _ in range(100):
                params = dict(game_id=exact["id"], first="100")
                if cursor:
                    params["after"] = cursor
                async with session.get("https://api.twitch.tv/helix/streams", headers=helix, params=params) as response:
                    response.raise_for_status()
                    payload = await response.json()
                for stream in payload.get("data") or []:
                    if str(stream.get("game_id")) != str(exact["id"]) or stream.get("type") != "live":
                        continue
                    login = str(stream.get("user_login") or "").casefold()
                    if login:
                        items[login] = dict(login=login, display_name=stream.get("user_name") or login,
                            stream_id=stream["id"], channel_id=stream["user_id"], game=exact["name"], game_id=exact["id"],
                            viewers=stream.get("viewer_count", 0), title=stream.get("title") or "")
                cursor = (payload.get("pagination") or {}).get("cursor") or ""
                complete = not cursor
                # The first page already contains the most popular streams.
                if not cursor or cursor in seen or order == "popular":
                    break
                seen.add(cursor)
    except TimeoutError:
        if not items:
            raise
    result = dict(items=sorted_channels(list(items.values()), order), complete=complete)
    if len(_directories) > 100:
        _directories.clear()
    _directories[key] = (time.monotonic(), result)
    return result


async def points_capable(session, headers, channel):
    key = (headers.get("Authorization"), channel["login"])
    cached = _contexts.get(key)
    if cached and time.monotonic() - cached[0] < 30:
        context = cached[1]
    else:
        try:
            context = await fetch_channel_points_context(session, headers, channel["login"])
        except Exception:
            # Do not cache transient failures: the next scan can recover.
            return None
        if len(_contexts) > 500:
            _contexts.clear()
        _contexts[key] = (time.monotonic(), context)
    result = dict(channel)
    result["_points_balance"] = context.balance
    return result


async def pick_points_target(session, headers, logins, games, order="popular", raid_login=""):
    try:
        async with asyncio.timeout(30):
            return await _pick_points_target(session, headers, logins, games, order, raid_login)
    except TimeoutError:
        return None


async def _pick_points_target(session, headers, logins, games, order, raid_login):
    from nyxor_core import fetch_streamer_channel
    candidates = list(dict.fromkeys(([raid_login] if raid_login else []) + logins))
    for login in candidates:
        try:
            channel = await fetch_streamer_channel(session, headers, login)
            if channel and channel_allowed(channel, logins, games):
                capable = await points_capable(session, headers, channel)
                if capable:
                    return capable
        except Exception:
            continue
    for game in games:
        try:
            directory = await category_channels(session, headers, game, order)
        except Exception:
            continue
        candidates = directory["items"]
        scan_key = (headers.get("Authorization"), game.casefold(), order)
        offset = _scan_positions.get(scan_key, 0) % max(1, len(candidates))
        for step in range(len(candidates)):
            index = (offset + step) % len(candidates)
            candidate = candidates[index]
            # Resume after a bounded scan instead of retrying only the same
            # channels without points every time. Keep a working selection stable.
            _scan_positions[scan_key] = (index + 1) % len(candidates)
            # Recheck stream and category: cached directory entries may be stale.
            try:
                channel = await fetch_streamer_channel(session, headers, candidate["login"])
                if not channel or channel.get("game", "").casefold() != game.casefold():
                    continue
                capable = await points_capable(session, headers, channel)
                if capable:
                    _scan_positions[scan_key] = index
                    return capable
            except Exception:
                continue
    return None
