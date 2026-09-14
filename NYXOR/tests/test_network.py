import asyncio
import socket
import unittest
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from nyxor import network


class NetworkTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.adapter = Mock()
        self.adapter.status.return_value = 'available'
        self.previous = network._android
        network.configure_android(self.adapter)
        self.dns_error = socket.gaierror(socket.EAI_NONAME, 'No address associated with hostname')

    def tearDown(self):
        network.configure_android(self.previous)

    async def test_successful_python_resolution_does_not_use_fallback(self):
        expected = [dict(host='192.0.2.1')]
        with patch.object(aiohttp.ThreadedResolver, 'resolve', AsyncMock(return_value=expected)):
            self.assertEqual(await network.AndroidResolver().resolve('id.twitch.tv'), expected)
        self.adapter.resolve.assert_not_called()

    async def test_fallback_preserves_tls_hostname_and_ipv4_ipv6(self):
        self.adapter.resolve.return_value = ['192.0.2.1', '2001:db8::1']
        with patch.object(aiohttp.ThreadedResolver, 'resolve', AsyncMock(side_effect=self.dns_error)):
            results = await network.AndroidResolver().resolve('id.twitch.tv', 443, socket.AF_UNSPEC)
        self.assertEqual([r['family'] for r in results], [socket.AF_INET, socket.AF_INET6])
        self.assertTrue(all(r['hostname'] == 'id.twitch.tv' and r['port'] == 443 for r in results))

    async def test_explicit_family_filters_other_addresses(self):
        self.adapter.resolve.return_value = ['192.0.2.1', '2001:db8::1']
        with patch.object(aiohttp.ThreadedResolver, 'resolve', AsyncMock(side_effect=self.dns_error)):
            results = await network.AndroidResolver().resolve('id.twitch.tv', 443, socket.AF_INET6)
        self.assertEqual([r['host'] for r in results], ['2001:db8::1'])

    async def test_transient_failure_retries_once(self):
        self.adapter.resolve.side_effect = [RuntimeError('network changing'), ['192.0.2.1']]
        with patch.object(aiohttp.ThreadedResolver, 'resolve', AsyncMock(side_effect=self.dns_error)), patch.object(network.asyncio, 'sleep', AsyncMock()) as sleep:
            self.assertTrue(await network.AndroidResolver().resolve('id.twitch.tv'))
        self.assertEqual(self.adapter.resolve.call_count, 2)
        sleep.assert_awaited_once_with(2)

    async def test_persistent_failure_is_bounded_and_remains_dns_error(self):
        self.adapter.resolve.side_effect = RuntimeError('DNS unavailable')
        with patch.object(aiohttp.ThreadedResolver, 'resolve', AsyncMock(side_effect=self.dns_error)), patch.object(network.asyncio, 'sleep', AsyncMock()):
            with self.assertRaises(socket.gaierror):
                await network.AndroidResolver().resolve('id.twitch.tv')
        self.assertEqual(self.adapter.resolve.call_count, 2)

    async def test_cancellation_is_not_swallowed_or_retried(self):
        with patch.object(aiohttp.ThreadedResolver, 'resolve', AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                await network.AndroidResolver().resolve('id.twitch.tv')
        self.adapter.resolve.assert_not_called()

    async def test_session_keeps_tls_validation_and_desktop_default(self):
        async with network.client_session() as session:
            self.assertIsInstance(session.connector._resolver, network.AndroidResolver)
            self.assertIs(session.connector._ssl, True)
        network.configure_android(None)
        async with network.client_session() as session:
            self.assertNotIsInstance(session.connector._resolver, network.AndroidResolver)

    async def test_connection_check_accepts_only_expected_token_free_401(self):
        response = Mock(status=401)
        response_context = AsyncMock()
        response_context.__aenter__.return_value = response
        session = Mock()
        session.get.return_value = response_context
        session_context = AsyncMock()
        session_context.__aenter__.return_value = session
        with patch.object(network, 'client_session', return_value=session_context):
            self.assertEqual(await network.check_connection(), {'status': 'ok'})
            response.status = 503
            self.assertEqual(await network.check_connection(), {'status': 'twitch_http'})
        session.get.assert_called_with('https://id.twitch.tv/oauth2/validate', allow_redirects=False)

    async def test_offline_check_never_starts_http_and_rechecks_after_reconnect(self):
        self.adapter.status.return_value = 'offline'
        with patch.object(network, 'client_session') as factory:
            self.assertEqual(await network.check_connection(), {'status': 'offline'})
            factory.assert_not_called()
        self.adapter.status.return_value = 'available'
        self.assertEqual(network.connection_blocker(), '')

    async def test_unknown_connectivity_does_not_block_a_real_request(self):
        self.adapter.status.side_effect = RuntimeError('status unavailable')
        self.assertEqual(network.connection_state(), 'unknown')
        self.assertEqual(network.connection_blocker(), '')

    async def test_error_diagnosis_distinguishes_dns_offline_and_tls(self):
        error = aiohttp.ClientConnectorError(Mock(), self.dns_error)
        self.assertEqual(network.error_code(error), 'dns')
        self.adapter.status.return_value = 'offline'
        self.assertEqual(network.error_code(error), 'offline')
        self.adapter.status.return_value = 'captive'
        self.assertEqual(network.error_code(error), 'captive')
        self.assertEqual(network.error_code(aiohttp.ClientSSLError(Mock(), OSError())), 'tls')
        self.assertEqual(network.error_code(RuntimeError('code expired')), '')
