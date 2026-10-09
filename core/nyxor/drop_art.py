"""Public reward artwork already returned by Twitch campaign queries."""
from urllib.parse import urlsplit


def image_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        return ''
    try:
        url = urlsplit(value)
        if (url.scheme == 'https' and url.hostname in {'static-cdn.jtvnw.net', 'static.twitchcdn.net'}
                and not url.username and not url.password and url.port in {None, 443}
                and not url.fragment):
            return value
    except ValueError:
        pass
    return ''


def benefits(drop):
    result = []
    for edge in drop.get('benefitEdges') or []:
        benefit = edge.get('benefit') if isinstance(edge, dict) else None
        if isinstance(benefit, dict):
            result.append({'id': str(benefit.get('id') or '')[:160],
                           'name': str(benefit.get('name') or drop.get('name') or 'Drop')[:300],
                           'image_url': image_url(benefit.get('imageAssetURL'))})
    return result[:30]
