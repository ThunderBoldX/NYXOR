import copy
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, patch

from nyxor import drop_progress as progress


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.channel = dict(channel_id='10', stream_id='100', login='worldoftanks', game='World of Tanks', available_campaign_ids=['c'])
        now = datetime.now(timezone.utc)
        self.state = dict(game='World of Tanks', mineable=[dict(campaign_id='c',drop_id='a',current=1,required=120,starts_at=now-timedelta(hours=1),ends_at=now+timedelta(hours=1),allowed_channels=None),dict(campaign_id='c',drop_id='b',current=1,required=240,starts_at=now-timedelta(hours=1),ends_at=now+timedelta(hours=1),allowed_channels=None)])

    def test_current_session_updates_only_exact_eligible_drop_without_regression(self):
        progress.apply_current_session(self.state,self.channel,dict(dropID='a',currentMinutesWatched=5))
        self.assertEqual([d['current'] for d in self.state['mineable']],[5,1])
        progress.apply_current_session(self.state,self.channel,dict(dropID='a',currentMinutesWatched=2))
        self.assertEqual(self.state['mineable'][0]['current'],5)
        progress.apply_current_session(self.state,self.channel,dict(dropID='unknown',currentMinutesWatched=500))
        self.assertEqual([d['current'] for d in self.state['mineable']],[5,1])
        progress.apply_current_session(self.state,{**self.channel,'available_campaign_ids':[]},dict(dropID='a',currentMinutesWatched=10))
        self.assertEqual(self.state['mineable'][0]['current'],5)

    def test_stall_recovery_is_bounded_and_progress_is_not_invented_from_packets(self):
        watch=progress.ProgressWatch(); drops=[dict(drop_id='a',current=1)]
        self.assertEqual(watch.observe(self.channel,drops,now=0)['status'],'waiting')
        self.assertFalse(watch.observe(self.channel,drops,now=179)['recover'])
        self.assertTrue(watch.observe(self.channel,drops,now=180)['recover'])
        self.assertFalse(watch.observe(self.channel,drops,now=200)['recover'])
        self.assertTrue(watch.observe(self.channel,drops,now=360)['recover'])
        self.assertEqual(drops,[dict(drop_id='a',current=1)])
        self.assertEqual(watch.observe(self.channel,[dict(drop_id='a',current=2)],now=370)['status'],'progressing')
        self.assertFalse(watch.observe(self.channel,[dict(drop_id='a',current=2)],now=500)['recover'])

    def test_new_channel_broadcast_or_reward_resets_stall_timer(self):
        for channel,drops in [({**self.channel,'stream_id':'101'},[dict(drop_id='a',current=1)]),({**self.channel,'channel_id':'11'},[dict(drop_id='a',current=1)]),(self.channel,[dict(drop_id='b',current=0)])]:
            watch=progress.ProgressWatch();watch.observe(self.channel,[dict(drop_id='a',current=1)],now=0)
            self.assertEqual(watch.observe(channel,drops,now=1000)['status'],'waiting')
            self.assertFalse(watch.observe(channel,drops,now=1100)['recover'])

    def test_failed_snapshot_and_empty_rewards_do_not_trigger_stall_recovery(self):
        watch=progress.ProgressWatch();drops=[dict(drop_id='a',current=1)]
        watch.observe(self.channel,drops,now=0)
        self.assertEqual(watch.observe(self.channel,drops,now=500,fresh=False),dict(status='unknown',recover=False,stalled_seconds=0))
        self.assertFalse(watch.observe(self.channel,[],now=500)['recover'])
        watch.reset()
        self.assertEqual(watch.observe(self.channel,drops,now=500)['status'],'waiting')


class CurrentSessionTests(unittest.IsolatedAsyncioTestCase):
    async def result(self, current):
        mock=AsyncMock(return_value={'data':{'currentUser':{'dropCurrentSession':current}}})
        with patch.object(progress,'gql_request',mock):
            return await progress.current_session(object(),{'Authorization':'OAuth fixture'},'10')

    async def test_matching_channel_is_required_and_absent_session_is_valid(self):
        self.assertIsNone(await self.result(None))
        self.assertIsNone(await self.result(dict(channel={'id':'11'},dropID='a',currentMinutesWatched=5)))
        d=dict(channel={'id':'10'},dropID='a',currentMinutesWatched=5)
        self.assertEqual(await self.result(d),d)

    async def test_malformed_and_non_integer_minutes_are_never_accepted(self):
        for value in (True,-1,1.5,'5',None):
            with self.assertRaises(ValueError):
                await self.result(dict(channel={'id':'10'},dropID='a',currentMinutesWatched=value))
