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


def _compute_waypoints(route_points, total_distance_miles, interval=25.0):
    if not route_points:
        return []
    waypoints = []
    n = len(route_points)
    sample_count = max(2, int(math.ceil(total_distance_miles / max(interval, 1.0))) + 1)
    for i in range(sample_count):
        frac = i / max(1, sample_count - 1)
        idx = min(n - 1, int(round(frac * (n - 1))))
        coord = route_points[idx]
        mile = frac * total_distance_miles
        waypoints.append({'mile': mile, 'coord': coord})
    return waypoints


def _station_near_route(station, waypoints, corridor_miles):
    station_lon = station['lon']
    station_lat = station['lat']
    for wp in waypoints:
        wp_lon, wp_lat = wp['coord']
        dist = _haversine(wp_lon, wp_lat, station_lon, station_lat)
        if dist <= corridor_miles:
            return wp['mile']
    return None


def _route_bounds(route_points, corridor_miles):
    lons = [coord[0] for coord in route_points]
    lats = [coord[1] for coord in route_points]
    min_lat = min(lats)
    max_lat = max(lats)
    min_lon = min(lons)
    max_lon = max(lons)

    lat_padding = corridor_miles / 69.0
    avg_lat = max(1e-6, math.cos(math.radians((min_lat + max_lat) / 2.0)))
    lon_padding = corridor_miles / (69.0 * avg_lat)
    return (
        min_lon - lon_padding,
        max_lon + lon_padding,
        min_lat - lat_padding,
        max_lat + lat_padding,
    )


def _station_in_bounds(station, bounds):
    min_lon, max_lon, min_lat, max_lat = bounds
    return min_lon <= station['lon'] <= max_lon and min_lat <= station['lat'] <= max_lat


def _estimate_start_price(stations_sorted, effective_range):
    # Prefer a station close to the route origin for valuing the initial full tank.
    near_start = [station for station in stations_sorted if station['mile'] <= min(50.0, effective_range)]
    pricing_pool = near_start or [stations_sorted[0]]
    return min(pricing_pool, key=lambda station: station['price'])['price']


def optimize_fuel_stops(route_points, total_distance_miles, route_stations=None):
    if total_distance_miles <= 0:
        raise ValueError('Invalid route distance')
    corridor = settings.ROUTE_CORRIDOR_MILES
    waypoint_interval = getattr(settings, 'ROUTE_WAYPOINT_INTERVAL_MILES', 25.0)
    waypoints = _compute_waypoints(route_points, total_distance_miles, interval=waypoint_interval)
    bounds = _route_bounds(route_points, corridor)
    max_range = settings.VEHICLE_RANGE_MILES
    tank_capacity = settings.TANK_CAPACITY_GALLONS
    mpg = settings.VEHICLE_MPG

    stations = route_stations if route_stations is not None else FUEL_STATIONS
    candidate_stops = []
    for station in stations:
        if not _station_in_bounds(station, bounds):
            continue
        mile = _station_near_route(station, waypoints, corridor)
        if mile is not None:
            candidate_stops.append({**station, 'mile': mile})
    candidate_stops.sort(key=lambda s: s['mile'])

    if not candidate_stops:
        raise ValueError('No fuel price data available along the route')

    # Fueling policy (cost-minimizing):
    # At each stop, if there's a cheaper station within vehicle range ahead, buy just enough to reach it.
    # Otherwise, fill enough to go as far as possible (up to destination).
    #
    # Assumption: vehicle starts with a full tank. We only count purchases made at recommended stops.
    tank_range_miles = tank_capacity * mpg
    effective_range = min(float(max_range), float(tank_range_miles))
    if effective_range <= 0:
        raise ValueError('Invalid vehicle range configuration')

    # Ensure we include stations very near the start, and we always have a destination sentinel.
    stations_sorted = [s for s in candidate_stops if 0.0 <= s['mile'] <= total_distance_miles]
    if not stations_sorted:
        raise ValueError('No fuel price data available along the route')

    starting_price = _estimate_start_price(stations_sorted, effective_range)
    initial_gallons = min(total_distance_miles / mpg, tank_capacity)
    base_trip_cost = initial_gallons * starting_price

    position = 0.0
    fuel_gallons = float(tank_capacity)
    stops = []

    idx = 0
    while position < total_distance_miles and idx < len(stations_sorted):
        station = stations_sorted[idx]
        # Need to reach this station from current position using current fuel.
        dist_to_station = station['mile'] - position
        if dist_to_station < -1e-6:
            idx += 1
            continue

        gallons_needed = max(0.0, dist_to_station / mpg)
        if gallons_needed - fuel_gallons > 1e-9:
            raise ValueError('Route cannot be completed with available fuel stops within vehicle range')

        # Drive to station.
        position = station['mile']
        fuel_gallons -= gallons_needed

        # Find next cheaper station within range.
        reachable_miles = position + effective_range
        next_cheaper_mile = None
        j = idx + 1
        while j < len(stations_sorted) and stations_sorted[j]['mile'] <= reachable_miles + 1e-6:
            if stations_sorted[j]['price'] < station['price']:
                next_cheaper_mile = stations_sorted[j]['mile']
                break
            j += 1

        target_mile = min(total_distance_miles, reachable_miles)
        if next_cheaper_mile is not None:
            target_mile = min(target_mile, next_cheaper_mile)

        desired_gallons = max(0.0, (target_mile - position) / mpg)
        desired_gallons = min(desired_gallons, tank_capacity)
        purchase = max(0.0, desired_gallons - fuel_gallons)

        if purchase > 1e-9:
            fuel_gallons += purchase
            stops.append({
                'station_name': station['name'],
                'address': station['address'],
                'city': station['city'],
                'state': station['state'],
                'coordinates': [station['lon'], station['lat']],
                'price_per_gallon': round(station['price'], 5),
                'miles_from_start': round(position, 1),
                'gallons_purchased': round(purchase, 2),
                'cost_at_stop': round(purchase * station['price'], 2),
            })

        # If we can reach destination now, finish.
        if position + fuel_gallons * mpg >= total_distance_miles - 1e-6:
            break

        idx += 1

    if position + fuel_gallons * mpg < total_distance_miles - 1e-6:
        raise ValueError('Route cannot be completed with available fuel stops within vehicle range')

    total_cost = base_trip_cost + sum(float(stop['cost_at_stop']) for stop in stops)
    return stops, round(total_cost, 2)
