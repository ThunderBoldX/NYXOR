"""Finite, user-initiated iOS sessions over the shared account engine.

Only the native serial queue calls this module. Progress is confirmed Twitch
minutes plus one completion unit for the confirmed claim, never a local timer.
"""
import json
import time
import uuid
from nyxor import android_runtime as runtime

_plan = None
_granted = False
_suspended = set()


class MinerError(ValueError):
    def __init__(self, response):
        super().__init__(response.get('error', 'Miner request failed'))
        self.response = response


def initialize(directory):
    runtime.initialize(directory)


def call(action, **values):
    response = json.loads(runtime.request(json.dumps(dict(action=action, **values))))
    if not response.get('ok'):
        raise MinerError(response)
    return response['data']


def goal_progress(snapshot, plan, now=None):
    now = time.monotonic() if now is None else now
    claimed = any(row.get('confirmed') is True and row.get('drop_id') == plan['drop_id']
                  and row.get('campaign_id') == plan['campaign_id'] for row in snapshot.get('history', []))
    row = next((row for row in snapshot.get('state', {}).get('active_drops', [])
                if row.get('drop_id') == plan['drop_id'] and row.get('campaign_id') == plan['campaign_id']), None)
    if row:
        current = row.get('current')
        if type(current) is int and current >= 0:
            plan['current'] = min(plan['required'], max(plan['current'], current))
        plan['missing_since'] = None
    elif not claimed and plan['missing_since'] is None:
        plan['missing_since'] = now
    unavailable = not claimed and plan['missing_since'] is not None and now-plan['missing_since'] >= 90
    state = 'completed' if claimed else 'unavailable' if unavailable else 'watching' if row else 'waiting'
    if not snapshot.get('running') and not claimed:
        state = 'stopped'
    current = plan['required'] if claimed else plan['current']
    return dict(id=plan['id'], status=state, title=plan['drop'], game=plan['game'], account_id=plan['account_id'],
                account=plan.get('account', ''), current=current, required=plan['required'], units=current+int(claimed), total=plan['required']+1)


def selected():
    return call('account_snapshot', account_id=_plan['account_id'])


def cancel_plan(identity=None):
    global _plan, _granted
    if _plan and (identity is None or identity == _plan['id']):
        _plan = None
        _granted = False


def dispatch(data):
    global _plan, _granted, _suspended
    action = data.get('action', 'snapshot')
    if action == 'ios_plan':
        if _plan:
            raise ValueError('Finish or cancel the current background session first')
        state = call('snapshot')
        row = next((row for row in state.get('state', {}).get('active_drops', [])
                    if row.get('drop_id') == data.get('drop_id')), None)
        if not state.get('running') or not row or type(row.get('required')) is not int or row['required'] <= 0:
            raise ValueError('Start farming and select an active Drop first')
        if type(row.get('current')) is not int or not 0 <= row['current'] <= row['required']:
            raise ValueError('Twitch has not reported valid progress')
        _plan = dict(id=str(uuid.uuid4()), account_id=state['active_account_id'], drop_id=row['drop_id'],
                     campaign_id=row['campaign_id'], game=state['state'].get('game', ''), drop=row['drop'],
                     account=state.get('account') or state['state'].get('account') or '',
                     current=row['current'], required=row['required'], missing_since=None)
        return goal_progress(state, _plan)
    if action == 'ios_grant':
        if not _plan or data.get('id') != _plan['id']:
            raise ValueError('Background session was cancelled')
        if _plan['account_id'] in _suspended:
            call('start', account_id=_plan['account_id'])
            _suspended.discard(_plan['account_id'])
        _granted = True
        return goal_progress(selected(), _plan)
    if action == 'ios_poll':
        if not _plan or data.get('id') != _plan['id']:
            raise ValueError('Background session was cancelled')
        return goal_progress(selected(), _plan)
    if action == 'ios_finish':
        if _plan and data.get('id') == _plan['id']:
            identity = _plan['account_id']
            _suspended.discard(identity)
            if data.get('stop') is True:
                call('stop', account_id=identity)
            cancel_plan(_plan['id'])
        return call('snapshot')
    if action == 'ios_suspend':
        state = call('snapshot')
        keep = _plan['account_id'] if _plan and _granted else None
        for row in state.get('accounts', []):
            if row['running'] and row['id'] != keep:
                _suspended.add(row['id'])
                call('stop', account_id=row['id'])
        return call('snapshot')
    if action == 'ios_resume':
        identities, _suspended = _suspended, set()
        state = call('snapshot')
        valid = {row['id'] for row in state.get('accounts', [])}
        for identity in identities & valid:
            try:
                call('start', account_id=identity)
            except ValueError:
                pass
        return call('snapshot')
    if action in {'stop', 'logout', 'account_delete', 'restart'}:
        identity = data.get('account_id') or call('snapshot').get('active_account_id')
        affected = data.get('ids', []) if action == 'account_delete' else [identity]
        _suspended.difference_update(affected)
        if _plan and _plan['account_id'] in affected:
            _suspended.discard(_plan['account_id'])
            cancel_plan()
    if action == 'settings' and 'launch_on_boot' in data.get('values', {}):
        raise ValueError('iOS does not support reboot autostart')
    return call(action, **{k:v for k,v in data.items() if k != 'action'})


def request(payload):
    try:
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError('Invalid request')
        result = dispatch(data)
        if isinstance(result, dict) and 'settings' in result:
            result['platform'] = 'ios'
            result['ios'] = dict(session=_plan['id'] if _plan else None, granted=_granted)
            result['settings']['launch_on_boot'] = False
        return json.dumps(dict(ok=True, data=result), ensure_ascii=False)
    except MinerError as error:
        return json.dumps(error.response, ensure_ascii=False)
    except Exception as error:
        return json.dumps(dict(ok=False, error=str(error)[:240]), ensure_ascii=False)
