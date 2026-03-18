# Fuel Route API

Production-ready Django API for optimizing fuel stops along US driving routes.

## Setup

1. Clone repo and create virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy env file:
   ```bash
   cp .env.example .env
   ```
3. Set your Mapbox token in `.env`:
   ```
   MAPBOX_TOKEN=pk.your_mapbox_token
   SECRET_KEY=unsafe-secret-key
   ```

## Mapbox Token

1. Sign up at https://account.mapbox.com/
2. Create an access token from your account.
3. Add to `.env` as `MAPBOX_TOKEN`.

## Fuel price data (required for good results)

The provided `fuel-prices-for-be-assessment.csv` does not include lat/lon, so the app uses a cached lookup of city/state centroids.

Build the cache once (writes `data/city_centroids.json`):

```bash
source .venv/bin/activate
python manage.py build_city_cache
```

## Run

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

Swagger UI: http://127.0.0.1:8000/api/docs/

## API

POST http://127.0.0.1:8000/api/v1/route/

Body:
```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

Example success response fields:
- `start`, `finish` details
- `total_distance_miles`
- `total_fuel_gallons`
- `total_fuel_cost_usd`
- `fuel_stops` list
- `route_geometry` GeoJSON
