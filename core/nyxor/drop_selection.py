"""Channel eligibility and coverage for simultaneous Drops campaigns."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def allowed_channels(campaign: dict[str, Any]) -> list[dict[str, Any]] | None:
    """None means unrestricted; an enabled empty list admits no channels."""
    allow = campaign.get("allow")
    if not isinstance(allow, dict) or allow.get("isEnabled") is False:
        return None
    channels = allow.get("channels")
    if not channels and allow.get("isEnabled") is not True:
        return None
    return [item for item in channels or [] if isinstance(item, dict)]


def channel_drops(state: dict[str, Any], channel: dict[str, Any]) -> list[dict[str, Any]]:
    """Return earnable drops on this channel, preserving the inventory order."""
    now = datetime.now(timezone.utc)
    login = str(channel.get("login") or "").casefold()
    channel_id = str(channel.get("channel_id") or "")
    if str(channel.get("game") or "").casefold() != str(state.get("game") or "").casefold():
        return []
    available = channel.get("available_campaign_ids")
    result = []
    for drop in state.get("mineable") or []:
        if not drop["starts_at"] <= now < drop["ends_at"]:
            continue
        if available is not None and drop["campaign_id"] not in available:
            continue
        allowed = drop.get("allowed_channels")
        if allowed is not None and not any(
            (channel_id and str(item.get("id") or "") == channel_id)
            or (login and str(item.get("login") or "").casefold() == login)
            for item in allowed
        ):
            continue
        result.append(drop)
    return result


def best_coverage_channels(
    state: dict[str, Any], channels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Count campaigns, not individual rewards within the same campaign."""
    best = 0
    result = []
    for channel in channels:
        count = len({drop["campaign_id"] for drop in channel_drops(state, channel)})
        if count > best:
            best, result = count, [channel]
        elif count == best and count:
            result.append(channel)
    return result


def progress_snapshot(state: dict[str, Any] | None, channel: dict[str, Any]) -> list[dict[str, Any]]:
    """JSON-safe progress from Twitch, without locally invented watch minutes."""
    return [
        {key: drop[key] for key in ("campaign_id", "campaign", "drop_id", "drop", "current", "required")}
        for drop in channel_drops(state, channel)
    ] if state else []
