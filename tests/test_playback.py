import asyncio
import time
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp
from aiohttp import web
import nyxor_player as player


class PlaylistTests(unittest.TestCase):
    def test_live_window_relative_urls_deduplication_and_bounded_size(self):
        text = '#EXTM3U\n' + ''.join(f'#EXTINF:2,\n{i}.ts\n' for i in range(40))
        rows = player.parse_media_segments(text, 'https://cdn.example/live/index.m3u8')
        self.assertEqual(len(rows), 30)
        self.assertEqual(rows[0], 'https://cdn.example/live/10.ts')
        self.assertEqual(rows[-1], 'https://cdn.example/live/39.ts')
        self.assertEqual(player.parse_media_segments('#EXTM3U\n#EXTINF:2,\na.ts\n#EXTINF:2,\na.ts', 'https://cdn.example/'), ['https://cdn.example/a.ts'])

    def test_json_empty_ended_and_master_playlists_are_not_active_video(self):
        for text in ('{"error":"offline"}', '#EXTM3U', '#EXTM3U\n#EXTINF:2,\na.ts\n#EXT-X-ENDLIST', '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=10\nvideo.m3u8'):
            with self.assertRaises(RuntimeError):
                player.parse_media_segments(text, 'https://cdn.example/')


class PlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.requests = []
        self.media_error = False
        self.head_unsupported = False
        self.segment_error = False
        self.master_count = 0
        self.media_count = 0
        async def master(request):
            self.master_count += 1
            self.assertNotIn('fast_bread', request.query)
            return web.Response(text='#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100,NAME="160p"\n/media.m3u8')
        async def media(request):
            self.media_count += 1
            if self.media_error:
                return web.Response(status=403)
            return web.Response(text='#EXTM3U\n' + ''.join(f'#EXTINF:2,\n/segment/{i}.ts\n' for i in range(12)))
        async def segment(request):
            self.requests.append((request.method, request.path, dict(request.headers)))
            if self.segment_error and request.match_info['id'] == '3':
                return web.Response(status=404)
            if self.head_unsupported and request.method == 'HEAD':
                return web.Response(status=405)
            return web.Response(body=b'x' * 2048)
        app = web.Application()
        app.router.add_get('/master/{login}.m3u8', master)
        app.router.add_get('/media.m3u8', media)
        app.router.add_get('/segment/{id}.ts', segment)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        self.url = 'http://127.0.0.1:' + str(site._server.sockets[0].getsockname()[1])
        self.session = aiohttp.ClientSession()
        self.token = AsyncMock(return_value=('fixture-sig', 'fixture-token'))
        self.patches = [patch.object(player, 'USHER_URL', self.url+'/master/{login}.m3u8'), patch.object(player, 'fetch_playback_token', self.token)]
        for item in self.patches:
            item.start()

    async def asyncTearDown(self):
        for item in self.patches:
            item.stop()
        await self.session.close()
        await self.runner.cleanup()

    async def touch(self, lease=None):
        return await player.touch_hls_stream(self.session, {'Authorization':'OAuth fixture'}, 'WorldofTanks', user_agent='NYXOR-test', lease=lease)

    async def test_whole_window_is_touched_without_downloading_video_or_leaking_auth(self):
        status = await self.touch()
        self.assertTrue(status.active)
        self.assertEqual((status.segments_checked, status.segments_total), (12, 12))
        self.assertEqual({p for _, p, _ in self.requests}, {f'/segment/{i}.ts' for i in range(12)})
        self.assertTrue(all(method == 'HEAD' for method, _, _ in self.requests))
        self.assertTrue(all('Authorization' not in h and 'Client-Integrity' not in h for _, _, h in self.requests))

    async def test_cached_variant_reduces_gql_but_still_refreshes_live_media(self):
        lease = player.PlaybackLease()
        self.assertTrue((await self.touch(lease)).active)
        self.assertTrue((await self.touch(lease)).active)
        self.assertEqual(self.token.await_count, 1)
        self.assertEqual(self.master_count, 1)
        self.assertEqual(self.media_count, 2)
        self.assertEqual(len(self.requests), 24)
        lease.updated_monotonic = time.monotonic() - 301
        await self.touch(lease)
        self.assertEqual(self.token.await_count, 2)

    async def test_media_failure_invalidates_cached_signed_url_and_recovers(self):
        lease = player.PlaybackLease()
        await self.touch(lease)
        self.media_error = True
        self.assertFalse((await self.touch(lease)).active)
        self.assertFalse(lease.url)
        self.media_error = False
        self.assertTrue((await self.touch(lease)).active)
        self.assertEqual(self.token.await_count, 2)

    async def test_missing_segment_never_reports_complete_active_playback(self):
        self.segment_error = True
        lease = player.PlaybackLease()
        status = await self.touch(lease)
        self.assertFalse(status.active)
        self.assertEqual(status.http_status, 404)
        self.assertEqual((status.segments_checked, status.segments_total), (11, 12))
        self.assertFalse(lease.url)

    async def test_head_unsupported_uses_only_tiny_range_gets(self):
        self.head_unsupported = True
        self.assertTrue((await self.touch()).active)
        gets = [headers for method, _, headers in self.requests if method == 'GET']
        self.assertEqual(len(gets), 12)
        self.assertTrue(all(h['Range'] == 'bytes=0-1023' for h in gets))

    async def test_eco_keeps_watch_cadence_and_new_broadcast_discards_old_lease(self):
        p = player.TwitchHLSPlayer(self.session, {}, user_agent='test', pulse_interval=60)
        p.set_power_saver(True)
        self.assertEqual(p._pulse_interval, 20)
        await p.set_channel('worldoftanks', 'old-broadcast')
        old = p._lease
        old.url = 'https://cdn.example/old.m3u8'
        await p.set_channel('worldoftanks', 'new-broadcast')
        self.assertIsNot(p._lease, old)
        self.assertFalse(p._lease.url)

    async def test_pulse_sleep_accounts_for_time_spent_on_requests(self):
        p = player.TwitchHLSPlayer(self.session, {}, user_agent='test')
        await p.set_channel('worldoftanks')
        clock = [100.0]
        async def touch(*args, **kwargs):
            clock[0] += 12
            return player.PlaybackStatus(login='worldoftanks', active=True, updated_monotonic=clock[0])
        waits = []
        async def wait(awaitable, timeout):
            awaitable.close()
            waits.append(timeout)
            raise asyncio.CancelledError
        with patch.object(player.time, 'monotonic', side_effect=lambda:clock[0]), patch.object(player, 'touch_hls_stream', side_effect=touch), patch.object(player.asyncio, 'wait_for', side_effect=wait):
            with self.assertRaises(asyncio.CancelledError):
                await p._run()
        self.assertEqual(waits, [8.0])

    async def test_channel_change_while_request_is_pending_cannot_publish_stale_success(self):
        p = player.TwitchHLSPlayer(self.session, {}, user_agent='test')
        await p.set_channel('worldoftanks','old')
        started, finish = asyncio.Event(), asyncio.Event()
        next_started = asyncio.Event()
        calls = 0
        async def touch(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls > 1:
                next_started.set()
                await asyncio.Event().wait()
            started.set()
            await finish.wait()
            return player.PlaybackStatus(login='worldoftanks',active=True,updated_monotonic=time.monotonic())
        with patch.object(player,'touch_hls_stream',side_effect=touch):
            await p.start(); await started.wait()
            await p.set_channel('worldoftanks','new')
            finish.set(); await asyncio.wait_for(next_started.wait(), 1)
            self.assertFalse(p.status.active)
            await p.stop()
