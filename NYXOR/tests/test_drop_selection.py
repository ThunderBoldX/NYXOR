from __future__ import annotations

import copy
import json
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
            with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("solo")])), \
                 patch.object(core, "fetch_streamer_channel", AsyncMock(return_value=channel("shared"))), \
                 patch.object(core, "gql_request_retry", AsyncMock(return_value={"data": {"channel": {"viewerDropCampaigns": available}}})):
                result = await core.pick_target(["Rust"], value, {}, [], "", "", session=object(), headers={})
            self.assertEqual(result[1]["login"], expected)

    async def test_offline_extra_and_failed_lookup_preserve_directory_fallback(self):
        value = states(campaign("a", ["shared"]), campaign("b"))
        for response in [None, RuntimeError("offline")]:
            fetch = AsyncMock(side_effect=response) if isinstance(response, Exception) else AsyncMock(return_value=response)
            with patch.object(core, "fetch_channels_retry", AsyncMock(return_value=[channel("solo")])), \
                 patch.object(core, "fetch_streamer_channel", fetch):
                result = await core.pick_target(["Rust"], value, {}, [], "", "", session=object(), headers={})
            self.assertEqual(result[1]["login"], "solo")


if __name__ == "__main__":
    unittest.main()
