import os
import unittest
from unittest.mock import Mock, AsyncMock, patch
import aiohttp
from nyxor import game_search, twitch_catalog

def response(status,payload):
    value=Mock(status=status);value.json=AsyncMock(return_value=payload)
    manager=AsyncMock();manager.__aenter__.return_value=value
    return manager

class DesktopCategorySearch(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'NYXOR_PLATFORM':'desktop'});self.env.start();game_search._CACHE.clear()
    def tearDown(self):
        self.env.stop();game_search._CACHE.clear()
    def session(self,status,payload):
        session=Mock();session.post.return_value=response(status,payload)
        manager=AsyncMock();manager.__aenter__.return_value=session
        return session,manager
    async def test_world_of_tanks_ranked_first_without_reading_account(self):
        payload={'data':{'searchFor':{'games':{'edges':[
            {'item':{'id':'2','name':'World of Tanks: Blitz','boxArtURL':'https://static-cdn.jtvnw.net/ttv-boxart/2.jpg'}},
            {'item':{'id':'1','name':'World of Tanks','boxArtURL':'https://static-cdn.jtvnw.net/ttv-boxart/1.jpg'}},
            {'item':{'id':'1','name':'World of Tanks'}},None]}}}}
        session,manager=self.session(200,payload)
        with patch.object(game_search,'client_session',return_value=manager) as factory,patch.object(game_search,'_load_twitch_token',side_effect=AssertionError('Do not read account')):
            games=await game_search.search_game_categories('  World  Of Tanks  ')
            self.assertEqual([game.name for game in games],['World of Tanks','World of Tanks: Blitz'])
            self.assertEqual(games[0].id,'1')
            self.assertEqual(await game_search.search_game_categories('world of tanks'),games);session.post.assert_called_once()
        self.assertIsInstance(factory.call_args.kwargs['cookie_jar'],aiohttp.DummyCookieJar)
        self.assertNotIn('Authorization',session.post.call_args.kwargs['headers'])
        self.assertEqual(session.post.call_args.kwargs['json']['variables']['query'],'World Of Tanks')
    async def test_empty_results_are_distinct_from_failures(self):
        for status,payload,code in [(429,{},'rate_limited'),(404,{},'twitch_error'),(200,{'errors':[{'message':'rejected'}]},'twitch_error'),(200,{'data':{'searchFor':{'games':None}}},'twitch_error')]:
            game_search._CACHE.clear();_,manager=self.session(status,payload)
            with patch.object(game_search,'client_session',return_value=manager),self.assertRaises(game_search.GameSearchError) as caught:
                await game_search.search_game_categories('World of Tanks')
            self.assertEqual(caught.exception.code,code);self.assertFalse(game_search._CACHE)
        _,manager=self.session(200,{'data':{'searchFor':{'games':{'edges':[]}}}})
        with patch.object(game_search,'client_session',return_value=manager):
            self.assertEqual(await game_search.search_game_categories('missing'),[])
    async def test_network_error_does_not_expose_transport_details(self):
        session,manager=self.session(200,{});session.post.side_effect=aiohttp.ClientConnectionError('private detail')
        with patch.object(game_search,'client_session',return_value=manager),self.assertRaises(game_search.GameSearchError) as caught:
            await game_search.search_game_categories('World of Tanks')
        self.assertEqual(caught.exception.code,'network');self.assertNotIn('private detail',str(caught.exception))
    async def test_queries_are_variables_and_short_query_does_no_request(self):
        with patch.object(game_search,'client_session') as factory:
            self.assertEqual(await game_search.search_game_categories('w'),[])
        factory.assert_not_called()
        session,manager=self.session(200,{'data':{'searchFor':{'games':{'edges':[]}}}})
        query='test" } mutation { unrelated }'
        with patch.object(game_search,'client_session',return_value=manager):
            await game_search.search_game_categories(query)
        self.assertEqual(session.post.call_args.kwargs['json']['query'],twitch_catalog.SEARCH_QUERY)
        self.assertEqual(session.post.call_args.kwargs['json']['variables']['query'],query)
