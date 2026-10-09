"""Account-local module namespaces share Android's event loop, never private paths."""
from __future__ import annotations

import asyncio
import builtins
import importlib.abc
import importlib.util
import json
import logging
import re
import shutil
import sys
import types
import uuid
from pathlib import Path

from nyxor.storage import atomic_write_json

LOCAL = {'nyxor', 'constants', 'version', 'nyxor_core', 'nyxor_miner', 'nyxor_channels',
         'nyxor_campaigns', 'nyxor_points', 'nyxor_rewards', 'nyxor_player'}
ID = re.compile(r'(?:default|[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\Z')
GLOBAL = {'language', 'launch_on_boot', 'energy_saver'}


class ProfileLoader(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """Use the APK loader's code objects, including Chaquopy's compiled modules."""
    def __init__(self):
        self.prefix = '_nyxor_profile_' + uuid.uuid4().hex
        package = types.ModuleType(self.prefix)
        package.__path__ = []
        sys.modules[self.prefix] = package
        sys.meta_path.insert(0, self)

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self.prefix + '.'):
            return None
        original = fullname[len(self.prefix) + 1:]
        if original.split('.')[0] not in LOCAL:
            return None
        source = importlib.util.find_spec(original)
        if source is None or not hasattr(source.loader, 'get_code'):
            raise ImportError('Account module unavailable: ' + original)
        spec = importlib.util.spec_from_loader(fullname, self, is_package=source.submodule_search_locations is not None)
        spec.loader_state = (original, source)
        return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        original, source = module.__spec__.loader_state
        module.__file__ = source.origin
        if source.submodule_search_locations is not None:
            module.__path__ = list(source.submodule_search_locations)
        def profile_import(name, globals=None, locals=None, fromlist=(), level=0):
            if not level and name.split('.')[0] in LOCAL:
                qualified = self.prefix + '.' + name
                result = builtins.__import__(qualified, globals, locals, fromlist, 0)
                return result if fromlist else sys.modules[self.prefix + '.' + name.split('.')[0]]
            return builtins.__import__(name, globals, locals, fromlist, level)
        module.__builtins__ = {**vars(builtins), '__import__': profile_import}
        exec(source.loader.get_code(original), module.__dict__)

    def load(self, name):
        return importlib.import_module(self.prefix + '.' + name)

    def close(self):
        if self in sys.meta_path:
            sys.meta_path.remove(self)
        for name in list(sys.modules):
            if name == self.prefix or name.startswith(self.prefix + '.'):
                del sys.modules[name]
        prefix = 'NYXOR.' + self.prefix
        for name, logger in list(logging.root.manager.loggerDict.items()):
            if name == prefix or name.startswith(prefix + '.'):
                if isinstance(logger, logging.Logger):
                    for handler in list(logger.handlers):
                        logger.removeHandler(handler)
                        handler.close()
                del logging.root.manager.loggerDict[name]


