import unittest
from nyxor.android_status import notification_status


class AndroidStatusTests(unittest.TestCase):
    def setUp(self):
        self.data = dict(running=True, network='available', settings=dict(language='uk'), state=dict(
            game='Rust', channel='SharedStreamer', active_drops=[
                dict(drop='Drop One', current=45, required=60), dict(drop='Drop Two', current=45, required=120)]))

    def test_shows_shared_campaign_progress(self):
        result = notification_status(self.data)
        self.assertEqual(result['progress'], 75)
        self.assertIn('SharedStreamer', result['text'])
        self.assertIn('Drop Two · 37%', result['details'])

    def test_offline_or_reconnecting_hides_stale_progress(self):
        self.data['network'] = 'offline'
        self.assertIn('Очікуємо інтернет', notification_status(self.data)['title'])
        self.assertIsNone(notification_status(self.data)['progress'])
        self.data['network'] = 'available'
        self.data['state']['_meta'] = dict(error='private technical error')
        result = notification_status(self.data)
        self.assertIn('Відновлюємо', result['title'])
        self.assertNotIn('private technical error', str(result))

    def test_stopped_state_takes_precedence_and_english_points_work(self):
        self.data.update(running=False, network='offline')
        self.assertIn('На паузі', notification_status(self.data)['title'])
        self.data.update(running=True, network='available', settings=dict(language='en'))
        self.data['state'].update(mode='points', points='100', active_drops=[])
        self.assertIn('Channel points: 100', notification_status(self.data)['details'])

    def test_invalid_progress_does_not_crash_and_percentage_is_bounded(self):
        self.data['state']['active_drops'] = [dict(current=10, required=0), dict(current='bad', required=10), dict(current=200, required=100)]
        self.assertEqual(notification_status(self.data)['progress'], 100)
