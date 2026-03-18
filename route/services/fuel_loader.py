import csv
import json
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

FUEL_STATIONS = []
FUEL_STATIONS_ALL = []

CITY_COORDINATE_CACHE = {}


def _city_cache_path() -> Path:
    return Path(settings.BASE_DIR) / 'data' / 'city_centroids.json'


def _load_city_cache():
    global CITY_COORDINATE_CACHE
    path = _city_cache_path()
    if not path.exists():
        CITY_COORDINATE_CACHE = {}
        return
    try:
        CITY_COORDINATE_CACHE = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        logger.warning('Failed to read %s', path)
        CITY_COORDINATE_CACHE = {}


def _resolve_city_state_centroid(city: str, state: str):
    lookup = f"{city.strip().lower()},{state.strip().lower()}"
    if lookup in CITY_COORDINATE_CACHE:
        lon, lat = CITY_COORDINATE_CACHE[lookup]
        return (float(lon), float(lat))
    return None


def load_fuel_data():
    global FUEL_STATIONS, FUEL_STATIONS_ALL
    _load_city_cache()

    # Prefer the assessment file name, fallback to the repo copy under /data.
    csv_path = Path(settings.BASE_DIR) / 'fuel-prices-for-be-assessment.csv'
    if not csv_path.exists():
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
    logger.info(
        'Loaded %d deduped fuel stations (%d raw rows). City cache entries=%d. CSV=%s',
        len(FUEL_STATIONS),
        len(FUEL_STATIONS_ALL),
        len(CITY_COORDINATE_CACHE),
        csv_path,
    )
