import asyncio
import tempfile
import unittest
import subprocess
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch, Mock, AsyncMock

import constants
from nyxor import android_runtime as runtime, paths, storage


class AndroidColdStartTests(unittest.TestCase):
    def test_private_paths_are_set_before_importing_miner(self):
        code = '''
import tempfile,json,os,sys
from pathlib import Path
from nyxor import android_runtime as r
cwd = os.getcwd()
sys.path.insert(0, cwd)  # Android's APK importer also has a fixed source root.
with tempfile.TemporaryDirectory() as directory:
    try:
        r.initialize(directory)
        response = json.loads(r.request('{}'))
        assert response['ok'], response
        import constants
        from nyxor import paths
        assert paths.BASE_DIR == Path(directory)
        assert constants.COOKIES_PATH.parent == Path(directory)
        assert json.loads(r.request(json.dumps(dict(action='queue', items=['Rust']))))['ok']
        from nyxor.worker import runtime
        assert runtime.DATA_DIR.parent == Path(directory)
    finally:
        if r._loop is not None:
            r._loop.call_soon_threadsafe(r._loop.stop)
            r._thread.join(3)
            r._loop.close()
        os.chdir(cwd)
'''
        result = subprocess.run([sys.executable, '-c', code], cwd=Path(__file__).resolve().parent.parent / "core",
                                capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr)


class AndroidRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stack = ExitStack()
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(patch.object(storage, "SETTINGS_PATH", self.root / "settings.json"))
        self.stack.enter_context(patch.object(constants, "COOKIES_PATH", self.root / "cookies.jar"))
        for name in ("STATE_PATH", "HISTORY_PATH", "EVENTS_PATH", "STATS_PATH"):
            self.stack.enter_context(patch.object(paths, name, self.root / name))
        runtime._miner = None
        runtime._auth_task = None

    async def asyncTearDown(self):
        await runtime.stop()
        self.stack.close()

    async def test_start_requires_authentication_and_queue(self):
        with self.assertRaises(ValueError):
            await runtime.dispatch({"action": "start"})
        constants.COOKIES_PATH.touch()
        with self.assertRaises(ValueError):
            await runtime.dispatch({"action": "start"})

    async def test_start_is_idempotent_and_stop_cancels_embedded_task(self):
        constants.COOKIES_PATH.touch()
        storage.save_queue(["Rust"])
        entered = asyncio.Event()
        stopped = asyncio.Event()
        async def miner():
            entered.set()
            try:
                await asyncio.sleep(100)
            finally:
                stopped.set()
        with patch.object(runtime, "mine", miner):
            await runtime.dispatch({"action": "start"})
            await entered.wait()
            first = runtime._miner
            await runtime.dispatch({"action": "start"})
            self.assertIs(first, runtime._miner)
            self.assertTrue(runtime.snapshot()["running"])
            await runtime.dispatch({"action": "stop"})
        self.assertTrue(stopped.is_set())
        self.assertFalse(runtime.snapshot()["running"])

    async def test_lists_persist_and_invalid_streamers_are_rejected(self):
        await runtime.dispatch({"action": "queue", "items": ["Rust", "Rust", "Warframe"]})
        self.assertEqual(storage.load_queue(), ["Rust", "Warframe"])
        with self.assertRaises(ValueError):
            await runtime.dispatch({"action": "streamers", "items": ["bad/streamer"]})
        await runtime.dispatch({"action": "streamers", "items": ["valid_streamer"]})
        self.assertEqual(storage.load_streamers(), ["valid_streamer"])

    async def test_settings_preserve_unrelated_data_and_reject_unknown_keys(self):
        storage.save_settings({"preferred_channels": {"Rust": "one"}, "channel_points": {"predictions": {"enabled": False}}})
        await runtime.dispatch({"action": "settings", "values": {"auto_claim_bonus": False}})
        result = storage.load_settings()
        self.assertEqual(result["preferred_channels"], {"Rust": "one"})
        self.assertFalse(result["channel_points"]["predictions"]["enabled"])
        with self.assertRaises(ValueError):
            await runtime.dispatch({"action": "settings", "values": {"auth_token": "no"}})

    async def test_boot_switch_defaults_off_and_persists_both_directions(self):
        self.assertFalse(runtime.snapshot()['settings']['launch_on_boot'])
        for enabled in (True, False):
            await runtime.dispatch({'action': 'settings', 'values': {'launch_on_boot': enabled}})
            self.assertEqual(storage.load_settings()['launch_on_boot'], enabled)
            self.assertEqual(runtime.snapshot()['settings']['launch_on_boot'], enabled)
        with self.assertRaises(ValueError):
            await runtime.dispatch({'action': 'settings', 'values': {'launch_on_boot': 'true'}})

    async def test_points_game_list_alone_is_enough_to_start(self):
        await runtime.dispatch({'action':'points_games','items':['Rust','Rust']})
        await runtime.dispatch({'action':'settings','values':{'points_order':'quiet'}})
        self.assertEqual(runtime.snapshot()['points_games'],['Rust'])
        self.assertEqual(runtime.snapshot()['settings']['points_order'],'quiet')
        constants.COOKIES_PATH.touch()
        with patch.object(runtime,'mine',side_effect=lambda:asyncio.sleep(100)):
            await runtime.dispatch({'action':'start'})
            self.assertTrue(runtime.snapshot()['running'])
            await runtime.stop()

    async def test_snapshot_never_returns_auth_cookie(self):
        constants.COOKIES_PATH.write_text("private-token")
        storage.save_settings({"auth_token": "private-token"})
        self.assertNotIn("private-token", str(runtime.snapshot()))

    async def test_logout_cancels_pending_auth_and_removes_cookie(self):
        constants.COOKIES_PATH.touch()
        runtime._auth_task = asyncio.create_task(asyncio.sleep(100))
        await runtime.dispatch({"action": "logout"})
        self.assertTrue(runtime._auth_task.cancelled())
        self.assertFalse(constants.COOKIES_PATH.exists())

    async def test_offline_login_returns_immediately_without_requesting_a_code(self):
        from nyxor import network
        with patch.object(network, 'connection_blocker', return_value='offline'), patch.object(network, 'client_session') as factory:
            await runtime.authenticate()
        factory.assert_not_called()
        self.assertEqual(runtime._auth['error_code'], 'offline')
        self.assertFalse(constants.COOKIES_PATH.exists())

    async def test_device_code_can_complete_after_pending_response(self):
        from nyxor import network
        def response(status, data):
            value = Mock(status=status)
            value.json = AsyncMock(return_value=data)
            context = AsyncMock()
            context.__aenter__.return_value = value
            return context
        verification = 'https://www.twitch.tv/activate?device-code=ABCD1234'
        session = Mock()
        session.post.side_effect = [
            response(200, dict(verification_uri=verification, user_code='ABCD1234', device_code='private-device', expires_in=300, interval=5)),
            response(400, dict(message='authorization_pending')),
            response(200, dict(access_token='test-token')),
        ]
        session.get.return_value = response(200, dict(client_id=constants.ClientType.ANDROID_APP.CLIENT_ID, user_id='123', login='test-user'))
        context = AsyncMock()
        context.__aenter__.return_value = session
        pending_states = []
        async def poll(delay):
            pending_states.append(dict(runtime._auth))
        with patch.object(network, 'connection_blocker', return_value=''), patch.object(network, 'client_session', return_value=context), patch.object(runtime.asyncio, 'sleep', side_effect=poll):
            await runtime.authenticate()
        self.assertEqual(runtime._auth, {'status': 'connected'})
        self.assertEqual(runtime._account, 'test-user')
        self.assertEqual(len(pending_states), 2)
        self.assertTrue(all(state['url'] == verification and state['code'] == 'ABCD1234' for state in pending_states))
        self.assertTrue(constants.COOKIES_PATH.exists())

    async def test_unknown_command_is_rejected(self):
        with self.assertRaises(ValueError):
            await runtime.dispatch({"action": "execute", "code": "bad"})
