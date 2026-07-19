from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import aiohttp

from nyxor_points import (
    ChannelPointsTracker,
    _operation,
    _post_gql,
    claim_channel_points_bonus,
    fetch_channel_points,
)


PUBSUB_URL = "wss://pubsub-edge.twitch.tv/v1"

JOIN_RAID_HASH = (
    "c6a332a86d1087fbbb1a8623aa01bd1313d2386e7c63be60fdb2d1901f01a4ae"
)
CLAIM_MOMENT_HASH = (
    "e2d67415aead910f7f9ceb45a77b750a1e1d9622c936d832328a0689e054db62"
)
MAKE_PREDICTION_HASH = (
    "b44682ecc88358817009f20e69d75081b1e58825bb40aa53d5dbadcc17c881d8"
)

logger = logging.getLogger("NYXOR.rewards")


@dataclass(slots=True)
class PredictionConfig:
    enabled: bool = False
    strategy: str = "most_voted"
    percentage: float = 2.0
    max_points: int = 1000
    minimum_balance: int = 5000
    reserve_points: int = 3000
    seconds_before_close: int = 20

    @classmethod
    def from_settings(cls, value: Any) -> "PredictionConfig":
        data = value if isinstance(value, dict) else {}

        strategy = str(data.get("strategy") or "most_voted").strip().lower()
        if strategy not in {"most_voted", "most_points"}:
            strategy = "most_voted"

        try:
            percentage = float(data.get("percentage", 2.0))
        except (TypeError, ValueError):
            percentage = 2.0

        def as_int(key: str, default: int) -> int:
            try:
                return int(data.get(key, default))
            except (TypeError, ValueError):
                return default

        return cls(
            enabled=bool(data.get("enabled", False)),
            strategy=strategy,
            percentage=max(0.0, min(100.0, percentage)),
            max_points=max(10, as_int("max_points", 1000)),
            minimum_balance=max(0, as_int("minimum_balance", 5000)),
            reserve_points=max(0, as_int("reserve_points", 3000)),
            seconds_before_close=max(
                3,
                min(120, as_int("seconds_before_close", 20)),
            ),
        )


@dataclass(slots=True)
class PredictionEvent:
    event_id: str
    title: str
    status: str
    closes_at: float
    outcomes: list[dict[str, Any]]
    channel_id: str
    channel_login: str
    bet_placed: bool = False


