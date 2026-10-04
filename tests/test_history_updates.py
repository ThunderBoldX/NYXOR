import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from contextlib import ExitStack

import nyxor_core
from nyxor import paths, drop_history, channel_history
from nyxor.game_art import safe_art_url
from nyxor.storage import atomic_write_json


class HistoryUpdates(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        for name, value in [('DATA_DIR', self.root), ('HISTORY_PATH', self.root/'history.jsonl'),
                            ('STATS_PATH', self.root/'stats.json')]:
            self.stack.enter_context(patch.object(paths, name, value))

    async def test_all_claims_in_one_cycle_are_saved_with_their_game(self):
        campaigns = [dict(id=str(i), game={'name': game}, timeBasedDrops=[dict(
            id='drop', name=game+' reward', requiredMinutesWatched=10,
            self={'currentMinutesWatched': 10})]) for i, game in enumerate(['Rust', 'Warframe'])]
        with patch.object(nyxor_core, 'claim_one', AsyncMock(return_value=(True, 'ELIGIBLE_FOR_ALL'))):
            await nyxor_core.claim_ready_drops(None, {}, '1', campaigns, {})
            await nyxor_core.claim_ready_drops(None, {}, '1', campaigns, {})
        self.assertEqual([r['game'] for r in drop_history.read_claims('1')], ['Warframe', 'Rust'])
        self.assertEqual(json.loads(paths.STATS_PATH.read_text())['claims'], 2)

    async def test_lost_claim_response_recovers_from_next_inventory(self):
        drop = dict(id='d', name='Reward', requiredMinutesWatched=10, self={'currentMinutesWatched': 10})
        campaign = dict(id='c', game={'name': 'Rust'}, timeBasedDrops=[drop])
        with patch.object(nyxor_core, 'claim_one', AsyncMock(side_effect=TimeoutError)):
            await nyxor_core.claim_ready_drops(None, {}, '1', [campaign], {})
        self.assertEqual(drop_history.read_claims('1'), [])
        self.assertTrue(drop_history.pending_claim('1', 'c', 'd'))
        drop['self']['isClaimed'] = True
        await nyxor_core.claim_ready_drops(None, {}, '1', [campaign], {})
        self.assertTrue(drop_history.read_claims('1')[0]['recovered'])
        self.assertFalse(drop_history.pending_claim('1', 'c', 'd'))

    def test_retention_compacts_old_log_and_keeps_latest(self):
        paths.HISTORY_PATH.write_text('\n'.join(json.dumps(dict(id=str(i), claim='✅ reward', user_id='1'))
                                                for i in range(700)), encoding='utf-8')
        rows = drop_history.read_claims('1')
        self.assertEqual(len(rows), 500)
        self.assertEqual(rows[0]['id'], '699')
        self.assertEqual(len(paths.HISTORY_PATH.read_text().splitlines()), 500)
        self.assertEqual(drop_history.read_claims('2'), [])
        drop_history.record_claim('1', 'new', 'new', 'Rust', 'New reward')
        self.assertEqual(drop_history.read_claims('1')[0]['drop'], 'New reward')
        self.assertEqual(len(drop_history.read_claims('1')), 500)

    def test_history_delete_is_account_scoped_and_not_resurrected(self):
        watched = channel_history.ChannelHistory(channel_history.history_path('1'))
        watched.begin({'login': 'first'}, 100)
        watched.begin({'login': 'active'}, 200)
        other = channel_history.ChannelHistory(channel_history.history_path('2'))
        other.begin({'login': 'first'}, 100)
        streamers = self.root/'streamers.json'
        atomic_write_json(streamers, ['first','active'])
        channel_history.delete_history('1', ['FIRST', 'active'])
        watched.observe('active', 250)
        watched.begin({'login': 'active'}, 250)
        self.assertEqual(channel_history.read_history('1'), [])
        self.assertEqual(len(channel_history.read_history('2')), 1)
        self.assertEqual(json.loads(streamers.read_text()), ['first','active'])
        watched.end()
        watched.begin({'login': 'active'}, 250)
        watched.observe('active', 260)
        self.assertEqual(channel_history.read_history('1')[0]['earned'], 10)

    def test_only_twitch_box_art_urls_are_allowed(self):
        self.assertEqual(safe_art_url('https://static-cdn.jtvnw.net/ttv-boxart/1-{width}x{height}.jpg'),
                         'https://static-cdn.jtvnw.net/ttv-boxart/1-144x192.jpg')
        for url in ['https://example.com/1.jpg', 'http://static-cdn.jtvnw.net/ttv-boxart/1.jpg',
                    'https://static-cdn.jtvnw.net:bad/ttv-boxart/1.jpg', 'https://[broken',
                    'https://u@static-cdn.jtvnw.net/ttv-boxart/1.jpg']:
            self.assertEqual(safe_art_url(url), '')
