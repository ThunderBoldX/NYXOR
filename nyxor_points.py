from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import aiohttp


GQL_URL = "https://gql.twitch.tv/gql"

CHANNEL_POINTS_CONTEXT_HASH = (
    "7fe050e3761eb2cf258d70ee1a21cbd76fa8cf3d7e7b12fc437e7029d446b5e3"
)
CLAIM_COMMUNITY_POINTS_HASH = (
    "46aaeebe02c99afdf4fc97c7c0cba964124bf6b0af229395f1f6d1feed05b3d0"
)


@dataclass(slots=True)
class ChannelPointsResult:
    """Result of one Channel Points refresh."""

    balance: int
    session_delta: int
    bonus_status: str
    claimed_bonus: bool = False
    bonus_count: int = 0
    reward_title: str | None = None
    reward_cost: int | None = None


@dataclass(slots=True, frozen=True)
class ChannelPointsSnapshot:
    """Balance, bonus claim and the most expensive visible reward."""

    balance: int
    claim_id: str | None
    reward_title: str | None
    reward_cost: int | None


@dataclass(slots=True)
class ChannelPointsTracker:
    """Keeps per-channel session statistics without writing private data to disk."""

    initial_balances: dict[str, int] = field(default_factory=dict)
    last_balances: dict[str, int] = field(default_factory=dict)
    pending_bonus_ids: set[str] = field(default_factory=set)
    claimed_bonus_ids: set[str] = field(default_factory=set)
    bonus_counts: dict[str, int] = field(default_factory=dict)
    streak_totals: dict[str, int] = field(default_factory=dict)
    moment_ids: dict[str, set[str]] = field(default_factory=dict)

    @staticmethod
    def _key(channel_login: str) -> str:
        return channel_login.strip().lower()

    def update(self, channel_login: str, balance: int) -> int:
        key = self._key(channel_login)
        if not key:
            return 0

        self.initial_balances.setdefault(key, balance)
        self.last_balances[key] = balance
        return balance - self.initial_balances[key]

    def reserve_bonus_claim(self, channel_login: str, claim_id: str) -> bool:
        key = self._key(channel_login)
        claim_id = claim_id.strip()
        if not key or not claim_id:
            return False
        if claim_id in self.pending_bonus_ids or claim_id in self.claimed_bonus_ids:
            return False
        self.pending_bonus_ids.add(claim_id)
        return True

    def confirm_bonus_claim(self, channel_login: str, claim_id: str) -> int:
        key = self._key(channel_login)
        self.pending_bonus_ids.discard(claim_id)
        if claim_id not in self.claimed_bonus_ids:
            self.claimed_bonus_ids.add(claim_id)
            self.bonus_counts[key] = self.bonus_counts.get(key, 0) + 1
        return self.bonus_counts.get(key, 0)

    def release_bonus_claim(self, channel_login: str, claim_id: str) -> None:
        del channel_login
        self.pending_bonus_ids.discard(claim_id)

    def bonus_count(self, channel_login: str) -> int:
        return self.bonus_counts.get(self._key(channel_login), 0)

    def record_streak(self, channel_login: str, points: int) -> int:
        key = self._key(channel_login)
        self.streak_totals[key] = self.streak_totals.get(key, 0) + max(0, points)
        return self.streak_totals[key]

    def streak_points(self, channel_login: str) -> int:
        return self.streak_totals.get(self._key(channel_login), 0)

    def record_moment(self, channel_login: str, moment_id: str) -> int:
        key = self._key(channel_login)
        ids = self.moment_ids.setdefault(key, set())
        ids.add(moment_id)
        return len(ids)

    def moment_count(self, channel_login: str) -> int:
        return len(self.moment_ids.get(self._key(channel_login), set()))


def _operation(
    operation_name: str,
    sha256_hash: str,
    variables: dict[str, Any],
) -> dict[str, Any]:
    return {
        "operationName": operation_name,
        "variables": variables,
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": sha256_hash,
            }
        },
    }


