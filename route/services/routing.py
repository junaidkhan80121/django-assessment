import httpx
from django.conf import settings
from .cache_store import load_json_cache, save_json_cache
from .geocoding import MapboxUnavailableError

class MapboxRoutingError(Exception):
    pass


def get_route(start_coords, finish_coords):
    token = settings.MAPBOX_TOKEN
    if not token:
        raise ValueError('Mapbox token not configured')
    start_lon, start_lat = start_coords
    finish_lon, finish_lat = finish_coords
    cache_key = (
        f'{float(start_lon):.6f},{float(start_lat):.6f}'
        f'->{float(finish_lon):.6f},{float(finish_lat):.6f}'
    )
    cache = load_json_cache('route_cache.json')
    if cache_key in cache:
        return cache[cache_key]

    coords = f'{start_lon},{start_lat};{finish_lon},{finish_lat}'
    endpoint = settings.MAPBOX_DIRECTIONS_URL.format(coords=coords)
    params = {'geometries': 'geojson', 'overview': 'full', 'access_token': token}
    url = endpoint
    try:
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, params=params)
    except httpx.TimeoutException as exc:
        raise MapboxUnavailableError('Mapbox directions timeout') from exc
    except httpx.HTTPError as exc:
        raise MapboxUnavailableError('Mapbox directions unavailable') from exc

    if 400 <= resp.status_code < 500:
        raise ValueError('Bad input for route API')
    if resp.status_code >= 500:
        raise MapboxUnavailableError('Mapbox directions unavailable')

    data = resp.json()
    if not data.get('routes'):
        raise ValueError('No route found')
    route = data['routes'][0]
    geometry = route.get('geometry', {})
    distance_meters = route.get('distance', 0)
    route_result = {
        # Persist the full route response so repeated trips can avoid another directions call.
        'distance_miles': float(distance_meters) / 1609.34,
        'duration_seconds': route.get('duration', 0),
        'geometry': geometry,
    }
    cache[cache_key] = route_result
    save_json_cache('route_cache.json', cache)
    return route_result
