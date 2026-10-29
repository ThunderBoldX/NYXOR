import copy
import json
import unittest
from unittest.mock import patch
from nyxor import ios_runtime as ios


def snapshot():
    return dict(running=True,active_account_id='a',settings={},accounts=[dict(id='a',running=True),dict(id='b',running=True)],
                state=dict(game='Rust',active_drops=[dict(drop_id='d',campaign_id='c',drop='Reward',current=10,required=60)]),history=[])


class SessionTests(unittest.TestCase):
    def setUp(self):
        ios._plan=None;ios._granted=False;ios._suspended=set()
        self.state=snapshot();self.calls=[]
        def call(action,**values):
            self.calls.append((action,values))
            return copy.deepcopy(self.state)
        self.patch=patch.object(ios,'call',side_effect=call);self.patch.start()
    def tearDown(self):
        self.patch.stop();ios._plan=None;ios._granted=False;ios._suspended=set()
    def plan(self):
        return ios.dispatch(dict(action='ios_plan',drop_id='d'))
    def test_goal_accepts_only_running_active_drop_and_server_progress(self):
        for field,value in [('running',False)]:
            self.state[field]=value
            with self.assertRaises(ValueError):self.plan()
        self.state=snapshot();self.state['state']['active_drops'][0]['current']=True
        with self.assertRaises(ValueError):self.plan()
        self.state=snapshot();p=self.plan()
        self.assertEqual((p['current'],p['units'],p['total']),(10,10,61))
        with self.assertRaises(ValueError):self.plan()
    def test_completion_requires_exact_confirmed_claim_not_missing_drop(self):
        p=self.plan();plan=ios._plan
        self.state['state']['active_drops']=[]
        self.assertEqual(ios.goal_progress(self.state,plan,0)['status'],'waiting')
        self.assertEqual(ios.goal_progress(self.state,plan,91)['status'],'unavailable')
        self.state['history']=[dict(confirmed=False,drop_id='d',campaign_id='c')]
        self.assertNotEqual(ios.goal_progress(self.state,plan,92)['status'],'completed')
        self.state['history'][0]['confirmed']=True
        done=ios.goal_progress(self.state,plan,93)
        self.assertEqual((done['status'],done['units'],done['total']),('completed',61,61))
    def test_minutes_do_not_regress_or_count_other_rewards(self):
        self.plan();plan=ios._plan
        self.state['state']['active_drops'][0]['current']=40
        self.assertEqual(ios.goal_progress(self.state,plan)['current'],40)
        self.state['state']['active_drops'][0]['current']=20
        self.state['history']=[dict(confirmed=True,drop_id='other',campaign_id='c')]
        self.assertEqual(ios.goal_progress(self.state,plan)['current'],40)
        self.assertNotEqual(ios.goal_progress(self.state,plan)['status'],'completed')
    def test_grant_keeps_only_pinned_account_running_when_backgrounded(self):
        p=self.plan();ios.dispatch(dict(action='ios_grant',id=p['id']))
        self.state['active_account_id']='b'
        ios.dispatch(dict(action='ios_suspend'))
        stops=[v['account_id'] for a,v in self.calls if a=='stop']
        self.assertEqual(stops,['b']);self.assertEqual(ios._suspended,{'b'})
        ios.dispatch(dict(action='ios_poll',id=p['id']))
        self.assertEqual(self.calls[-1],('account_snapshot',dict(account_id='a')))
    def test_foreground_resume_and_delayed_grant_preserve_user_intent(self):
        p=self.plan();ios.dispatch(dict(action='ios_suspend'))
        self.assertEqual(ios._suspended,{'a','b'})
        ios.dispatch(dict(action='ios_grant',id=p['id']))
        self.assertEqual(ios._suspended,{'b'})
        ios.dispatch(dict(action='ios_finish',id=p['id'],stop=True))
        self.assertIsNone(ios._plan);self.assertNotIn('a',ios._suspended)
        ios.dispatch(dict(action='ios_resume'))
        self.assertEqual([v['account_id'] for a,v in self.calls if a=='start'],['a','b'])
    def test_old_finish_and_late_grant_cannot_restart_cancelled_goal(self):
        p=self.plan();ios.dispatch(dict(action='stop',account_id='a'))
        self.assertIsNone(ios._plan)
        with self.assertRaises(ValueError):ios.dispatch(dict(action='ios_grant',id=p['id']))
        new=self.plan();ios.dispatch(dict(action='ios_finish',id=p['id'],stop=True))
        self.assertEqual(ios._plan['id'],new['id'])
    def test_cold_resume_starts_nothing_and_ios_has_no_reboot_switch(self):
        ios.dispatch(dict(action='ios_resume'))
        self.assertFalse(any(a=='start' for a,v in self.calls))
        result=json.loads(ios.request(json.dumps(dict(action='settings',values=dict(launch_on_boot=True)))))
        self.assertFalse(result['ok'])
        result=json.loads(ios.request('{}'))
        self.assertEqual(result['data']['platform'],'ios')
    def test_watch_completion_reserves_claim_unit_until_twitch_confirms(self):
        self.plan();self.state['state']['active_drops'][0]['current']=60
        result=ios.goal_progress(self.state,ios._plan)
        self.assertEqual((result['current'],result['units'],result['total']),(60,60,61))
        self.assertNotEqual(result['status'],'completed')
    def test_explicit_stop_of_paused_other_account_prevents_auto_resume(self):
        p=self.plan();ios.dispatch(dict(action='ios_grant',id=p['id']))
        ios.dispatch(dict(action='ios_suspend'));self.assertEqual(ios._suspended,{'b'})
        ios.dispatch(dict(action='stop',account_id='b'));self.assertEqual(ios._suspended,set())
        ios.dispatch(dict(action='ios_resume'))
        self.assertFalse(any(a=='start' for a,v in self.calls))


if __name__=='__main__':unittest.main()
