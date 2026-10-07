import unittest
from unittest.mock import Mock,AsyncMock,patch
from constants import ClientType
from nyxor import twitch_catalog,points_selection,game_art

def response(payload):
    value=Mock(status=200);value.json=AsyncMock(return_value={'data':payload})
    manager=AsyncMock();manager.__aenter__.return_value=value
    return manager

def stream(login,viewers,game='1'):
    return {'id':'stream-'+login,'viewersCount':viewers,'title':'Live','game':{'id':game,'name':'World of Tanks'},
            'broadcaster':{'id':'channel-'+login,'login':login,'displayName':login.title()}}

class PublicCatalogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        points_selection._directories.clear();game_art._cache.clear()

    async def test_directory_paginates_for_low_viewers_and_checks_the_category(self):
        def page(items,cursor,more):
            return {'game':{'id':'1','name':'World of Tanks','streams':{'edges':[{'cursor':cursor,'node':item} for item in items], 'pageInfo':{'hasNextPage':more}}}}
        session=Mock();session.post.side_effect=[response(page([stream('large',500),stream('outside',0,'2')],'next',True)),
                                                response(page([stream('small',1),stream('large',499)],'last',False))]
        result=await points_selection.category_channels(session,{'Authorization':'OAuth fixture','Client-Id':ClientType.WEB.CLIENT_ID},'World of Tanks','quiet')
        self.assertEqual([item['login'] for item in result['items']],['small','large'])
        self.assertTrue(result['complete'])
        self.assertEqual(session.post.call_args.kwargs['json']['variables']['after'],'next')
        self.assertNotIn('Authorization',session.post.call_args.kwargs['headers'])
        session.get.assert_not_called()

    async def test_popular_directory_is_marked_partial_without_scanning_all_pages(self):
        session=Mock();session.post.return_value=response({'game':{'id':'1','name':'World of Tanks','streams':{'edges':[{'cursor':'next','node':stream('one',5)}],'pageInfo':{'hasNextPage':True}}}})
        result=await points_selection.category_channels(session,{'Client-Id':ClientType.WEB.CLIENT_ID},'World of Tanks','popular')
        self.assertFalse(result['complete']);self.assertEqual(len(result['items']),1);session.post.assert_called_once()

    async def test_game_art_uses_public_web_metadata_and_rejects_foreign_urls(self):
        for name,url,expected in [('World of Tanks','https://static-cdn.jtvnw.net/ttv-boxart/1-144x192.jpg',True),('Rust','https://example.com/art.jpg',False)]:
            session=Mock();session.post.return_value=response({'game':{'id':'1','name':name,'boxArtURL':url}})
            art=await game_art.game_art(session,{'Client-Id':ClientType.WEB.CLIENT_ID},name)
            self.assertEqual(bool(art),expected);session.get.assert_not_called()
