import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from multidict import CIMultiDict
from yarl import URL

import constants
from nyxor import android_runtime as runtime, browser_auth, network


def context():
    return {"headers": {"authorization": "OAuth fixturetoken", "client-id": constants.ClientType.WEB.CLIENT_ID,
                        "client-integrity": "fixtureproof", "x-device-id": "fixturedevice"},
            "user_agent": "Fixture Chrome", "expires_at": time.time() + 3600}


def response(status, data):
    value = Mock(status=status)
    value.json = AsyncMock(return_value=data)
    manager = AsyncMock()
    manager.__aenter__.return_value = value
    return manager


class BrowserAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.cookies = patch.object(constants, "COOKIES_PATH", self.root / "cookies.jar")
        self.cookies.start()

    async def asyncTearDown(self):
        self.cookies.stop()
        self.temporary.cleanup()

    def session(self, catalog):
        session = Mock()
        session.get.return_value = response(200, {"client_id": constants.ClientType.WEB.CLIENT_ID, "user_id": "123", "login": "fixture"})
        session.post.return_value = response(200, catalog)
        manager = AsyncMock()
        manager.__aenter__.return_value = session
        return manager

    async def test_catalog_failure_preserves_previous_session(self):
        constants.COOKIES_PATH.write_bytes(b"previous-session")
        for catalog in ({"data": {"currentUser": {"dropCampaigns": None}}}, {"errors": [{"message": "denied fixturetoken"}]}):
            with patch.object(network, "client_session", return_value=self.session(catalog)):
                with self.assertRaises(browser_auth.BrowserAuthError) as caught:
                    await browser_auth.import_context(context())
            self.assertNotIn("fixturetoken", str(caught.exception))
            self.assertEqual(constants.COOKIES_PATH.read_bytes(), b"previous-session")
            self.assertFalse(browser_auth.context_path().exists())

    async def test_validated_context_is_saved_and_never_appears_in_snapshot(self):
        with patch.object(network, "client_session", return_value=self.session({"data": {"currentUser": {"dropCampaigns": []}}})):
            self.assertEqual(await browser_auth.import_context(context()), "fixture")
        with patch.dict(os.environ, {"NYXOR_PLATFORM": "desktop"}):
            self.assertIs(browser_auth.stored_client(), constants.ClientType.WEB)
            state = runtime.snapshot()
            self.assertEqual(state["auth_mode"], "browser")
            self.assertEqual(runtime.account_id(), "123")
            self.assertNotIn("fixturetoken", json.dumps(state))
            self.assertNotIn("fixtureproof", json.dumps(state))
        with patch.dict(os.environ, {"NYXOR_PLATFORM": "android"}):
            self.assertIs(browser_auth.stored_client(), constants.ClientType.ANDROID_APP)

    async def test_cookie_commit_failure_restores_previous_context(self):
        previous=context();previous['headers']['authorization']='OAuth previous'
        browser_auth.atomic_save(browser_auth.context_path(),previous)
        constants.COOKIES_PATH.write_bytes(b'previous-session')
        with patch.object(network,'client_session',return_value=self.session({'data':{'currentUser':{'dropCampaigns':[]}}})), patch.object(aiohttp.CookieJar,'save',side_effect=OSError('locked')):
            with self.assertRaises(browser_auth.BrowserAuthError):
                await browser_auth.import_context(context())
        self.assertEqual(json.loads(browser_auth.context_path().read_text()),previous)
        self.assertEqual(constants.COOKIES_PATH.read_bytes(),b'previous-session')

    async def test_renewal_refreshes_proof_without_replacing_the_cookie_jar(self):
        catalog={'data':{'currentUser':{'dropCampaigns':[]}}}
        with patch.object(network,'client_session',return_value=self.session(catalog)):
            await browser_auth.import_context(context())
            saved=constants.COOKIES_PATH.read_bytes()
            updated=context();updated['headers']['client-integrity']='renewedproof'
            await browser_auth.import_context(updated,renewal=True)
        self.assertEqual(constants.COOKIES_PATH.read_bytes(),saved)
        self.assertEqual(json.loads(browser_auth.context_path().read_text())['headers']['client-integrity'],'renewedproof')

    async def test_request_hook_refreshes_only_matching_gql_context(self):
        browser_auth.atomic_save(browser_auth.context_path(), context())
        original={"Client-Id": constants.ClientType.WEB.CLIENT_ID, "Authorization": "OAuth fixturetoken", "X-Device-Id": "wrong", "User-Agent": "old"}
        params=SimpleNamespace(url=URL('https://gql.twitch.tv/gql'),headers=CIMultiDict(original))
        await browser_auth.apply_context(None,None,params)
        self.assertEqual(params.headers['Client-Integrity'],'fixtureproof')
        self.assertEqual(params.headers['X-Device-Id'],'fixturedevice')
        self.assertEqual(params.headers['User-Agent'],'Fixture Chrome')
        other=SimpleNamespace(url=URL('https://example.com/'),headers=CIMultiDict(original))
        await browser_auth.apply_context(None,None,other)
        self.assertNotIn('Client-Integrity',other.headers)
        wrong=SimpleNamespace(url=params.url,headers=CIMultiDict({**original,'Authorization':'OAuth other'}))
        with self.assertRaises(browser_auth.BrowserAuthError):
            await browser_auth.apply_context(None,None,wrong)

    async def test_expired_context_and_account_change_are_rejected(self):
        value=context();value['expires_at']=0
        with self.assertRaises(browser_auth.BrowserAuthError):
            browser_auth.validate_context(value)
        browser_auth.atomic_save(browser_auth.context_path(), value)
        params=SimpleNamespace(url=URL('https://gql.twitch.tv/gql'),headers=CIMultiDict({'Client-Id':constants.ClientType.WEB.CLIENT_ID}))
        with self.assertRaises(browser_auth.BrowserAuthError) as caught:
            await browser_auth.apply_context(None,None,params)
        self.assertEqual(caught.exception.code,'browser_expired')
        jar=aiohttp.CookieJar()
        jar.update_cookies({'persistent':'999','auth-token':'fixturetoken'},constants.ClientType.WEB.CLIENT_URL)
        jar.save(constants.COOKIES_PATH)
        with patch.object(network,'client_session',return_value=self.session({'data':{'currentUser':{'dropCampaigns':[]}}})):
            with self.assertRaises(browser_auth.BrowserAuthError) as caught:
                await browser_auth.import_context(context(),renewal=True)
        self.assertEqual(caught.exception.code,'browser_account_changed')

    async def test_invalid_client_is_specific_and_does_not_delete_existing_login(self):
        constants.COOKIES_PATH.write_bytes(b'previous-session')
        session=Mock();session.post.return_value=response(400,{'message':'invalid client'})
        manager=AsyncMock();manager.__aenter__.return_value=session
        with patch.object(network,'client_session',return_value=manager), patch.object(network,'connection_blocker',return_value=''):
            await runtime.authenticate()
        self.assertEqual(runtime._auth['error_code'],'auth_client')
        self.assertEqual(runtime._auth['http_status'],400)
        self.assertEqual(constants.COOKIES_PATH.read_bytes(),b'previous-session')
