import math
from django.conf import settings
from .fuel_loader import FUEL_STATIONS


def _haversine(lon1, lat1, lon2, lat2):
    r = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return r * c


def _compute_waypoints(route_points, total_distance_miles, interval=10.0):
    if not route_points:
        return []
    waypoints = []
    n = len(route_points)
    for i, coord in enumerate(route_points):
        frac = i / max(1, n - 1)
        mile = frac * total_distance_miles
        waypoints.append({'mile': mile, 'coord': coord})
    return waypoints


def _station_near_route(station, waypoints, corridor_miles):
    station_lon = station['lon']
    station_lat = station['lat']
    nearest = None
    min_mile = None
    for wp in waypoints:
        wp_lon, wp_lat = wp['coord']
        dist = _haversine(wp_lon, wp_lat, station_lon, station_lat)
        if dist <= corridor_miles:
            if min_mile is None or wp['mile'] < min_mile:
                min_mile = wp['mile']
                nearest = dist
    return min_mile


def optimize_fuel_stops(route_points, total_distance_miles, route_stations=None):
    if total_distance_miles <= 0:
        raise ValueError('Invalid route distance')
    waypoints = _compute_waypoints(route_points, total_distance_miles)
    corridor = settings.ROUTE_CORRIDOR_MILES
    safety = settings.SAFETY_BUFFER_MILES
    max_range = settings.VEHICLE_RANGE_MILES
    tank_capacity = settings.TANK_CAPACITY_GALLONS

    stations = route_stations if route_stations is not None else FUEL_STATIONS
    candidate_stops = []
    for station in stations:
        mile = _station_near_route(station, waypoints, corridor)
        if mile is not None:
            candidate_stops.append({**station, 'mile': mile})
    candidate_stops.sort(key=lambda s: s['mile'])

    if not candidate_stops:
        # no station near route; return empty stops and zero cost as fallback
        return [], 0.0

    remaining = max_range
    current_mile = 0.0
    stops = []
    while current_mile + remaining < total_distance_miles:
        window_start = current_mile + max(0, remaining - safety)
        window_end = min(current_mile + remaining, total_distance_miles)
        allowed = [s for s in candidate_stops if s['mile'] > current_mile and window_start <= s['mile'] <= window_end]
        if not allowed:
            fallback = [s for s in candidate_stops if s['mile'] > current_mile and s['mile'] <= current_mile + remaining]
            if not fallback:
                break
            cheapest = min(fallback, key=lambda s: s['price'])
        else:
            cheapest = min(allowed, key=lambda s: s['price'])

        if cheapest['mile'] <= current_mile:
            break

        current_mile = cheapest['mile']
        remaining = max_range
        gallons_purchased = tank_capacity
        stops.append({
            'station_name': cheapest['name'],
            'address': cheapest['address'],
            'city': cheapest['city'],
            'state': cheapest['state'],
            'coordinates': [cheapest['lon'], cheapest['lat']],
            'price_per_gallon': round(cheapest['price'], 5),
            'miles_from_start': round(current_mile, 1),
            'gallons_purchased': round(gallons_purchased, 2),
            'cost_at_stop': round(gallons_purchased * cheapest['price'], 2),
        })

    total_cost = sum(stop['cost_at_stop'] for stop in stops)
    return stops, round(total_cost, 2)