async def _post_gql(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    async with session.post(
        GQL_URL,
        headers=headers,
        json=payload,
        timeout=aiohttp.ClientTimeout(total=20),
    ) as response:
        raw = await response.text()

        if response.status != 200:
            preview = raw.replace("\n", " ")[:180]
            raise RuntimeError(f"Twitch GQL HTTP {response.status}: {preview}")

    try:
        decoded: Any = json.loads(raw)
    except json.JSONDecodeError as error:
        raise RuntimeError("Twitch повернув некоректну JSON-відповідь") from error

    if isinstance(decoded, list):
        if not decoded:
            raise RuntimeError("Twitch повернув порожню GQL-відповідь")
        decoded = decoded[0]

    if not isinstance(decoded, dict):
        raise RuntimeError("Неочікуваний формат Twitch GQL-відповіді")

    errors = decoded.get("errors")
    if errors:
        messages = []
        for item in errors:
            if isinstance(item, dict):
                messages.append(str(item.get("message") or item))
            else:
                messages.append(str(item))
        raise RuntimeError("; ".join(messages)[:240])

    return decoded


def _optional_bool(value: Any) -> bool | None:
    """Return a boolean only when Twitch supplied an unambiguous value."""

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False

    if isinstance(value, int) and value in {0, 1}:
        return bool(value)

    return None


def _reward_field(reward: dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in reward:
            return reward[name]
    return None


def _reward_cost(reward: dict[str, Any]) -> int | None:
    raw = _reward_field(reward, "cost", "price", "points")

    if isinstance(raw, dict):
        raw = (
            raw.get("amount")
            or raw.get("value")
            or raw.get("cost")
            or raw.get("points")
        )

    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None


def _looks_like_reward(value: Any) -> bool:
    if not isinstance(value, dict):
        return False

    title = _reward_field(value, "title", "name")
    return bool(str(title or "").strip()) and _reward_cost(value) is not None


def _iter_reward_nodes(value: Any):
    """Flatten Twitch reward arrays, nodes and edges defensively."""

    if isinstance(value, list):
        for item in value:
            yield from _iter_reward_nodes(item)
        return

    if not isinstance(value, dict):
        return

    if _looks_like_reward(value):
        yield value
        return

    node = value.get("node")
    if isinstance(node, dict):
        yield from _iter_reward_nodes(node)

    for key in ("nodes", "edges", "items", "rewards"):
        child = value.get(key)
        if isinstance(child, (list, dict)):
            yield from _iter_reward_nodes(child)


def _iter_reward_collections(value: Any):
    """
    Find reward collections anywhere in ChannelPointsContext.

    Twitch has moved these fields between community/channel/settings objects
    before, so the parser intentionally does not depend on one exact path.
    """

    if isinstance(value, list):
        for item in value:
            yield from _iter_reward_collections(item)
        return

    if not isinstance(value, dict):
        return

    for key, child in value.items():
        normalized = key.replace("_", "").lower()

        if normalized in {"customrewards", "automaticrewards"}:
            yield child

        if isinstance(child, (dict, list)):
            yield from _iter_reward_collections(child)


def _reward_is_available(reward: dict[str, Any]) -> bool:
    enabled = _optional_bool(
        _reward_field(reward, "isEnabled", "is_enabled", "enabled")
    )
    paused = _optional_bool(
        _reward_field(reward, "isPaused", "is_paused", "paused")
    )
    in_stock = _optional_bool(
        _reward_field(reward, "isInStock", "is_in_stock", "inStock")
    )

    if enabled is False:
        return False
    if paused is True:
        return False
    if in_stock is False:
        return False

    availability = reward.get("availability")
    if isinstance(availability, dict):
        availability_stock = _optional_bool(
            _reward_field(
                availability,
                "isInStock",
                "is_in_stock",
                "inStock",
            )
        )
        availability_paused = _optional_bool(
            _reward_field(
                availability,
                "isPaused",
                "is_paused",
                "paused",
            )
        )

        if availability_stock is False or availability_paused is True:
            return False

    return True


def _most_expensive_reward(
    data: dict[str, Any],
) -> tuple[str | None, int | None]:
    """Return the highest-cost reward currently visible to the viewer."""

    rewards: list[tuple[str, int]] = []
    seen: set[tuple[str, int]] = set()

    for collection in _iter_reward_collections(data):
        for reward in _iter_reward_nodes(collection):
            if not _reward_is_available(reward):
                continue

            title = str(
                _reward_field(reward, "title", "name") or ""
            ).strip()
            cost = _reward_cost(reward)

            if not title or cost is None:
                continue

            key = (title.casefold(), cost)
            if key in seen:
                continue

            seen.add(key)
            rewards.append((title, cost))

    if not rewards:
        return None, None

    title, cost = max(
        rewards,
        key=lambda item: (item[1], item[0].casefold()),
    )
    return title, cost


def _community_points(data: dict[str, Any]) -> dict[str, Any] | None:
    root = data.get("data")
    if not isinstance(root, dict):
        return None

    community = root.get("community")
    if isinstance(community, dict):
        channel = community.get("channel")
        if isinstance(channel, dict):
            points = channel.get("self", {}).get("communityPoints")
            if isinstance(points, dict):
                return points

    # Запасний розбір на випадок невеликої зміни структури Twitch.
    for value in root.values():
        if not isinstance(value, dict):
            continue
        points = value.get("self", {}).get("communityPoints")
        if isinstance(points, dict):
            return points

    return None


async def fetch_channel_points_context(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    channel_login: str,
) -> ChannelPointsSnapshot:
    login = channel_login.strip()
    if not login:
        raise ValueError("Не передано логін Twitch-каналу")

    payload = _operation(
        "ChannelPointsContext",
        CHANNEL_POINTS_CONTEXT_HASH,
        {"channelLogin": login},
    )
    response = await _post_gql(session, headers, payload)
    points = _community_points(response)

    if not points:
        raise RuntimeError(
            "Channel Points недоступні для цього каналу або Twitch змінив відповідь"
        )

    try:
        balance = int(points.get("balance") or 0)
    except (TypeError, ValueError) as error:
        raise RuntimeError("Не вдалося прочитати баланс Channel Points") from error

    claim = points.get("availableClaim")
    claim_id: str | None = None
    if isinstance(claim, dict) and claim.get("id"):
        claim_id = str(claim["id"])

    reward_title, reward_cost = _most_expensive_reward(response)

    return ChannelPointsSnapshot(
        balance=balance,
        claim_id=claim_id,
        reward_title=reward_title,
        reward_cost=reward_cost,
    )


async def fetch_channel_points(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    channel_login: str,
) -> tuple[int, str | None]:
    """
    Backwards-compatible balance/claim helper used by Predictions and PubSub.
    """

    snapshot = await fetch_channel_points_context(
        session,
        headers,
        channel_login,
    )
    return snapshot.balance, snapshot.claim_id


async def claim_channel_points_bonus(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    channel_id: str,
    claim_id: str,
) -> None:
    if not channel_id.strip():
        raise ValueError("Не передано ID Twitch-каналу")
    if not claim_id.strip():
        raise ValueError("Не передано ID бонусу")

    payload = _operation(
        "ClaimCommunityPoints",
        CLAIM_COMMUNITY_POINTS_HASH,
        {
            "input": {
                "channelID": channel_id,
                "claimID": claim_id,
            }
        },
    )
    await _post_gql(session, headers, payload)


async def update_channel_points(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    *,
    login: str,
    channel_id: str,
    tracker: ChannelPointsTracker,
    auto_claim: bool = True,
) -> ChannelPointsResult:
    """
    Refresh balance and optionally claim the orange bonus chest.

    The first observed balance is treated as the session baseline. Therefore,
    the session delta includes rewards claimed after NYXOR starts.
    """

    snapshot = await fetch_channel_points_context(
        session,
        headers,
        login,
    )
    balance = snapshot.balance
    claim_id = snapshot.claim_id
    reward_title = snapshot.reward_title
    reward_cost = snapshot.reward_cost
    session_delta = tracker.update(login, balance)

    claimed = False
    bonus_count = tracker.bonus_count(login)
    bonus_status = (
        f"✓ коробок: {bonus_count}" if bonus_count else "очікування"
    )

    if claim_id:
        if auto_claim and channel_id.strip():
            if tracker.reserve_bonus_claim(login, claim_id):
                try:
                    await claim_channel_points_bonus(
                        session,
                        headers,
                        channel_id=channel_id,
                        claim_id=claim_id,
                    )
                except Exception:
                    tracker.release_bonus_claim(login, claim_id)
                    raise

                claimed = True
                bonus_count = tracker.confirm_bonus_claim(login, claim_id)
                bonus_status = f"✓ коробок: {bonus_count}"

                # Twitch may update the balance with a small delay.
                await asyncio.sleep(0.6)
                try:
                    refreshed = await fetch_channel_points_context(
                        session,
                        headers,
                        login,
                    )
                    balance = refreshed.balance
                    reward_title = refreshed.reward_title
                    reward_cost = refreshed.reward_cost
                    session_delta = tracker.update(login, balance)
                except Exception:
                    # A later NYXOR cycle will refresh the balance.
                    pass
        elif auto_claim:
            bonus_status = "немає ID каналу"
        else:
            bonus_status = "доступний"

    return ChannelPointsResult(
        balance=balance,
        session_delta=session_delta,
        bonus_status=bonus_status,
        claimed_bonus=claimed,
        bonus_count=bonus_count,
        reward_title=reward_title,
        reward_cost=reward_cost,
    )
