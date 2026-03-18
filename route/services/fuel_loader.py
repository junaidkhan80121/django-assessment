import csv
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

FUEL_STATIONS = []
FUEL_STATIONS_ALL = []

CITY_COORDINATE_CACHE = {
    'new york,ny': (-74.0060, 40.7128),
    'los angeles,ca': (-118.2437, 34.0522),
    'chicago,il': (-87.6298, 41.8781),
    'houston,tx': (-95.3698, 29.7604),
    'philadelphia,pa': (-75.1652, 39.9526),
    'phoenix,az': (-112.0740, 33.4484),
    'san antonio,tx': (-98.4936, 29.4241),
    'san diego,ca': (-117.1611, 32.7157),
    'dallas,tx': (-96.7970, 32.7767),
    'san jose,ca': (-121.8863, 37.3382),
}


def _resolve_city_state_centroid(city: str, state: str):
    lookup = f"{city.strip().lower()},{state.strip().lower()}"
    if lookup in CITY_COORDINATE_CACHE:
        return CITY_COORDINATE_CACHE[lookup]
    return None


def load_fuel_data():
    global FUEL_STATIONS, FUEL_STATIONS_ALL
    csv_path = Path(settings.BASE_DIR) / 'data' / 'fuel_prices.csv'
    if not csv_path.exists():
        logger.warning('Fuel CSV not found at %s', csv_path)
        FUEL_STATIONS = []
        FUEL_STATIONS_ALL = []
        return

    raw_rows = []
    with csv_path.open(newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            city = (row.get('City') or '').strip()
            state = (row.get('State') or '').strip()
            name = (row.get('Truckstop Name') or '').strip()
            address = (row.get('Address') or '').strip()
            retail = (row.get('Retail Price') or '').strip()
            if not city or not state or not retail:
                continue
            try:
                price = float(retail)
                if price <= 0:
                    continue
            except ValueError:
                continue
            coords = _resolve_city_state_centroid(city, state)
            if coords is None:
                continue
            raw_rows.append({
                'name': name or row.get('OPIS Truckstop ID', '').strip(),
                'address': address,
                'city': city,
                'state': state,
                'lat': coords[1],
                'lon': coords[0],
                'price': round(price, 3),
            })

    deduped = {}
    for row in raw_rows:
        key = (row['city'].lower(), row['state'].lower())
        existing = deduped.get(key)
        if existing is None or row['price'] < existing['price']:
            deduped[key] = row

    FUEL_STATIONS_ALL = raw_rows
    FUEL_STATIONS = list(deduped.values())
    logger.info('Loaded %d fuel stations', len(FUEL_STATIONS))
