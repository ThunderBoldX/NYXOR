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


async def fetch_channel_points(
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    channel_login: str,
) -> tuple[int, str | None]:
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

    return balance, claim_id


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

    balance, claim_id = await fetch_channel_points(session, headers, login)
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
                    balance, _ = await fetch_channel_points(session, headers, login)
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
    )
