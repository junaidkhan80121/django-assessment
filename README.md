# Fuel Route Optimizer

Backend assessment project built with Django and Django REST Framework. The service accepts a US start and finish location, gets a driving route from Mapbox, matches fuel price data near that route, and returns a cost-aware refueling plan.

## Project Summary

This implementation focuses on three things:

- Producing a usable route response with estimated fuel cost and recommended stops
- Keeping third-party API usage low through persistent JSON caching
- Giving reviewers a simple way to inspect results through Swagger, a browser map view, and downloadable route logs

## What The App Does

- `POST /api/v1/route/` computes a route and optimized fuel stop plan
- `GET /api/v1/route/map/` renders a browser-friendly preview of the same route
- `GET /api/v1/route/logs/` lists stored route/search/error logs and supports JSON or CSV download
- `POST /api/v1/route/logs/create/` creates a manual log entry
- `GET /api/v1/route/health/` returns a simple health response
- `GET /api/docs/` exposes the Swagger UI

## Technical Approach

### 1. Input validation

The API requires `start` and `finish` in a lightweight US format such as `Chicago, IL`.

Validation rejects:

- Blank inputs
- Identical start and finish
- Values that do not resemble `City, ST`

### 2. Geocoding and routing

The app uses Mapbox for:

- Forward geocoding of the start and finish locations
- Driving directions between those coordinates

To reduce repeated external calls, the app persists:

- `data/geocode_cache.json`
- `data/route_cache.json`

If the same request is repeated, cached results are reused instead of calling Mapbox again.

### 3. Fuel price loading

The provided assessment CSV does not contain station latitude/longitude, so the app resolves fuel data by city/state centroid.

Flow:

- Read the assessment CSV
- Resolve each unique `city,state` to coordinates
- Save those coordinates into `data/city_centroids.json`
- Load station rows into memory and keep the cheapest entry per city/state for optimization

This keeps the runtime matching simple and deterministic for the assessment dataset.

### 4. Stop optimization

The optimizer:

- Samples waypoints along the route
- Builds a corridor around the route
- Keeps only stations near that corridor
- Chooses stops with a greedy cost-minimizing strategy

Fueling assumptions from settings:

- Vehicle range: `500` miles
- Fuel economy: `10` MPG
- Tank capacity: `50` gallons
- Route corridor: `5` miles
- Waypoint interval: `25` miles

Policy:

- The trip starts with a full tank
- If a cheaper station is reachable ahead, buy only enough fuel to reach it
- Otherwise, buy enough fuel to go as far as possible toward the destination

## Architecture Notes

Key modules:

- [route/views.py](/home/khan/Desktop/backend-assessment/route/views.py) handles API endpoints, HTML views, and route logging
- [route/serializers.py](/home/khan/Desktop/backend-assessment/route/serializers.py) validates request/filter payloads and shapes responses
- [route/services/geocoding.py](/home/khan/Desktop/backend-assessment/route/services/geocoding.py) manages Mapbox geocoding plus persistent cache
- [route/services/routing.py](/home/khan/Desktop/backend-assessment/route/services/routing.py) fetches and caches route geometry
- [route/services/fuel_loader.py](/home/khan/Desktop/backend-assessment/route/services/fuel_loader.py) loads the fuel dataset and city centroid cache
- [route/services/optimizer.py](/home/khan/Desktop/backend-assessment/route/services/optimizer.py) computes the recommended stop sequence
- [route/models.py](/home/khan/Desktop/backend-assessment/route/models.py) stores search/error/manual log history

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Populate `.env` with at least:

```env
SECRET_KEY=unsafe-secret-key
MAPBOX_TOKEN=pk.your_mapbox_token
DEBUG=True
```

## Build Fuel Coordinate Cache

Run this once before using the optimizer with the assessment CSV:

```bash
source .venv/bin/activate
python manage.py build_city_cache
```

It writes `data/city_centroids.json`, which is then reused at runtime.

## Run Locally

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

Useful URLs:

- Swagger UI: `http://127.0.0.1:8000/api/docs/`
- Route API: `http://127.0.0.1:8000/api/v1/route/`
- Map preview: `http://127.0.0.1:8000/api/v1/route/map/`
- Logs/report view: `http://127.0.0.1:8000/api/v1/route/logs/`

## API Examples

### Route optimization

`POST /api/v1/route/`

Request:

```json
{
  "start": "New York, NY",
  "finish": "Los Angeles, CA"
}
```

Response fields include:

- `start`
- `finish`
- `total_distance_miles`
- `total_fuel_gallons`
- `total_fuel_cost_usd`
- `fuel_stops`
- `route_geometry`

Typical error responses:

- `400` for validation errors or infeasible routes
- `502` when Mapbox is unavailable
- `500` for unexpected server errors

### Map preview

`GET /api/v1/route/map/?start=New+York,+NY&finish=Los+Angeles,+CA`

This page renders:

- The same route computation used by the API
- A Mapbox-backed browser view
- An SVG fallback/summary preview
- Validation or upstream error messages when applicable

### Logs and report endpoints

`GET /api/v1/route/logs/`

Supports:

- JSON list response by default
- HTML report view when the browser requests `text/html`
- Date filters with `start_date` and `end_date`
- File downloads with `?download=json` or `?download=csv`

Manual log creation:

`POST /api/v1/route/logs/create/`

Example payload:

```json
{
  "category": "info",
  "source": "manual",
  "message": "Reviewer opened dashboard",
  "start": "Chicago, IL",
  "finish": "Denver, CO",
  "status_code": 200,
  "details": {
    "note": "manual log"
  }
}
```

## Testing

The automated tests cover:

- Request validation rules
- Optimizer behavior and infeasible-route handling
- Persistent cache behavior for geocoding and routing
- Route API happy path with mocked upstream services
- Map validation rendering
- Route log creation, filtering, and CSV download behavior

Run:

```bash
source .venv/bin/activate
pytest
```

## Tradeoffs And Limitations

- Fuel station coordinates are approximated from city/state centroids, not true station coordinates
- The optimizer uses a pragmatic greedy strategy rather than a global optimal search
- Location validation is intentionally lightweight and US-focused
- A real production version would likely use a stronger datastore and richer observability than SQLite plus JSON caches

## Deliverable Notes

For assessment purposes, this repo includes:

- A documented REST API
- A visual route preview for reviewers
- Persistent caching to stay within free-tier API limits
- A lightweight reporting surface through route logs and CSV/JSON export
