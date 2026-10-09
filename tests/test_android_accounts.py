import asyncio
import json
import aiohttp
from yarl import URL
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nyxor.android_accounts import AndroidAccounts


class AndroidAccountsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manager = AndroidAccounts(self.root)

    async def asyncTearDown(self):
        for loader, runtime in self.manager.slots.values():
            await runtime.dispatch({'action':'logout'})
            loader.close()
        self.temp.cleanup()

    async def add(self):
        return (await self.manager.dispatch({'action':'account_add'}))['active_account_id']

    async def test_upgrade_preserves_legacy_login_lists_history_and_boot_preferences(self):
        root = self.root/'legacy-upgrade'
        root.mkdir()
        (root/'nyxor_settings.json').write_text(json.dumps({'language':'en','launch_on_boot':True,'priority_games':['Rust'],'channel_points':{'enabled':True}}))
        jar = aiohttp.CookieJar()
        jar.update_cookies({'persistent':'123','auth-token':'fictional-test-token'},URL('https://www.twitch.tv'))
        jar.save(root/'cookies.jar')
        cookie = (root/'cookies.jar').read_bytes()
        (root/'data').mkdir()
        claim={'user_id':'123','id':'123:c:d','claim':'Legacy reward','confirmed':True}
        (root/'data/history.jsonl').write_text(json.dumps(claim)+'\n')
        manager=AndroidAccounts(root)
        try:
            snapshot=manager.snapshot()
            self.assertTrue(snapshot['authenticated'])
            self.assertEqual(snapshot['account_user_id'],'123')
            self.assertEqual(snapshot['queue'],['Rust'])
            self.assertEqual(snapshot['history'][0]['claim'],'Legacy reward')
            self.assertTrue(snapshot['settings']['launch_on_boot'])
            self.assertEqual(snapshot['settings']['language'],'en')
            await manager.dispatch({'action':'account_add'})
            self.assertEqual((root/'cookies.jar').read_bytes(),cookie)
            self.assertEqual(manager.snapshot('default')['queue'],['Rust'])
        finally:
            for loader,runtime in manager.slots.values():
                await runtime.dispatch({'action':'logout'})
                loader.close()

    async def test_imported_core_globals_paths_network_and_lists_are_isolated(self):
        from nyxor.network import configure_android
        adapter = type('Offline', (), {'status':lambda self:'offline'})()
        with patch('nyxor.network._android', adapter):
            second = await self.add()
        await self.manager.dispatch({'action':'queue','account_id':'default','items':['Rust']})
        await self.manager.dispatch({'action':'queue','account_id':second,'items':['Warframe']})
        loaders = [self.manager.slots[key][0] for key in ('default',second)]
        self.assertNotEqual(loaders[0].load('constants').COOKIES_PATH, loaders[1].load('constants').COOKIES_PATH)
        for loader in loaders:
            core = loader.load('nyxor_core')
            worker = loader.load('nyxor.worker.runtime')
            self.assertEqual(worker.STATE_PATH.parent, loader.load('nyxor.paths').RUNTIME_DIR)
            self.assertEqual(loader.load('nyxor_channels').SETTINGS_PATH,loader.load('nyxor.paths').SETTINGS_PATH)
        loaders[0].load('nyxor_core').settings_changed()
        self.assertEqual(loaders[0].load('nyxor_core').CONFIG_REVISION,1)
        self.assertEqual(loaders[1].load('nyxor_core').CONFIG_REVISION,0)
        self.assertEqual(self.manager.snapshot('default')['queue'],['Rust'])
        self.assertEqual(self.manager.snapshot(second)['queue'],['Warframe'])
        self.assertEqual(self.manager.snapshot(second)['network'],'offline')
        loaders[0].load('nyxor_core').logger.warning('Only first account event')
        first_events = loaders[0].load('nyxor.paths').EVENTS_PATH.read_text(encoding='utf-8')
        other_events = loaders[1].load('nyxor.paths').EVENTS_PATH
        self.assertIn('Only first account event',first_events)
        self.assertTrue(not other_events.exists() or 'Only first account event' not in other_events.read_text(encoding='utf-8'))
        await self.manager.dispatch({'action':'settings','values':{'energy_saver':True}})
        self.assertTrue(self.manager.snapshot('default')['settings']['energy_saver'])

    async def test_parallel_farms_survive_switch_and_bulk_delete_of_other_accounts(self):
        second = await self.add()
        third = await self.add()
        stopped = []
        async def miner(identity):
            try:
                await asyncio.sleep(100)
            finally:
                stopped.append(identity)
        for identity in ('default',second,third):
            runtime = self.manager.runtime(identity)
            self.manager.slots[identity][0].load('constants').COOKIES_PATH.touch()
            await runtime.dispatch({'action':'queue','items':['Rust']})
            runtime.mine = lambda identity=identity:miner(identity)
            await self.manager.dispatch({'action':'start','account_id':identity})
        await asyncio.sleep(0)
        await self.manager.dispatch({'action':'account_select','account_id':'default'})
        self.assertEqual(len([p for p in self.manager.snapshot()['accounts'] if p['running']]),3)
        result = await self.manager.dispatch({'action':'account_delete','ids':['default',third]})
        self.assertTrue(result['any_running'])
        self.assertEqual(result['active_account_id'],second)
        self.assertNotIn(second,stopped)
        self.assertCountEqual(stopped,['default',third])
        self.assertFalse((self.root/'cookies.jar').exists())
        self.assertFalse((self.root/'accounts'/third).exists())
        self.assertTrue((self.root/'accounts'/second/'cookies.jar').exists())
        self.assertTrue((self.root/'accounts-index.json').exists())

    async def test_invalid_selection_empty_profiles_and_fresh_profile_after_restart(self):
        for ids in ([],['default','default'],['default','../outside']):
            with self.assertRaises(ValueError):
                await self.manager.dispatch({'action':'account_delete','ids':ids})
        result = await self.manager.dispatch({'action':'account_delete','ids':['default']})
        self.assertEqual(result['accounts'],[])
        self.assertFalse(result['any_running'])
        restored = AndroidAccounts(self.root)
        self.assertEqual(restored.snapshot()['accounts'],[])
        result = await self.manager.dispatch({'action':'account_add'})
        self.assertEqual(result['queue'],[])
        self.assertFalse(result['authenticated'])

    async def test_stopping_one_profile_keeps_background_state_and_restore_is_opt_in(self):
        second = await self.add()
        for identity in ('default',second):
            runtime = self.manager.runtime(identity)
            self.manager.slots[identity][0].load('constants').COOKIES_PATH.touch()
            await runtime.dispatch({'action':'queue','items':['Rust']})
            runtime.mine = lambda:asyncio.sleep(100)
            await self.manager.dispatch({'action':'start','account_id':identity})
        await self.manager.dispatch({'action':'stop','account_id':'default'})
        self.assertTrue(self.manager.snapshot()['any_running'])
        await self.manager.dispatch({'action':'stop_all','preserve_wanted':True})
        result = await self.manager.dispatch({'action':'resume_accounts','reason':'restore'})
        self.assertEqual([p['id'] for p in result['accounts'] if p['running']],[second])
        await self.manager.dispatch({'action':'stop_all'})
        self.assertFalse((await self.manager.dispatch({'action':'resume_accounts','reason':'restore'}))['any_running'])
