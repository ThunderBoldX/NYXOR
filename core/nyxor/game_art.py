"""Small, bounded cache of official Twitch category artwork URLs."""
import time
from urllib.parse import urlsplit
import aiohttp

_cache = {}


def safe_art_url(value):
    value = str(value or '').replace('{width}', '144').replace('{height}', '192')
    try:
        url = urlsplit(value)
        return value if (url.scheme == 'https' and url.hostname == 'static-cdn.jtvnw.net'
                         and url.path.startswith('/ttv-boxart/') and not url.username
                         and not url.password and url.port in (None, 443)) else ''
    except ValueError:
        return ''


async def game_art(session, headers, name):
    if not name:
        return ''
    key = name.casefold()
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    try:
        from constants import ClientType
        if headers.get('Client-Id') == ClientType.WEB.CLIENT_ID:
            from nyxor.twitch_catalog import public_request, ART_QUERY
            payload = await public_request(session, ART_QUERY, {'name': name})
            game = payload.get('game') or {}
            url = safe_art_url(game.get('boxArtURL')) if str(game.get('name', '')).casefold() == key else ''
            _cache[key] = (time.monotonic() + (86400 if url else 60), url)
            if len(_cache) > 100:
                _cache.pop(next(iter(_cache)))
            return url
        async with session.get('https://api.twitch.tv/helix/games', params={'name': name},
                               headers={'Client-Id': headers['Client-Id'],
                                        'Authorization': headers['Authorization'].replace('OAuth ', 'Bearer ', 1)},
                               timeout=aiohttp.ClientTimeout(total=6)) as response:
            response.raise_for_status()
            payload = await response.json()
        url = next((safe_art_url(row.get('box_art_url')) for row in payload.get('data', [])
                    if str(row.get('name', '')).casefold() == key), '')
    except Exception:
        url = ''
    if len(_cache) >= 100:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic() + (86400 if url else 60), url)
    return url
