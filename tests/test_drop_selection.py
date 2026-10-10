from __future__ import annotations

import copy
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import nyxor_core as core
from nyxor.drop_selection import best_coverage_channels, channel_drops, progress_snapshot


def campaign(identifier, logins=None, *, game="Rust", **changes):
    now = datetime.now(timezone.utc)
    value = {
        "id": identifier, "name": identifier, "status": "ACTIVE",
        "game": {"name": game}, "self": {"isAccountConnected": True},
        "startAt": (now - timedelta(days=1)).isoformat(),
        "endAt": (now + timedelta(days=1)).isoformat(),
        "allow": {"isEnabled": logins is not None, "channels": [
            {"id": login, "login": login} for login in logins or []
        ]},
        "timeBasedDrops": [{"id": identifier + "-reward", "name": "Reward " + identifier,
                            "requiredMinutesWatched": 60,
                            "self": {"currentMinutesWatched": 10, "isClaimed": False}}],
    }
    value.update(changes)
    return value


def channel(login, *, game="Rust", viewers=10):
    return {"channel_id": login, "login": login, "stream_id": login + "-live",
            "game": game, "viewers": viewers}


def states(*campaigns):
    return core.build_game_states(list(campaigns), {}, {})


class CoverageTests(unittest.TestCase):
    def test_current_progress_keeps_all_benefit_images(self):
        value = campaign('a', ['shared'])
        value['timeBasedDrops'][0]['benefitEdges'] = [
            {'benefit': {'id': str(i), 'name': f'Item {i}', 'imageAssetURL': f'https://static-cdn.jtvnw.net/reward-{i}.png'}}
            for i in range(2)
        ]
        result = progress_snapshot(states(value)['Rust'], channel('shared'))
        self.assertEqual(len(result[0]['benefits']), 2)
        self.assertEqual(result[0]['benefits'][1]['image_url'], 'https://static-cdn.jtvnw.net/reward-1.png')
        self.assertEqual(result[0]['current'], 10)

    def test_shared_channel_wins_over_popularity(self):
        state = states(campaign("a", ["shared"]), campaign("b", ["popular", "shared"]))["Rust"]
        result = best_coverage_channels(state, [channel("popular", viewers=10000), channel("shared")])
        self.assertEqual([item["login"] for item in result], ["shared"])

    def test_counts_campaigns_not_rewards(self):
        a = campaign("a", ["solo"])
        a["timeBasedDrops"] *= 5
        state = states(a, campaign("b", ["shared"]), campaign("c", ["shared"]))["Rust"]
        self.assertEqual(best_coverage_channels(state, [channel("solo"), channel("shared")])[0]["login"], "shared")

    def test_unrestricted_and_restricted_overlap(self):
        state = states(campaign("a"), campaign("b", ["shared"]))["Rust"]
        self.assertEqual(len(channel_drops(state, channel("shared"))), 2)
        self.assertEqual(len(channel_drops(state, channel("other"))), 1)

    def test_id_match_and_case_insensitive_login(self):
        state = states(campaign("a", ["shared"]))["Rust"]
        self.assertEqual(len(channel_drops(state, channel("SHARED"))), 1)
        renamed = channel("renamed")
        renamed["channel_id"] = "shared"
        self.assertEqual(len(channel_drops(state, renamed)), 1)

    def test_wrong_category_and_empty_enabled_allowlist(self):
        self.assertEqual(channel_drops(states(campaign("a"))["Rust"], channel("one", game="Other")), [])
        self.assertEqual(channel_drops(states(campaign("a", []))["Rust"], channel("one")), [])

    def test_completed_unlinked_expired_and_future_are_not_coverage(self):
        now = datetime.now(timezone.utc)
        complete = campaign("complete", ["shared"])
        complete["timeBasedDrops"][0]["self"]["isClaimed"] = True
        value = states(complete, campaign("expired", endAt=(now - timedelta(hours=1)).isoformat()),
                       campaign("future", startAt=(now + timedelta(hours=1)).isoformat()),
                       campaign("unlinked", self={"isAccountConnected": False}, accountLinkURL="https://example.test"),
                       campaign("ready", timeBasedDrops=[{"id": "r", "requiredMinutesWatched": 60, "self": {"currentMinutesWatched": 60}}]))
        self.assertEqual(channel_drops(value["Rust"], channel("shared")), [])

    def test_campaign_window_caps_drop_window(self):
        a = campaign("a", endAt=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat())
        a["timeBasedDrops"][0]["endAt"] = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.assertEqual(states(a)["Rust"]["mineable"], [])

    def test_prerequisite_requires_claim_and_inventory_overrides_cached_progress(self):
        a = campaign("a")
        second = copy.deepcopy(a["timeBasedDrops"][0])
        second.update(id="second", preconditionDrops=[{"id": "a-reward"}])
        a["timeBasedDrops"].append(second)
        self.assertEqual([d["drop_id"] for d in states(a)["Rust"]["mineable"]], ["a-reward"])
        updated = core.build_game_states([a], {("a", "a-reward"): {"isClaimed": True}}, {})
        self.assertEqual([d["drop_id"] for d in updated["Rust"]["mineable"]], ["second"])

    def test_snapshot_only_displays_selected_channel_rewards(self):
        state = states(campaign("a", ["one"]), campaign("b", ["two"]))["Rust"]
        snapshot = progress_snapshot(state, channel("two"))
        self.assertEqual([d["campaign_id"] for d in snapshot], ["b"])
        self.assertEqual(snapshot[0]["current"], 10)
        json.dumps(snapshot)
        self.assertIn("Reward b", core.active_drop_text(state, channel("two")))

    def test_expiration_rechecked_between_snapshots(self):
        state = states(campaign("a"))["Rust"]
        state["mineable"][0]["ends_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertEqual(channel_drops(state, channel("one")), [])


class TargetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        cache = patch.dict(core.DROP_AVAILABILITY_CACHE, {}, clear=True)
        cache.start()
        self.addCleanup(cache.stop)

    async def test_worldoftanks_cyganzor_do_not_ping_pong_on_estimated_coverage(self):
        value = states(campaign("a", game="World of Tanks"), campaign("b", game="World of Tanks"))
        current = channel("worldoftanks", game="World of Tanks")
        directory = AsyncMock(side_effect=lambda game: [channel(
            "cyganzor" if current["login"] == "worldoftanks" else "worldoftanks", game=game)])
        live = AsyncMock(side_effect=lambda session, headers, login: channel(login, game="World of Tanks"))
        # Both channels actually offer only A; the generic Drops directory
        # contains no per-campaign information and initially appears to offer A+B.
        available = AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": [{"id": "a"}]}}})
        with patch.object(core, "fetch_channels_retry", directory), \
             patch.object(core, "fetch_streamer_channel", live), \
             patch.object(core, "gql_request_retry", available):
            for _ in range(8):
                result = await core.pick_target(["World of Tanks"], value, {}, [], "World of Tanks", current["login"], session=object(), headers={}, current_channel=current)
                self.assertEqual(result[1]["login"], "worldoftanks")
                current = result[1]

    async def test_verified_shared_stream_improves_coverage_without_bouncing_back(self):
        value = states(campaign("a"), campaign("b"))
        async def available(session, query, headers, **kw):
            return {"data": {"channel": {"viewerDropCampaigns": [{"id": i} for i in (["a", "b"] if query["variables"]["channelID"] == "shared" else ["a"])]}}}
        current = channel("solo")
        with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("solo", viewers=1000), channel("shared")])), \
             patch.object(core, "gql_request_retry", AsyncMock(side_effect=available)):
            for _ in range(4):
                result = await core.pick_target(["Rust"], value, {"Rust": "solo"}, ["solo"], "Rust", current["login"], session=object(), headers={}, current_channel=current)
                self.assertEqual(result[1]["login"], "shared")
                self.assertEqual(len(channel_drops(value["Rust"], result[1])), 2)
                current = result[1]

    async def test_drops_tag_alone_does_not_select_an_unavailable_campaign(self):
        with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("tagged")])), \
             patch.object(core, "gql_request_retry", AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": []}}})):
            result = await core.pick_target(["Rust"], states(campaign("a")), {}, [], "", "", session=object(), headers={})
        self.assertIsNone(result)

    async def test_availability_cache_is_scoped_to_account_stream_and_freshness(self):
        response = {"data": {"channel": {"viewerDropCampaigns": [{"id": "a"}]}}}
        with patch.object(core, "gql_request_retry", AsyncMock(return_value=response)) as request:
            for _ in range(4):
                await core.confirmed_drop_channel(object(), {"Authorization": "fixture-one"}, channel("one"))
            self.assertEqual(request.await_count, 1)
            await core.confirmed_drop_channel(object(), {"Authorization": "fixture-two"}, channel("one"))
            await core.confirmed_drop_channel(object(), {"Authorization": "fixture-one"}, {**channel("one"), "stream_id": "new-live"})
            key = ("fixture-one", "one", "one-live")
            core.DROP_AVAILABILITY_CACHE[key] = time.monotonic() - core.DROP_AVAILABILITY_CACHE_TTL - 1, ["a"]
            await core.confirmed_drop_channel(object(), {"Authorization": "fixture-one"}, channel("one"))
            self.assertEqual(request.await_count, 4)

    async def test_failed_or_malformed_availability_is_not_cached_as_disabled(self):
        with patch.object(core, "gql_request_retry", AsyncMock(side_effect=[RuntimeError("network"), {"data": {}}, {"data": {"channel": {"viewerDropCampaigns": [{"id": "a"}]}}}])) as request:
            for _ in range(2):
                with self.assertRaises(RuntimeError):
                    await core.confirmed_drop_channel(object(), {}, channel("one"))
                self.assertFalse(core.DROP_AVAILABILITY_CACHE)
            result = await core.confirmed_drop_channel(object(), {}, channel("one"))
            self.assertEqual(result["available_campaign_ids"], ["a"])
            self.assertEqual(request.await_count, 3)

    async def test_current_stream_wins_equal_coverage_over_new_preferences(self):
        with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("other"), channel("current")])):
            result = await core.pick_target(["Rust"], states(campaign("a")), {"Rust": "other"}, ["other"], "Rust", "current")
        self.assertEqual(result[1]["login"], "current")

    async def test_directory_changes_do_not_interrupt_unrestricted_current_stream(self):
        value = states(campaign("a"))
        current = channel("current")
        with patch.object(core, "fetch_channels_retry", AsyncMock(side_effect=[
                [channel("current"), channel("popular")], [channel("popular")], [], [channel("new")]])), \
             patch.object(core, "fetch_streamer_channel", AsyncMock(return_value=channel("current"))) as fetch, \
             patch.object(core, "gql_request_retry", AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": [{"id": "a"}]}}})):
            for _ in range(4):
                result = await core.pick_target(["Rust"], value, {}, [], "Rust", "current", session=object(), headers={}, current_channel=current)
                self.assertEqual(result[1]["login"], "current")
                current = result[1]
            self.assertEqual(fetch.await_count, 3)

    async def test_confirmed_offline_wrong_game_or_disabled_drops_use_replacement(self):
        for fresh, available in [(None, ["a"]), (channel("current", game="Other"), ["a"]), (channel("current"), [])]:
            core.DROP_AVAILABILITY_CACHE.clear()
            with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("other")])), \
                 patch.object(core, "fetch_streamer_channel", AsyncMock(return_value=fresh)), \
                 patch.object(core, "gql_request_retry", AsyncMock(side_effect=lambda session, query, headers, **kw: {"data": {"channel": {"viewerDropCampaigns": [{"id": i} for i in (available if query["variables"]["channelID"] == "current" else ["a"])]}}})):
                result = await core.pick_target(["Rust"], states(campaign("a")), {}, [], "Rust", "current", session=object(), headers={}, current_channel={**channel("current"), "_drop_checked_at": time.monotonic()})
            self.assertEqual(result[1]["login"], "other")

    async def test_temporary_probe_failure_has_bounded_grace(self):
        for age, expected in [(0, "current"), (core.DROP_CHANNEL_GRACE + 1, "other")]:
            core.DROP_AVAILABILITY_CACHE.clear()
            current = {**channel("current"), "_drop_checked_at": time.monotonic() - age}
            with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("other")])), \
                 patch.object(core, "fetch_streamer_channel", AsyncMock(side_effect=RuntimeError("network"))), \
                 patch.object(core, "gql_request_retry", AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": [{"id": "a"}]}}})):
                result = await core.pick_target(["Rust"], states(campaign("a")), {}, [], "Rust", "current", session=object(), headers={}, current_channel=current)
            self.assertEqual(result[1]["login"], expected)
            if expected == "current":
                self.assertEqual(result[1]["_drop_checked_at"], current["_drop_checked_at"])

    async def test_directory_error_checks_current_directly(self):
        with patch.object(core, "fetch_channels_retry", AsyncMock(side_effect=RuntimeError("directory failed"))), \
             patch.object(core, "fetch_streamer_channel", AsyncMock(return_value=channel("current"))), \
             patch.object(core, "gql_request_retry", AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": [{"id": "a"}]}}})):
            result = await core.pick_target(["Rust"], states(campaign("a")), {}, [], "Rust", "current", session=object(), headers={})
        self.assertEqual(result[1]["login"], "current")

    def test_discovery_failure_retains_only_recent_eligible_drops(self):
        value = states(campaign("a"))
        current = {**channel("current"), "_drop_checked_at": time.monotonic()}
        self.assertEqual(core.retained_drop_target(["Rust"], value, "Rust", current), ("Rust", current))
        self.assertIsNone(core.retained_drop_target([], value, "Rust", current))
        self.assertIsNone(core.retained_drop_target(["Rust"], value, "Rust", {**current, "_drop_checked_at": time.monotonic() - core.DROP_CHANNEL_GRACE - 1}))
        value["Rust"]["mineable"][0]["ends_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        self.assertIsNone(core.retained_drop_target(["Rust"], value, "Rust", current))

    async def test_overlap_beats_preferred_current_and_streamer_list(self):
        value = states(campaign("a", ["shared"]), campaign("b", ["solo", "shared"]))
        with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("solo"), channel("shared")])):
            result = await core.pick_target(["Rust"], value, {"Rust": "solo"}, ["solo"], "Rust", "solo")
        self.assertEqual(result[1]["login"], "shared")

    async def test_ties_preserve_existing_preferences_and_current_stream(self):
        with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("one"), channel("two")])):
            for preferred, configured, current in [({"Rust": "two"}, [], ""), ({}, ["two"], ""), ({}, [], "two")]:
                result = await core.pick_target(["Rust"], states(campaign("a")), preferred, configured, "Rust", current)
                self.assertEqual(result[1]["login"], "two")

    async def test_game_priority_preserved(self):
        value = states(campaign("a", game="First"), campaign("b"), campaign("c"))
        with patch.object(core, "fetch_channels_retry", AsyncMock(side_effect=lambda game: [channel("one", game=game)])):
            result = await core.pick_target(["First", "Rust"], value, {}, [], "", "")
        self.assertEqual(result[0], "First")

    async def test_no_eligible_channel_returns_none(self):
        with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("wrong")])):
            result = await core.pick_target(["Rust"], states(campaign("a", ["offline"])), {}, [], "", "")
        self.assertIsNone(result)

    async def test_shared_streamer_outside_directory_and_drops_disabled(self):
        value = states(campaign("a", ["shared"]), campaign("b", ["solo", "shared"]))
        for available, expected in [([{"id": "a"}, {"id": "b"}], "shared"), ([], "solo")]:
            core.DROP_AVAILABILITY_CACHE.clear()
            with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("solo")])), \
                 patch.object(core, "fetch_streamer_channel", AsyncMock(return_value=channel("shared"))), \
                 patch.object(core, "gql_request_retry", AsyncMock(side_effect=lambda session, query, headers, **kw: {"data": {"channel": {"viewerDropCampaigns": available if query["variables"]["channelID"] == "shared" else [{"id": "b"}]}}})):
                result = await core.pick_target(["Rust"], value, {}, [], "", "", session=object(), headers={})
            self.assertEqual(result[1]["login"], expected)

    async def test_offline_extra_and_failed_lookup_preserve_directory_fallback(self):
        value = states(campaign("a", ["shared"]), campaign("b"))
        for response in [None, RuntimeError("offline")]:
            core.DROP_AVAILABILITY_CACHE.clear()
            fetch = AsyncMock(side_effect=response) if isinstance(response, Exception) else AsyncMock(return_value=response)
            with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("solo")])), \
                 patch.object(core, "fetch_streamer_channel", fetch), \
                 patch.object(core, "gql_request_retry", AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": [{"id": "b"}]}}})):
                result = await core.pick_target(["Rust"], value, {}, [], "", "", session=object(), headers={})
            self.assertEqual(result[1]["login"], "solo")


if __name__ == "__main__":
    unittest.main()
