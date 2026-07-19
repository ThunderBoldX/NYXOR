from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import aiohttp

from constants import COOKIES_PATH, ClientType
from nyxor_campaigns import get_cookie_value


SEARCH_CATEGORIES_URL = "https://api.twitch.tv/helix/search/categories"
CACHE_TTL_SECONDS = 300
MAX_TWITCH_RESULTS = 50


@dataclass(frozen=True, slots=True)
class GameCategory:
    id: str
    name: str
    box_art_url: str = ""


class GameSearchError(RuntimeError):
    def __init__(self, code: str, details: str = "") -> None:
        super().__init__(details or code)
        self.code = code
        self.details = details


_CACHE: dict[str, tuple[float, tuple[GameCategory, ...]]] = {}


def normalize_query(value: str) -> str:
    return " ".join(value.split()).strip()


def _normalized(value: str) -> str:
    return normalize_query(value).casefold()


def _category_rank(category: GameCategory, query: str, source_index: int) -> tuple[Any, ...]:
    name = _normalized(category.name)
    wanted = _normalized(query)
    terms = [term for term in wanted.split(" ") if term]
    words = [word for word in name.replace("-", " ").split(" ") if word]

    exact = name == wanted
    full_prefix = name.startswith(wanted)
    every_term_prefixes_a_word = bool(terms) and all(
        any(word.startswith(term) for word in words)
        for term in terms
    )
    contains_full_query = wanted in name
    every_term_present = bool(terms) and all(term in name for term in terms)

    if exact:
        group = 0
    elif full_prefix:
        group = 1
    elif every_term_prefixes_a_word:
        group = 2
    elif contains_full_query:
        group = 3
    elif every_term_present:
        group = 4
    else:
        group = 5

    return (
        group,
        abs(len(name) - len(wanted)),
        source_index,
        name,
    )


def parse_categories(payload: Any, query: str, limit: int) -> list[GameCategory]:
    if not isinstance(payload, dict):
        return []

    raw_items = payload.get("data")
    if not isinstance(raw_items, list):
        return []

    categories: list[GameCategory] = []
    seen: set[str] = set()

    for item in raw_items:
        if not isinstance(item, dict):
            continue

        name = normalize_query(str(item.get("name") or ""))
        category_id = str(item.get("id") or "").strip()
        if not name or not category_id:
            continue

        folded = name.casefold()
        if folded in seen:
            continue

        seen.add(folded)
        categories.append(
            GameCategory(
                id=category_id,
                name=name,
                box_art_url=str(item.get("box_art_url") or ""),
            )
        )

    indexed = list(enumerate(categories))
    indexed.sort(key=lambda pair: _category_rank(pair[1], query, pair[0]))
    return [category for _, category in indexed[: max(1, limit)]]


def _load_twitch_token() -> tuple[str, Any]:
    client = ClientType.ANDROID_APP

    if not COOKIES_PATH.exists():
        raise GameSearchError("auth_missing")

    jar = aiohttp.CookieJar()
    try:
        jar.load(COOKIES_PATH)
    except Exception as error:
        raise GameSearchError("auth_invalid", str(error)) from error

    cookies = jar.filter_cookies(client.CLIENT_URL)
    token = get_cookie_value(cookies, "auth-token")

    if not token:
        raise GameSearchError("auth_missing")

    return token, client


async def search_game_categories(
    query: str,
    *,
    limit: int = 10,
) -> list[GameCategory]:
    cleaned = normalize_query(query)
    if len(cleaned) < 2:
        return []

    cache_key = cleaned.casefold()
    cached = _CACHE.get(cache_key)
    now = time.monotonic()

    if cached is not None:
        cached_at, categories = cached
        if now - cached_at <= CACHE_TTL_SECONDS:
            return list(categories[:limit])
        _CACHE.pop(cache_key, None)

    token, client = _load_twitch_token()
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Client-Id": client.CLIENT_ID,
        "User-Agent": client.USER_AGENT,
    }
    params = {
        "query": cleaned,
        "first": str(MAX_TWITCH_RESULTS),
    }
    timeout = aiohttp.ClientTimeout(sock_connect=10, total=20)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                SEARCH_CATEGORIES_URL,
                headers=headers,
                params=params,
            ) as response:
                if response.status == 401:
                    raise GameSearchError("auth_invalid")
                if response.status == 429:
                    raise GameSearchError("rate_limited")
                if response.status != 200:
                    details = (await response.text()).replace("\n", " ")[:180]
                    raise GameSearchError(
                        "twitch_error",
                        f"HTTP {response.status}: {details}",
                    )

                payload = await response.json(content_type=None)
    except GameSearchError:
        raise
    except (aiohttp.ClientError, TimeoutError) as error:
        raise GameSearchError("network", str(error)) from error
    except Exception as error:
        raise GameSearchError("unknown", str(error)) from error

    categories = parse_categories(payload, cleaned, MAX_TWITCH_RESULTS)
    _CACHE[cache_key] = (now, tuple(categories))
    return categories[:limit]