class TwitchRewardsEngine:
    """One PubSub connection for rewards of the currently watched channel."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        gql_headers: dict[str, str],
        *,
        auth_token: str,
        user_id: str,
        tracker: ChannelPointsTracker,
        settings: dict[str, Any] | None = None,
    ) -> None:
        config = settings if isinstance(settings, dict) else {}

        self.session = session
        self.gql_headers = gql_headers
        self.auth_token = auth_token
        self.user_id = user_id
        self.tracker = tracker

        self.enabled = bool(config.get("enabled", True))
        self.auto_claim_bonus = bool(config.get("auto_claim_bonus", True))
        self.follow_raids = bool(config.get("follow_raids", True))
        self.claim_moments = bool(config.get("claim_moments", True))
        self.prediction = PredictionConfig.from_settings(
            config.get("predictions")
        )

        self._channel: dict[str, Any] | None = None
        self._mode = ""
        self._task: asyncio.Task[None] | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._prediction_tasks: dict[str, asyncio.Task[None]] = {}
        self._prediction_events: dict[str, PredictionEvent] = {}
        self._claimed_moment_ids: set[str] = set()
        self._handled_raid_ids: set[str] = set()
        self._pending_raid_login = ""
        self._stopping = False

        self._status: dict[str, str] = {
            "pubsub": "вимкнено" if not self.enabled else "очікування",
            "bonus": "очікування",
            "streak": "—",
            "moments": "0",
            "raid": "—",
            "prediction": (
                "очікування" if self.prediction.enabled else "вимкнено"
            ),
        }

    @property
    def channel_id(self) -> str:
        if not isinstance(self._channel, dict):
            return ""
        return str(self._channel.get("channel_id") or "")

    @property
    def channel_login(self) -> str:
        if not isinstance(self._channel, dict):
            return ""
        return str(self._channel.get("login") or "")

    async def set_channel(
        self,
        channel: dict[str, Any] | None,
        mode: str,
    ) -> None:
        self._mode = mode

        new_id = (
            str(channel.get("channel_id") or "")
            if isinstance(channel, dict)
            else ""
        )
        old_id = self.channel_id

        if new_id == old_id:
            if isinstance(channel, dict):
                self._channel = dict(channel)
            return

        await self._stop_socket()
        self._channel = dict(channel) if isinstance(channel, dict) else None
        self._cancel_prediction_tasks()
        self._prediction_events.clear()

        if not self.enabled or not new_id:
            self._status["pubsub"] = (
                "вимкнено" if not self.enabled else "очікування"
            )
            return

        self._status["pubsub"] = "підключення"
        self._status["raid"] = "—"
        self._status["prediction"] = (
            "очікування" if self.prediction.enabled else "вимкнено"
        )
        self._task = asyncio.create_task(
            self._run_socket(),
            name=f"nyxor-pubsub-{new_id}",
        )

    async def stop(self) -> None:
        self._stopping = True
        await self._stop_socket()
        self._cancel_prediction_tasks()

    def snapshot(self) -> dict[str, str]:
        login = self.channel_login
        bonus_count = self.tracker.bonus_count(login)
        if bonus_count > 0:
            self._status["bonus"] = f"✓ коробок: {bonus_count}"

        moment_count = self.tracker.moment_count(login)
        if moment_count > 0:
            self._status["moments"] = f"✓ {moment_count}"

        streak_points = self.tracker.streak_points(login)
        if streak_points > 0:
            self._status["streak"] = f"✓ +{streak_points}"

        return dict(self._status)

    def consume_raid_target(self) -> str:
        login = self._pending_raid_login
        self._pending_raid_login = ""
        return login

    async def _stop_socket(self) -> None:
        task = self._task
        self._task = None

        ws = self._ws
        self._ws = None
        if ws is not None and not ws.closed:
            try:
                await ws.close()
            except Exception:
                pass

        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.debug("PubSub task stop failed", exc_info=True)

    def _cancel_prediction_tasks(self) -> None:
        for task in self._prediction_tasks.values():
            if not task.done():
                task.cancel()
        self._prediction_tasks.clear()

    async def _run_socket(self) -> None:
        while not self._stopping and self.channel_id:
            try:
                self._status["pubsub"] = "підключення"
                async with self.session.ws_connect(
                    PUBSUB_URL,
                    heartbeat=None,
                    autoping=True,
                ) as ws:
                    self._ws = ws
                    await self._listen(ws)
                    self._status["pubsub"] = "✓ підключено"

                    ping_task = asyncio.create_task(self._ping_loop(ws))
                    try:
                        async for message in ws:
                            if message.type == aiohttp.WSMsgType.TEXT:
                                reconnect = await self._handle_message(message.data)
                                if reconnect:
                                    break
                            elif message.type in {
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.CLOSE,
                                aiohttp.WSMsgType.ERROR,
                            }:
                                break
                    finally:
                        ping_task.cancel()
                        try:
                            await ping_task
                        except asyncio.CancelledError:
                            pass

            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.debug("PubSub failure: %s", error, exc_info=True)
                self._status["pubsub"] = f"перепідключення: {str(error)[:28]}"
            finally:
                self._ws = None

            if not self._stopping and self.channel_id:
                await asyncio.sleep(5)

    async def _listen(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        user_topics = [f"community-points-user-v1.{self.user_id}"]
        if self.prediction.enabled:
            user_topics.append(f"predictions-user-v1.{self.user_id}")

        channel_topics: list[str] = []
        channel_id = self.channel_id
        if self.follow_raids:
            channel_topics.append(f"raid.{channel_id}")
        if self.claim_moments:
            channel_topics.append(
                f"community-moments-channel-v1.{channel_id}"
            )
        if self.prediction.enabled:
            channel_topics.append(f"predictions-channel-v1.{channel_id}")

        await ws.send_json(
            {
                "type": "LISTEN",
                "nonce": secrets.token_hex(8),
                "data": {
                    "topics": user_topics,
                    "auth_token": self.auth_token,
                },
            }
        )

        if channel_topics:
            await ws.send_json(
                {
                    "type": "LISTEN",
                    "nonce": secrets.token_hex(8),
                    "data": {"topics": channel_topics},
                }
            )

    async def _ping_loop(
        self,
        ws: aiohttp.ClientWebSocketResponse,
    ) -> None:
        while not ws.closed:
            await asyncio.sleep(240)
            await ws.send_json({"type": "PING"})

    async def _handle_message(self, raw: str) -> bool:
        try:
            outer = json.loads(raw)
        except json.JSONDecodeError:
            return False

        message_type = str(outer.get("type") or "")

        if message_type == "PONG":
            return False
        if message_type == "RECONNECT":
            self._status["pubsub"] = "Twitch просить перепідключення"
            return True
        if message_type == "RESPONSE":
            error = str(outer.get("error") or "")
            if error:
                self._status["pubsub"] = f"помилка: {error[:36]}"
                logger.warning("Twitch PubSub LISTEN error: %s", error)
            return False
        if message_type != "MESSAGE":
            return False

        data = outer.get("data")
        if not isinstance(data, dict):
            return False

        topic = str(data.get("topic") or "")
        encoded = data.get("message")
        if not isinstance(encoded, str):
            return False

        try:
            inner = json.loads(encoded)
        except json.JSONDecodeError:
            return False

        event_type = str(inner.get("type") or "")
        payload = inner.get("data")
        payload = payload if isinstance(payload, dict) else {}

        try:
            if topic.startswith("community-points-user-v1."):
                await self._handle_points(event_type, payload)
            elif topic.startswith("raid."):
                await self._handle_raid(event_type, inner)
            elif topic.startswith("community-moments-channel-v1."):
                await self._handle_moment(event_type, payload)
            elif topic.startswith("predictions-channel-v1."):
                await self._handle_prediction_channel(event_type, payload)
            elif topic.startswith("predictions-user-v1."):
                self._handle_prediction_user(event_type, payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Reward event failed: topic=%s type=%s",
                topic,
                event_type,
            )

        return False

    def _payload_channel_id(self, payload: dict[str, Any]) -> str:
        direct = payload.get("channel_id")
        if direct:
            return str(direct)

        for key in ("balance", "claim", "prediction"):
            value = payload.get(key)
            if isinstance(value, dict) and value.get("channel_id"):
                return str(value["channel_id"])

        return ""

    async def _handle_points(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        payload_channel_id = self._payload_channel_id(payload)
        if payload_channel_id and payload_channel_id != self.channel_id:
            return

        if event_type in {"points-earned", "points-spent"}:
            balance_data = payload.get("balance")
            if isinstance(balance_data, dict):
                try:
                    balance = int(balance_data.get("balance") or 0)
                    self.tracker.update(self.channel_login, balance)
                except (TypeError, ValueError):
                    pass

            gain = payload.get("point_gain")
            if event_type == "points-earned" and isinstance(gain, dict):
                reason = str(gain.get("reason_code") or "")
                try:
                    earned = int(gain.get("total_points") or 0)
                except (TypeError, ValueError):
                    earned = 0

                if reason == "WATCH_STREAK" and earned > 0:
                    total = self.tracker.record_streak(
                        self.channel_login,
                        earned,
                    )
                    self._status["streak"] = f"✓ +{total}"
                    logger.info(
                        "Watch Streak +%s on %s",
                        earned,
                        self.channel_login,
                    )
            return

        if event_type != "claim-available" or not self.auto_claim_bonus:
            return

        claim = payload.get("claim")
        if not isinstance(claim, dict):
            return

        claim_id = str(claim.get("id") or "")
        channel_id = str(claim.get("channel_id") or self.channel_id)
        if claim_id and channel_id == self.channel_id:
            await self._claim_bonus(claim_id)

    async def _claim_bonus(self, claim_id: str) -> None:
        login = self.channel_login
        if not self.tracker.reserve_bonus_claim(login, claim_id):
            return

        try:
            await claim_channel_points_bonus(
                self.session,
                self.gql_headers,
                self.channel_id,
                claim_id,
            )
        except Exception:
            self.tracker.release_bonus_claim(login, claim_id)
            self._status["bonus"] = "помилка claim"
            raise

        count = self.tracker.confirm_bonus_claim(login, claim_id)
        self._status["bonus"] = f"✓ коробок: {count}"
        logger.info("Claimed bonus #%s on %s", count, login)

    async def _handle_moment(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.claim_moments or event_type != "active":
            return

        moment_id = str(payload.get("moment_id") or "")
        if not moment_id or moment_id in self._claimed_moment_ids:
            return

        response = await _post_gql(
            self.session,
            self.gql_headers,
            _operation(
                "CommunityMomentCallout_Claim",
                CLAIM_MOMENT_HASH,
                {"input": {"momentID": moment_id}},
            ),
        )
        del response

        self._claimed_moment_ids.add(moment_id)
        count = self.tracker.record_moment(self.channel_login, moment_id)
        self._status["moments"] = f"✓ {count}"
        logger.info("Claimed Moment #%s on %s", count, self.channel_login)

    async def _handle_raid(
        self,
        event_type: str,
        inner: dict[str, Any],
    ) -> None:
        if not self.follow_raids or event_type != "raid_update_v2":
            return

        raid = inner.get("raid")
        if not isinstance(raid, dict):
            payload = inner.get("data")
            if isinstance(payload, dict):
                raid = payload.get("raid")
        if not isinstance(raid, dict):
            return

        raid_id = str(raid.get("id") or "")
        target_login = str(raid.get("target_login") or "").strip().lower()
        if not raid_id or not target_login:
            return
        if raid_id in self._handled_raid_ids:
            return
        self._handled_raid_ids.add(raid_id)

        if self._mode == "drops":
            self._status["raid"] = f"пропущено → {target_login} (Drops)"
            logger.info("Skipped raid to %s because Drops are active", target_login)
            return

        await _post_gql(
            self.session,
            self.gql_headers,
            _operation(
                "JoinRaid",
                JOIN_RAID_HASH,
                {"input": {"raidID": raid_id}},
            ),
        )
        self._pending_raid_login = target_login
        self._status["raid"] = f"→ {target_login}"
        logger.info("Joined raid to %s", target_login)

    async def _handle_prediction_channel(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.prediction.enabled:
            return

        event_data = payload.get("event")
        if not isinstance(event_data, dict):
            return

        event_id = str(event_data.get("id") or "")
        if not event_id:
            return

        status = str(event_data.get("status") or "")
        outcomes = event_data.get("outcomes")
        outcomes = outcomes if isinstance(outcomes, list) else []

        existing = self._prediction_events.get(event_id)
        if existing is not None:
            existing.status = status
            existing.outcomes = [
                item for item in outcomes if isinstance(item, dict)
            ]
            if status != "ACTIVE":
                task = self._prediction_tasks.pop(event_id, None)
                if task is not None and not task.done():
                    task.cancel()
            return

        if event_type != "event-created" or status != "ACTIVE":
            return

        title = str(event_data.get("title") or "Prediction").strip()
        closes_at = self._prediction_close_timestamp(event_data)
        event = PredictionEvent(
            event_id=event_id,
            title=title,
            status=status,
            closes_at=closes_at,
            outcomes=[item for item in outcomes if isinstance(item, dict)],
            channel_id=self.channel_id,
            channel_login=self.channel_login,
        )
        self._prediction_events[event_id] = event

        delay = max(
            0.0,
            closes_at - time.time() - self.prediction.seconds_before_close,
        )
        self._status["prediction"] = f"відкрите: {title[:28]}"
        task = asyncio.create_task(
            self._prediction_after_delay(event_id, delay),
            name=f"nyxor-prediction-{event_id}",
        )
        self._prediction_tasks[event_id] = task

    def _prediction_close_timestamp(self, event: dict[str, Any]) -> float:
        created_at = str(event.get("created_at") or "")
        try:
            created = datetime.fromisoformat(
                created_at.replace("Z", "+00:00")
            )
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            created_timestamp = created.timestamp()
        except ValueError:
            created_timestamp = time.time()

        try:
            window = float(event.get("prediction_window_seconds") or 0)
        except (TypeError, ValueError):
            window = 0.0

        return created_timestamp + max(0.0, window)

    async def _prediction_after_delay(
        self,
        event_id: str,
        delay: float,
    ) -> None:
        try:
            await asyncio.sleep(delay)
            await self._place_prediction(event_id)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._status["prediction"] = f"помилка: {str(error)[:34]}"
            logger.exception("Prediction failed")
        finally:
            self._prediction_tasks.pop(event_id, None)

    async def _place_prediction(self, event_id: str) -> None:
        event = self._prediction_events.get(event_id)
        if event is None or event.status != "ACTIVE" or event.bet_placed:
            return
        if event.channel_id != self.channel_id:
            return

        outcomes = [
            item
            for item in event.outcomes
            if isinstance(item, dict) and item.get("id")
        ]
        if len(outcomes) < 2:
            self._status["prediction"] = "пропущено: немає варіантів"
            return

        key = (
            "total_points"
            if self.prediction.strategy == "most_points"
            else "total_users"
        )

        def metric(item: dict[str, Any]) -> tuple[int, int]:
            try:
                primary = int(item.get(key) or 0)
            except (TypeError, ValueError):
                primary = 0
            try:
                secondary = int(item.get("total_points") or 0)
            except (TypeError, ValueError):
                secondary = 0
            return primary, secondary

        outcome = max(outcomes, key=metric)
        if metric(outcome) == (0, 0):
            self._status["prediction"] = "пропущено: немає статистики"
            return

        balance, _ = await fetch_channel_points(
            self.session,
            self.gql_headers,
            event.channel_login,
        )

        if balance < self.prediction.minimum_balance:
            self._status["prediction"] = (
                f"пропущено: баланс {balance}"
            )
            return

        percentage_amount = int(
            balance * self.prediction.percentage / 100.0
        )
        spendable = max(0, balance - self.prediction.reserve_points)
        amount = min(
            self.prediction.max_points,
            spendable,
            percentage_amount,
        )

        if amount < 10:
            self._status["prediction"] = "пропущено: ставка < 10"
            return

        response = await _post_gql(
            self.session,
            self.gql_headers,
            _operation(
                "MakePrediction",
                MAKE_PREDICTION_HASH,
                {
                    "input": {
                        "eventID": event.event_id,
                        "outcomeID": str(outcome["id"]),
                        "points": amount,
                        "transactionID": secrets.token_hex(16),
                    }
                },
            ),
        )

        make_data = response.get("data", {}).get("makePrediction")
        if isinstance(make_data, dict) and make_data.get("error"):
            error = make_data["error"]
            if isinstance(error, dict):
                error = error.get("code") or error
            raise RuntimeError(str(error))

        event.bet_placed = True
        title = str(outcome.get("title") or "варіант")
        self._status["prediction"] = f"✓ {amount} → {title[:24]}"
        logger.info(
            "Placed prediction: %s points on %s (%s)",
            amount,
            title,
            event.title,
        )

    def _handle_prediction_user(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        if not self.prediction.enabled:
            return

        prediction = payload.get("prediction")
        if not isinstance(prediction, dict):
            return

        if event_type == "prediction-made":
            self._status["prediction"] = "✓ ставка підтверджена"
            return

        if event_type != "prediction-result":
            return

        result = prediction.get("result")
        if not isinstance(result, dict):
            return

        result_type = str(result.get("type") or "RESULT")
        try:
            points_won = int(result.get("points_won") or 0)
        except (TypeError, ValueError):
            points_won = 0

        if result_type == "WIN":
            self._status["prediction"] = f"виграш: +{points_won}"
        elif result_type == "REFUND":
            self._status["prediction"] = "повернення ставки"
        else:
            self._status["prediction"] = "програш"
