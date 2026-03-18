import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from route.serializers import RouteRequestSerializer
from route.services.optimizer import optimize_fuel_stops


def test_request_serializer_valid():
    serializer = RouteRequestSerializer(data={'start': 'New York, NY', 'finish': 'Los Angeles, CA'})
    assert serializer.is_valid()


def test_request_serializer_invalid_blank():
    serializer = RouteRequestSerializer(data={'start': '   ', 'finish': 'Los Angeles, CA'})
    assert not serializer.is_valid()
    assert 'start' in serializer.errors


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
