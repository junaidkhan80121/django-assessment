from functools import lru_cache
from urllib.parse import quote
import httpx
from django.conf import settings

class MapboxUnavailableError(Exception):
    pass

@lru_cache(maxsize=256)
def geocode_place(query: str):
    if not query or not isinstance(query, str):
        raise ValueError(f'Location not found or not in USA: {query}')
    token = settings.MAPBOX_TOKEN
    if not token:
        raise ValueError('Mapbox token not configured')

    endpoint = settings.MAPBOX_GEOCODING_URL.format(query=quote(query))
    params = {'country': 'us', 'types': 'place,address', 'access_token': token}
    url = endpoint
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise MapboxUnavailableError('Mapbox geocoding timeout') from exc
    except httpx.HTTPError as exc:
        raise MapboxUnavailableError('Mapbox geocoding unavailable') from exc

    if 400 <= resp.status_code < 500:
        raise ValueError(f'Location not found or not in USA: {query}')
    if resp.status_code >= 500:
        raise MapboxUnavailableError('Mapbox geocoding unavailable')

    data = resp.json()
    if not data.get('features'):
        raise ValueError(f'Location not found or not in USA: {query}')

    feature = data['features'][0]
    lon, lat = feature['center']
    if not (-130.0 <= lon <= -65.0 and 23.0 <= lat <= 50.0):
        raise ValueError(f'Location not found or not in USA: {query}')
    return lon, lat
