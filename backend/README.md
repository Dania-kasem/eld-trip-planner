# ELD Trip Planner – Django backend

Stateless JSON API. Takes trip details, returns the route, stops/rests, and
ready-to-draw daily ELD log sheets (FMCSA HOS rules, property carrier, 70 h / 8 days).

## Run locally
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py runserver        # http://127.0.0.1:8000/api/
python manage.py test trips       # 13 tests
```

## Endpoints
### `POST /api/plan-trip/`
```json
{
  "current_location": "Richmond, VA",
  "pickup_location": "Baltimore, MD",
  "dropoff_location": "Newark, NJ",
  "current_cycle_used": 20,
  "start_time": "2026-10-05T08:00"
}
```
Locations can be a string (geocoded with Nominatim) or `{"lat":..,"lng":..,"label":".."}`
(use this when the user picked an autocomplete suggestion). `start_time` is optional
(default: today 08:00). `current_cycle_used` is 0–70.

Response keys: `summary`, `waypoints`, `route.geometry` ([lat,lng] list for Leaflet),
`route.instructions`, `stops[]` (pickup / dropoff / fuel / break / rest / restart with
lat, lng, start, end, location), `logs[]`, `assumptions[]`.

Each entry in `logs[]` is one 24 h sheet:
```json
{
  "date": "2026-10-05", "day_number": 1, "total_miles_driving": 605.0,
  "segments": [{"status": "driving", "start_minute": 480, "end_minute": 807,
                "location": "Richmond, VA", "note": "Driving", "miles": 300.0}],
  "remarks": [{"minute": 480, "status": "driving", "location": "Richmond, VA", "note": "Driving"}],
  "totals_hours": {"off_duty": 8.0, "sleeper": 4.0, "driving": 11.0, "on_duty": 1.0}
}
```
`status` is one of `off_duty | sleeper | driving | on_duty`; minutes are 0–1440 from
midnight, segments are contiguous and the four totals always add up to 24.
Draw each segment as a horizontal line on its status row and connect consecutive
segments with vertical lines.

### `GET /api/geocode/?q=richmond` – up to 5 autocomplete suggestions
### `GET /api/health/`

## Code map
* `trips/hos.py` – pure HOS simulation + daily log builder (the core logic, fully tested)
* `trips/routing.py` – Nominatim + OSRM clients, position-along-route helper
* `trips/views.py` – validation and response assembly

## Deploy (Render / Railway)
* Build: `pip install -r requirements.txt` · Start: `gunicorn config.wsgi --timeout 90` (see `Procfile`)
* Env vars: `SECRET_KEY`, `DEBUG=false`, `ALLOWED_HOSTS=your-api.onrender.com`,
  `CORS_ALLOWED_ORIGINS=https://your-app.vercel.app`
* Optional: `REVERSE_GEOCODE=false` to skip city names for stops (faster),
  `REVERSE_GEOCODE_BUDGET=20` (seconds), `OSRM_URL`, `NOMINATIM_URL`, `HTTP_USER_AGENT`.

## Notes
* Nominatim allows 1 request/second, so city names for stops are looked up sequentially within a
  time budget; anything beyond it falls back to coordinates. Self-host or swap the provider for production.
* The public OSRM server is car-based; speed is capped at 60 mph average to approximate a truck.
