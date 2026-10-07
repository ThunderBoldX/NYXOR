"""Public category metadata from Twitch's website; no account credentials."""
from constants import ClientType

GQL_URL = "https://gql.twitch.tv/gql"
SEARCH_QUERY = '''query NyxorCategorySearch($query: String!) {
  searchFor(userQuery: $query, platform: "web", options: {targets: [{index: GAME}]}) {
    games { edges { item { ... on Game { id name boxArtURL(width: 144, height: 192) } } } }
  }
}'''
DIRECTORY_QUERY = '''query NyxorGameDirectory($name: String!, $after: Cursor) {
  game(name: $name) { id name
    streams(first: 100, after: $after, options: {sort: VIEWER_COUNT}) {
      edges { cursor node { id viewersCount title game {id name} broadcaster {id login displayName} } }
      pageInfo {hasNextPage}
    }
  }
}'''
ART_QUERY = '''query NyxorGameArtwork($name: String!) {
  game(name: $name) {id name boxArtURL(width: 144, height: 192)}
}'''


class CatalogError(RuntimeError):
    def __init__(self, code="twitch_error"):
        self.code = code
        super().__init__(code)


async def public_request(session, query, variables):
    async with session.post(GQL_URL, headers={"Client-Id": ClientType.WEB.CLIENT_ID},
                            json={"query": query, "variables": variables}, allow_redirects=False) as response:
        if response.status == 429:
            raise CatalogError("rate_limited")
        if response.status != 200:
            raise CatalogError()
        data = await response.json()
    if not isinstance(data, dict) or data.get("errors") or not isinstance(data.get("data"), dict):
        raise CatalogError()
    return data["data"]


async def search_categories(session, query):
    data = await public_request(session, SEARCH_QUERY, {"query": query})
    games = (data.get("searchFor") or {}).get("games") or {}
    edges = games.get("edges")
    if not isinstance(edges, list):
        raise CatalogError()
    rows = []
    for edge in edges:
        item = edge.get("item") if isinstance(edge, dict) else None
        if isinstance(item, dict):
            rows.append({"id": item.get("id"), "name": item.get("name"), "box_art_url": item.get("boxArtURL")})
    return {"data": rows}


async def directory_page(session, name, after=None):
    data = await public_request(session, DIRECTORY_QUERY, {"name": name, "after": after})
    game = data.get("game")
    if game is None:
        return {"items": [], "cursor": "", "complete": True}
    if not isinstance(game, dict) or str(game.get("name", "")).casefold() != name.casefold():
        raise CatalogError()
    streams = game.get("streams") or {}
    edges = streams.get("edges")
    if not isinstance(edges, list):
        raise CatalogError()
    rows = []
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        if not isinstance(node, dict):
            continue
        broadcaster = node.get("broadcaster") or {}
        actual_game = node.get("game") or {}
        if (str(actual_game.get("id")) != str(game.get("id")) or str(actual_game.get("name", "")).casefold() != name.casefold()
                or not node.get("id") or not broadcaster.get("id") or not broadcaster.get("login")):
            continue
        rows.append({"login": str(broadcaster["login"]).casefold(), "display_name": broadcaster.get("displayName") or broadcaster["login"],
                     "stream_id": str(node["id"]), "channel_id": str(broadcaster["id"]), "game": game["name"], "game_id": str(game["id"]),
                     "viewers": node.get("viewersCount") or 0, "title": node.get("title") or ""})
    complete = (streams.get("pageInfo") or {}).get("hasNextPage") is False
    cursor = next((str(edge.get("cursor")) for edge in reversed(edges) if isinstance(edge, dict) and edge.get("cursor")), "")
    return {"items": rows, "cursor": cursor, "complete": complete}
