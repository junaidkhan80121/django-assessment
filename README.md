# Fuel Route Optimizer

Backend assessment project built with Django and Django REST Framework. The service accepts a US start and finish location, retrieves a driving route from Mapbox, matches fuel price data near that route, and returns a cost-aware refueling plan.

---

## Project Summary

This implementation focuses on three key goals:

- Producing a usable route response with estimated fuel cost and recommended stops  
- Keeping third-party API usage low through persistent JSON caching (prebuilt and ready to use)  
- Providing reviewers with easy inspection tools via Swagger, a browser map view, and downloadable route logs  

---

## What The App Does

- `POST /api/v1/route/` → Computes a route and optimized fuel stop plan  
- `GET /api/v1/route/map/` → Renders a browser-friendly preview of the route  
- `GET /api/v1/route/logs/` → Lists stored route/search/error logs with JSON or CSV download  
- `POST /api/v1/route/logs/create/` → Creates a manual log entry  
- `GET /api/v1/route/health/` → Health check endpoint  
- `GET /api/docs/` → Swagger UI  

---

## Technical Approach

### 1. Input Validation

The API expects:

```
City, ST
```

Example: `Chicago, IL`

Validation rejects:

- Blank inputs  
- Identical start and finish  
- Improperly formatted locations  

---

### 2. Geocoding and Routing

The app uses Mapbox for:

- Forward geocoding  
- Driving directions  

To improve performance and reduce API usage, results are cached locally:

- `data/geocode_cache.json`  
- `data/route_cache.json`  

If a request is repeated, cached data is reused instead of calling Mapbox again.

---

### 3. Fuel price loading

The provided assessment CSV does not contain station latitude/longitude, so the app resolves fuel data by city/state centroid.

Flow:

- Load precomputed city/state coordinates from `data/city_centroids.json`  
- Load station rows into memory and keep the cheapest entry per city/state for optimization  

The coordinate cache is already built and included in the project, so no preprocessing step is required. This keeps runtime fast and deterministic.

---

### 4. Stop optimization

The optimizer:

- Samples waypoints along the route  
- Builds a corridor around the route  
- Keeps only stations near that corridor  
- Chooses stops with a greedy cost-minimizing strategy  

#### Assumptions

- Vehicle range: `500` miles  
- Fuel economy: `10` MPG  
- Tank capacity: `50` gallons  
- Route corridor: `5` miles  
- Waypoint interval: `25` miles  

#### Policy

- The trip starts with a full tank  
- If a cheaper station is reachable ahead, buy only enough fuel to reach it  
- Otherwise, buy enough fuel to go as far as possible toward the destination  

---

## Architecture Notes

Key modules:

- `route/views.py` → API endpoints, HTML views, and route logging  
- `route/serializers.py` → Request validation and response shaping  
- `route/services/geocoding.py` → Mapbox geocoding plus persistent cache  
- `route/services/routing.py` → Fetches and caches route geometry  
- `route/services/fuel_loader.py` → Loads fuel dataset and centroid cache  
- `route/services/optimizer.py` → Computes recommended stop sequence  
- `route/models.py` → Stores search/error/manual log history  

---

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Populate `.env` with:

```env
SECRET_KEY=unsafe-secret-key
MAPBOX_TOKEN=pk.your_mapbox_token
DEBUG=True
```

Note: Required caches are already included in the repository, so no additional data preparation steps are needed.

---

## Run Locally

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py runserver
```

---

## Useful URLs

- Swagger UI: `http://127.0.0.1:8000/api/docs/`  
- Route API: `http://127.0.0.1:8000/api/v1/route/`  
- Map preview: `http://127.0.0.1:8000/api/v1/route/map/`  
- Logs/report view: `http://127.0.0.1:8000/api/v1/route/logs/`  

---

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

### Errors

- `400` → Validation errors or infeasible routes  
- `502` → Mapbox unavailable  
- `500` → Unexpected server errors  

---

### Map preview

`GET /api/v1/route/map/?start=New+York,+NY&finish=Los+Angeles,+CA`

This page renders:

- Route computation  
- Mapbox-backed browser view  
- SVG fallback preview  
- Validation or upstream error messages  

---

### Logs and report endpoints

`GET /api/v1/route/logs/`

Supports:

- JSON list response  
- HTML report view  
- Date filters (`start_date`, `end_date`)  
- File downloads (`?download=json` or `?download=csv`)  

---

### Manual log creation

`POST /api/v1/route/logs/create/`

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

---

## Testing

Run:

```bash
pytest
```

Covers:

- Validation rules  
- Optimizer behavior  
- Cache reuse  
- API happy path  
- Map rendering  
- Logging and CSV export  

---

## Tradeoffs And Limitations

- Fuel station coordinates are approximated using city/state centroids  
- Greedy optimization instead of global optimal search  
- Lightweight US-only validation  
- SQLite + JSON cache instead of production-grade datastore  

---

## Deliverable Notes

- Documented REST API  
- Interactive Swagger UI  
- Visual route preview  
- Persistent caching for performance and API efficiency  
- Lightweight reporting via logs and CSV/JSON export  
