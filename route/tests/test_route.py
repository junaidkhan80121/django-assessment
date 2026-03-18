import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from route.serializers import RouteRequestSerializer
from route.services import geocoding, routing
from route.services.optimizer import optimize_fuel_stops


def test_request_serializer_valid():
    serializer = RouteRequestSerializer(data={'start': 'New York, NY', 'finish': 'Los Angeles, CA'})
    assert serializer.is_valid()


def test_request_serializer_invalid_blank():
    serializer = RouteRequestSerializer(data={'start': '   ', 'finish': 'Los Angeles, CA'})
    assert not serializer.is_valid()
    assert 'start' in serializer.errors


def test_request_serializer_rejects_same_start_and_finish():
    serializer = RouteRequestSerializer(data={'start': 'Denver, CO', 'finish': 'denver, co'})
    assert not serializer.is_valid()
    assert serializer.errors == {'finish': ['Start and finish cannot be the same location.']}


def test_optimizer_no_route_distance():
    with pytest.raises(ValueError):
        optimize_fuel_stops(route_points=[[ -74.0,40.7],[-118.2,34.0]], total_distance_miles=0, route_stations=[])


def test_optimizer_picks_cheapest():
    route_points = [[-74.0, 40.7], [-73.5, 41.0], [-73.0, 41.4], [-72.5, 41.8], [-72.0, 42.2], [-71.5, 42.6]]
    stations = [
        {'name': 'A', 'address': '1', 'city': 'X', 'state': 'NY', 'lat': 41.0, 'lon': -73.5, 'price': 4.0},
        {'name': 'B', 'address': '2', 'city': 'Y', 'state': 'NY', 'lat': 41.8, 'lon': -72.5, 'price': 3.5},
        {'name': 'C', 'address': '3', 'city': 'Z', 'state': 'NY', 'lat': 42.2, 'lon': -72.0, 'price': 3.9},
    ]
    stops, total = optimize_fuel_stops(route_points=route_points, total_distance_miles=1200, route_stations=stations)
    assert len(stops) >= 1
    assert any(s['station_name'] == 'B' for s in stops)


def test_optimizer_prices_short_trip_from_route_data():
    route_points = [[-74.0, 40.7], [-73.5, 41.0]]
    stations = [
        {'name': 'Start Fuel', 'address': '1', 'city': 'X', 'state': 'NY', 'lat': 40.7, 'lon': -74.0, 'price': 3.5},
    ]

    stops, total = optimize_fuel_stops(route_points=route_points, total_distance_miles=100, route_stations=stations)

    assert stops == []
    assert total == 35.0


def test_optimizer_raises_for_infeasible_long_route():
    route_points = [[-74.0, 40.7], [-73.0, 41.4], [-72.0, 42.2], [-71.0, 43.0]]
    stations = [
        {'name': 'Too Late', 'address': '1', 'city': 'X', 'state': 'NY', 'lat': 42.2, 'lon': -72.0, 'price': 3.5},
    ]

    with pytest.raises(ValueError, match='Route cannot be completed'):
        optimize_fuel_stops(route_points=route_points, total_distance_miles=1200, route_stations=stations)


def test_geocode_place_uses_persistent_cache(monkeypatch):
    geocoding.geocode_place.cache_clear()
    cache = {}
    calls = {'count': 0}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {'features': [{'center': [-74.0060, 40.7128]}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            calls['count'] += 1
            return FakeResponse()

    monkeypatch.setattr(geocoding, 'load_json_cache', lambda name: cache)
    monkeypatch.setattr(geocoding, 'save_json_cache', lambda name, data: None)
    monkeypatch.setattr(geocoding.httpx, 'Client', FakeClient)

    first = geocoding.geocode_place('New York, NY')
    geocoding.geocode_place.cache_clear()
    second = geocoding.geocode_place('New York, NY')

    assert first == second == (-74.006, 40.7128)
    assert calls['count'] == 1


def test_get_route_uses_persistent_cache(monkeypatch):
    cache = {}
    calls = {'count': 0}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                'routes': [
                    {
                        'distance': 16093.4,
                        'duration': 900,
                        'geometry': {'type': 'LineString', 'coordinates': [[-74.0, 40.7], [-73.9, 40.8]]},
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, params=None):
            calls['count'] += 1
            return FakeResponse()

    monkeypatch.setattr(routing, 'load_json_cache', lambda name: cache)
    monkeypatch.setattr(routing, 'save_json_cache', lambda name, data: None)
    monkeypatch.setattr(routing.httpx, 'Client', FakeClient)

    first = routing.get_route((-74.0, 40.7), (-73.9, 40.8))
    second = routing.get_route((-74.0, 40.7), (-73.9, 40.8))

    assert first == second
    assert first['distance_miles'] == pytest.approx(10.0)
    assert calls['count'] == 1


def test_route_api_post_mocked(monkeypatch):
    client = APIClient()

    def fake_geocode(query):
        if 'New York' in query:
            return (-74.0060, 40.7128)
        return (-118.2437, 34.0522)

    def fake_get_route(start, finish):
        return {
            'distance_miles': 2789.4,
            'duration_seconds': 160000,
            'geometry': {'type': 'LineString', 'coordinates': [[-74.0060, 40.7128], [-118.2437, 34.0522]]},
        }

    monkeypatch.setattr('route.services.geocoding.geocode_place', fake_geocode)
    monkeypatch.setattr('route.services.routing.get_route', fake_get_route)
    monkeypatch.setattr('route.services.optimizer.optimize_fuel_stops', lambda route_points, total_distance_miles, route_stations=None: ([], 0.0))
    response = client.post('/api/v1/route/', {'start': 'New York, NY', 'finish': 'Los Angeles, CA'}, format='json')
    assert response.status_code == 200
    assert response.data['start']['name'] == 'New York, NY'
