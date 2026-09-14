import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, MagicMock, patch
from contextlib import ExitStack
import copy
import aiohttp

from nyxor.channel_history import ChannelHistory
from nyxor import points_selection as selection
from nyxor_points import visible_rewards, ChannelPointsSnapshot
import nyxor_core as core


class HistoryTests(unittest.TestCase):
    def test_baseline_repeat_spend_and_restart_do_not_count_existing_points(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.json'
            h = ChannelHistory(path)
            channel = dict(login='one', game='Rust', display_name='One')
            h.begin(channel, 1000)
            h.observe('one', 1020)
            h.observe('one', 1020)
            h.observe('one', 900)
            h.observe('one', 910)
            self.assertEqual(h.rows['one']['earned'], 30)
            h.end()
            h.observe('one', 9999)
            second = ChannelHistory(path)
            second.begin(channel, 9999)
            second.observe('one', 10009)
            self.assertEqual(second.rows['one']['earned'], 40)
            self.assertEqual(second.rows['one']['visits'], 2)

    def test_other_channel_balance_is_not_attributed_to_current_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            h = ChannelHistory(Path(directory)/'history.json')
            h.begin(dict(login='one'))
            h.observe('two', 1000)
            h.observe('one', 100)
            h.observe('one', 110)
            h.begin(dict(login='two'))
            h.observe('one', 1000)
            self.assertEqual(h.rows['one']['earned'], 10)
            self.assertEqual(h.rows['two']['earned'], 0)

    def test_catalog_keeps_prices_availability_and_deduplicates(self):
        reward = dict(id='a', title='VIP', cost=1000, isEnabled=True)
        data = dict(data=dict(customRewards=[reward, reward, dict(id='b', title='Emote', cost=100, isPaused=True)]))
        rows = visible_rewards(data)
        self.assertEqual([r['cost'] for r in rows], [100, 1000])
        self.assertFalse(rows[0]['available'])
        self.assertTrue(rows[1]['available'])


class SelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        selection._directories.clear()
        selection._contexts.clear()
        selection._scan_positions.clear()

    async def test_raid_outside_configured_channels_or_games_is_rejected(self):
        outside = dict(login='stranger', game='Other', channel_id='9')
        configured = dict(login='one', game='Other', channel_id='1')
        with patch.object(core, 'fetch_streamer_channel', AsyncMock(side_effect=[outside, configured])), patch.object(selection, 'points_capable', AsyncMock(side_effect=lambda s,h,c:c)) as capable:
            result = await selection.pick_points_target(None, {}, ['one'], ['Rust'], raid_login='stranger')
        self.assertEqual(result['login'], 'one')
        self.assertEqual(capable.await_count, 1)

    async def test_category_selection_rechecks_game_and_skips_channels_without_points(self):
        candidates = [dict(login='moved',viewers=1),dict(login='no_points',viewers=2),dict(login='good',viewers=3)]
        live = [dict(login='moved',game='Other'),dict(login='no_points',game='Rust'),dict(login='good',game='Rust')]
        with patch.object(selection, 'category_channels', AsyncMock(return_value=dict(items=candidates,complete=True))), patch.object(core, 'fetch_streamer_channel', AsyncMock(side_effect=live)), patch.object(selection, 'points_capable', AsyncMock(side_effect=[None,live[-1]])):
            result = await selection.pick_points_target(None, {}, [], ['Rust'], 'quiet')
        self.assertEqual(result['login'],'good')

    async def test_transient_point_context_failure_is_not_cached(self):
        channel=dict(login='one')
        context=ChannelPointsSnapshot(balance=10,claim_id=None,reward_title=None,reward_cost=None)
        with patch.object(selection,'fetch_channel_points_context',AsyncMock(side_effect=[RuntimeError('offline'),context])):
            self.assertIsNone(await selection.points_capable(None,{},channel))
            self.assertEqual((await selection.points_capable(None,{},channel))['_points_balance'],10)

    async def test_low_viewer_sort_includes_later_pages_and_removes_duplicates(self):
        def response(payload):
            value=Mock(); value.json=AsyncMock(return_value=payload)
            context=AsyncMock();context.__aenter__.return_value=value
            return context
        def stream(login,viewers,game='1'):
            return dict(id=login,user_id=login,user_login=login,user_name=login,game_id=game,type='live',viewer_count=viewers)
        session=Mock()
        session.get.side_effect=[response(dict(data=[dict(id='1',name='Rust')])),
            response(dict(data=[stream('big',500),stream('wrong',0,'2')],pagination=dict(cursor='next'))),
            response(dict(data=[stream('small',1),stream('big',499)],pagination={}))]
        result=await selection.category_channels(session,{'Authorization':'OAuth test','Client-Id':'client'},'Rust','quiet')
        self.assertEqual([c['login'] for c in result['items']],['small','big'])
        self.assertTrue(result['complete'])
        self.assertEqual(session.get.call_args_list[-1].kwargs['params']['after'],'next')
        self.assertEqual(session.get.call_args_list[-1].kwargs['headers']['Authorization'],'Bearer test')

    async def test_wait_is_interrupted_when_settings_change(self):
        state={}
        live=Mock()
        async def change(_):
            core.settings_changed()
        with patch.object(core,'render_status',return_value='state'),patch.object(core.asyncio,'sleep',side_effect=change):
            await core.wait_live(90,live,state)
        self.assertEqual(state['remaining'],0)

    async def test_raid_is_blocked_before_joining_twitch(self):
        from nyxor_rewards import TwitchRewardsEngine
        from nyxor_points import ChannelPointsTracker
        engine=TwitchRewardsEngine(None,{},auth_token='test',user_id='1',tracker=ChannelPointsTracker())
        engine._mode='points'
        with patch('nyxor.storage.load_settings',return_value={'streamer_channels':['one']}),patch.object(core,'fetch_streamer_channel',AsyncMock(return_value=dict(login='outsider',game='Other'))),patch('nyxor_rewards._post_gql',AsyncMock()) as post:
            await engine._handle_raid('raid_update_v2',dict(raid=dict(id='r',target_login='outsider')))
        post.assert_not_awaited()
        self.assertEqual(engine.consume_raid_target(),'')

    async def test_running_miner_picks_up_new_streamers_even_when_drops_api_fails(self):
        from nyxor_points import ChannelPointsResult
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            cookie_path = Path(directory)/'cookies.jar'
            jar = aiohttp.CookieJar()
            jar.update_cookies({'auth-token':'test','persistent':'1'},core.ClientType.ANDROID_APP.CLIENT_URL)
            jar.save(cookie_path)
            settings={'priority_games':['Rust'],'streamer_channels':['one'],'channel_points':{'follow_raids':False}}
            stack.enter_context(patch.object(core,'COOKIES_PATH',cookie_path))
            stack.enter_context(patch.object(core,'load_settings',side_effect=lambda:copy.deepcopy(settings)))
            stack.enter_context(patch.object(core,'history_path',return_value=Path(directory)/'history.json'))
            context=AsyncMock();context.__aenter__.return_value=Mock()
            stack.enter_context(patch.object(core,'client_session',return_value=context))
            stack.enter_context(patch.object(core,'validate_account',AsyncMock(return_value=dict(user_id='1',login='tester'))))
            stack.enter_context(patch.object(core,'fetch_campaign_snapshot',AsyncMock(side_effect=RuntimeError('Drops unavailable'))))
            player=Mock(start=AsyncMock(),stop=AsyncMock(),clear=AsyncMock())
            playback=Mock(active=True,http_status=200);playback.display_text.return_value='active'
            player.ensure_active=AsyncMock(return_value=playback)
            stack.enter_context(patch.object(core,'TwitchHLSPlayer',return_value=player))
            rewards=Mock(follow_raids=False,start=AsyncMock(),stop=AsyncMock(),set_channel=AsyncMock(),reconfigure=AsyncMock())
            rewards.snapshot.return_value={}
            stack.enter_context(patch.object(core,'TwitchRewardsEngine',return_value=rewards))
            async def live_channel(session,headers,login):
                return dict(login=login,channel_id=login,stream_id=login,game='Other')
            stack.enter_context(patch.object(core,'fetch_streamer_channel',side_effect=live_channel))
            stack.enter_context(patch.object(selection,'points_capable',AsyncMock(side_effect=lambda s,h,c:c)))
            stack.enter_context(patch.object(core,'get_spade_url',AsyncMock(return_value='https://example.test')))
            stack.enter_context(patch.object(core,'send_watch',AsyncMock(return_value=(True,204))))
            stack.enter_context(patch.object(core,'fetch_channel_points_context',AsyncMock(return_value=ChannelPointsSnapshot(100,None,None,None))))
            stack.enter_context(patch.object(core,'update_channel_points',AsyncMock(return_value=ChannelPointsResult(110,10,'ok'))))
            stack.enter_context(patch.object(core,'Live',MagicMock()))
            stack.enter_context(patch.object(core,'render_status',return_value='status'))
            stack.enter_context(patch.object(core,'run_termux_command'))
            calls=[]
            async def next_cycle(seconds,live,state):
                calls.append(state['channel_login'])
                if len(calls)==2:
                    raise asyncio.CancelledError()
                settings['streamer_channels']=['two']
                core.settings_changed()
            stack.enter_context(patch.object(core,'wait_live',side_effect=next_cycle))
            with self.assertRaises(asyncio.CancelledError):
                await core.main()
            self.assertEqual(calls,['one','two'])
            self.assertEqual(player.ensure_active.await_count,2)
            player.stop.assert_awaited_once()
