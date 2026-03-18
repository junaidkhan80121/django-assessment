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

This command:

- Loads the CSV of fuel prices.
- Resolves each station’s `city, state` to a coordinate (using Mapbox once per unique city/state).
- Writes `data/city_centroids.json`, which is then used at runtime to build an in-memory list of stations with coordinates.

At request time the optimizer:

- Takes the route geometry from Mapbox Directions.
- Builds a narrow corridor (default 5 miles) around the route.
- Filters the station list to those within that corridor.
- Chooses cost-effective fuel stops subject to:
  - Max range: 500 miles
  - MPG: 10
  - Tank capacity: 50 gallons

## Run

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

Swagger UI: http://127.0.0.1:8000/api/docs/

## API

### Route optimization

**Endpoint**

- `POST /api/v1/route/`

**Request body**

```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

- Both `start` and `finish` must be **US city + state**, e.g. `"Chicago, IL"`.
- The API rejects:
  - Blank values
  - Identical start/finish
  - Inputs that do not look like `City, ST` (2-letter state).

**Behavior**

- Geocodes start and finish using Mapbox.
- Fetches a driving route using Mapbox Directions.
- Uses the supplied fuel price data to recommend cost-effective fuel stops, assuming:
  - Vehicle range: 500 miles
  - Fuel economy: 10 miles per gallon
  - Tank capacity: 50 gallons
- Results are cached on disk so **repeated requests for the same route do not hit Mapbox again**, keeping usage within free-tier limits.

**Example success response fields**

- `start`, `finish` details
- `total_distance_miles`
- `total_fuel_gallons`
- `total_fuel_cost_usd`
- `fuel_stops` list
- `route_geometry` GeoJSON

**Error responses**

- `400 Bad Request` – validation or routing/optimizer issues:
  - `{"error": "Validation failed", "details": {...}}`
  - `{"error": "Invalid or unsupported route", "details": {"message": ["No fuel price data available along the route"]}}`
- `502 Bad Gateway` – Mapbox is unreachable or times out:
  - `{"error": "Upstream mapping service temporarily unavailable", "details": {"message": ["Mapbox ..."]}}`
- `500 Internal Server Error` – unexpected issues on the server.

### Map preview

- `GET /api/v1/route/map/?start=New+York,+NY&finish=Los+Angeles,+CA`
- Renders an HTML page that:
  - Calls the same internal logic as the API to compute the route and fuel stops.
  - Shows a simple SVG preview of the route and stop locations.

This is primarily for evaluators to **visually inspect** a route produced by the API.