class AndroidAccounts:
    def __init__(self, directory):
        self.root = Path(directory).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.file = self.root/'accounts-index.json'
        self.index = json.loads(self.file.read_text(encoding='utf-8')) if self.file.exists() else {
            'version': 1, 'active': 'default', 'preferences': None,
            'profiles': [{'id': 'default', 'auto_farm': True, 'wanted': False}]}
        records = self.index.get('profiles')
        if (self.index.get('version') != 1 or not isinstance(records, list) or len(records) > 20
                or any(not isinstance(p, dict) or not isinstance(p.get('id'), str) or not ID.fullmatch(p['id']) for p in records)
                or len({p['id'] for p in records}) != len(records)
                or (self.index.get('active') not in {p['id'] for p in records} if records else self.index.get('active') is not None)):
            raise ValueError('Invalid account index')
        self.slots = {}
        self.lock = asyncio.Lock()
        if self.index['preferences'] is None:
            settings = self.runtime('default').snapshot()['settings']
            self.index['preferences'] = {k: settings.get(k) for k in GLOBAL}
            self.save()

    def save(self):
        atomic_write_json(self.file, self.index)

    def record(self, identity):
        record = next((p for p in self.index['profiles'] if p['id'] == identity), None)
        if record is None:
            raise ValueError('Unknown account')
        return record

    def folder(self, identity):
        self.record(identity)
        return self.root if identity == 'default' else self.root/'accounts'/identity

    def runtime(self, identity):
        record = self.record(identity)
        if identity not in self.slots:
            folder = self.folder(identity)
            folder.mkdir(parents=True, exist_ok=True)
            loader = ProfileLoader()
            try:
                paths = loader.load('nyxor.paths')
                paths.BASE_DIR = folder
                paths.LOCALES_DIR = self.root/'locales'
                paths.SETTINGS_PATH = folder/'nyxor_settings.json'
                for name, child in [('RUNTIME_DIR','runtime'), ('DATA_DIR','data'), ('LOG_DIR','logs')]:
                    setattr(paths, name, folder/child)
                for name, parent, child in [('STATE_PATH','runtime','state.json'), ('LOG_PATH','logs','nyxor.log'),
                        ('HISTORY_PATH','data','history.jsonl'), ('EVENTS_PATH','data','events.jsonl'), ('STATS_PATH','data','stats.json')]:
                    setattr(paths, name, folder/parent/child)
                paths.ensure_directories()
                loader.load('constants').COOKIES_PATH = folder/'cookies.jar'
                from nyxor.network import _android
                loader.load('nyxor.network').configure_android(_android)
                runtime = loader.load('nyxor.android_runtime')
                runtime._account = record.get('account', '')
                self.slots[identity] = (loader, runtime)
            except BaseException:
                loader.close()
                raise
        return self.slots[identity][1]

    def snapshot(self, selected=None):
        active = self.index['active'] if selected is None else selected
        data = self.runtime(active).snapshot() if active else {
            'running':False,'authenticated':False,'account':'','account_user_id':'','auth':{'status':'idle'},
            'state':{},'stats':{},'queue':[],'streamers':[],'points_games':[],'history':[],'watched':[],'events':[],
            'settings':{'channel_points':{},'auto_restart':True},'error':'','network':'unknown','platform':'android'}
        rows = []
        for record in self.index['profiles']:
            state = self.runtime(record['id']).snapshot()
            account = state['account'] or state['state'].get('account') or record.get('account','')
            if account != record.get('account',''):
                record['account'] = account
                self.save()
            rows.append({'id':record['id'],'account':account,'authenticated':state['authenticated'],
                'running':state['running'],'auto_farm':record.get('auto_farm',False),
                'auth_status':state['auth'].get('status'),'auth_error':state['auth'].get('error_code',''),
                **{k:state['state'].get(k,'') for k in ('game','channel','mode','points')},
                'drops':state['state'].get('active_drops',[]),'error':state['error']})
        data.update(accounts=rows, active_account_id=active, any_running=any(p['running'] for p in rows))
        data['settings'].update(self.index['preferences'])
        running = [row for row in rows if row['running']]
        if running:
            from nyxor.android_status import notification_status
            statuses = []
            for row in running:
                status = notification_status(self.runtime(row['id']).snapshot())
                statuses.append('@'+(row['account'] or row['id'][:8])+' · '+status['details'])
            data['notification'] = {'title':'NYXOR · '+str(len(running))+(' акаунт(и)' if data['settings']['language']=='uk' else ' account(s)'),
                'text':statuses[0].split('\n')[0], 'details':'\n\n'.join(statuses), 'progress':None}
        return data

    async def dispatch(self, data):
        # Account mutations and view switches cannot race deletion or auth completion.
        async with self.lock:
            action = data.get('action','snapshot')
            if action == 'snapshot':
                return self.snapshot()
            if action == 'account_snapshot':
                return self.snapshot(data.get('account_id') or self.index['active'])
            if action == 'account_add':
                if len(self.index['profiles']) >= 20:
                    raise ValueError('Up to 20 accounts are supported')
                identity = str(uuid.uuid4())
                self.index['profiles'].append({'id':identity,'auto_farm':False,'wanted':False})
                await self.runtime(identity).dispatch({'action':'settings','values':self.index['preferences']})
                self.index['active'] = identity
                self.save()
                return self.snapshot()
            if action == 'account_delete':
                ids = data.get('ids')
                if not isinstance(ids,list) or not 1 <= len(ids) <= 20 or any(not isinstance(i,str) for i in ids) or len(set(ids)) != len(ids):
                    raise ValueError('Invalid account selection')
                for identity in ids:
                    self.record(identity)
                for identity in ids:
                    runtime = self.runtime(identity)
                    await runtime.dispatch({'action':'logout'})
                    folder = self.folder(identity)
                    if identity == 'default':
                        targets = [folder/name for name in ('cookies.jar','browser-session.json','nyxor_settings.json','runtime','data','logs')]
                    else:
                        if folder.parent != self.root/'accounts' or folder.name != identity:
                            raise ValueError('Invalid profile folder')
                        targets = [folder]
                    for target in targets:
                        if target.is_dir() and not target.is_symlink():
                            shutil.rmtree(target)
                        else:
                            target.unlink(missing_ok=True)
                    self.slots.pop(identity)[0].close()
                    self.index['profiles'] = [p for p in self.index['profiles'] if p['id'] != identity]
                    if self.index['active'] == identity:
                        self.index['active'] = next((p['id'] for p in self.index['profiles']),None)
                    self.save()
                return self.snapshot()
            if action in {'stop_all','resume_accounts'}:
                for record in self.index['profiles']:
                    runtime = self.runtime(record['id'])
                    if action == 'stop_all':
                        await runtime.stop()
                        if data.get('preserve_wanted') is not True:
                            record['wanted'] = False
                    elif record.get('auto_farm' if data.get('reason')=='boot' else 'wanted'):
                        try:
                            await self.start(record['id'])
                        except Exception as error:
                            runtime._error = str(error)[:200]
                self.save()
                return self.snapshot()
            identity = data.get('account_id') or self.index['active']
            runtime = self.runtime(identity)
            record = self.record(identity)
            if action == 'account_select':
                self.index['active'] = identity
                self.save()
            elif action == 'account_autostart':
                if not isinstance(data.get('enabled'),bool):
                    raise ValueError('Invalid startup setting')
                record['auto_farm'] = data['enabled']
                self.save()
            elif action in {'start','restart'}:
                if action == 'restart':
                    await runtime.stop()
                await self.start(identity)
            else:
                result = await runtime.dispatch(data)
                if action in {'search','directory','check_connection'}:
                    return result
                if action in {'stop','logout'}:
                    record['wanted'] = False
                    if action == 'logout':
                        record['account'] = ''
                    self.save()
                if action == 'settings':
                    values = {k:v for k,v in data['values'].items() if k in GLOBAL}
                    self.index['preferences'].update(values)
                    for other in self.index['profiles']:
                        if other['id'] != identity and values:
                            await self.runtime(other['id']).dispatch({'action':'settings','values':values})
                    self.save()
            return self.snapshot()

    async def start(self, identity):
        runtime = self.runtime(identity)
        user = runtime.account_id()
        if user and any(self.runtime(p['id']).account_id()==user for p in self.index['profiles'] if p['id'] != identity):
            raise ValueError('Цей Twitch-акаунт уже підключений / Twitch account already connected')
        await runtime.dispatch({'action':'start'})
        self.record(identity)['wanted'] = True
        self.save()
