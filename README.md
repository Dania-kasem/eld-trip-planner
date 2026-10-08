# ELD Trip Planner

A full-stack app for truck drivers. Enter where the truck is, where it loads and where it unloads, plus the hours already used in the 70-hour cycle. The app returns the route, every required stop and rest, and a filled-in **Driver's Daily Log** (24-hour graph grid) for each day of the trip.

   **Live demo:** https://eld-trip-planner-gamma-ten.vercel.app | **API:** https://eld-trip-planner-api-90o1.onrender.com/api/health/ | **Video walkthrough:** add your Loom URL

> The free API host sleeps when idle. If the first calculation is slow, wait up to a minute and try again.

## What it does
- Route and turn-by-turn directions on a map (OpenStreetMap, OSRM, Nominatim; no API keys)
- Stops with type and time: pickup, drop-off, fuel, 30-minute break, 10-hour rest, 34-hour restart
- One log sheet per day, drawn as SVG on the official 4-row grid, with remarks, totals that add up to 24 hours, and the 70 hour / 8 day recap
- Print or save as PDF (always white paper, one day per page)
- Light and dark themes (system default, remembered choice)

## HOS rules implemented (FMCSA, property-carrying, 70 h / 8 days)
| Rule | Behaviour |
|---|---|
| 11-hour driving limit | Driving stops at 11 h, then a 10-hour rest |
| 14-hour window | Starts at first on-duty time; no driving after it ends |
| 30-minute break | Inserted after 8 cumulative driving hours (any 30+ minute non-driving stop counts) |
| 70 hours / 8 days | Driving stops at 70 h; a 34-hour restart is inserted |
| Fuel | At least every 1,000 miles (30 min on duty) |
| Pickup and drop-off | 1 hour on duty each |

**Assumptions:** driver starts fully rested; hours already used stay inside the 8-day window for the whole trip; 10-hour rests are logged as Sleeper Berth; no adverse driving conditions; average speed is capped at 60 mph; log days run midnight to midnight in the start location's time. The app also lists these under "Assumptions behind the plan".

## Structure
```
backend/    Django JSON API  (trips/hos.py is the pure, tested HOS engine)
frontend/   React + Vite     (SVG log sheet, Leaflet map, themes)
render.yaml Render blueprint for the API
```

## Run locally
```bash
# API  (http://127.0.0.1:8000)
cd backend
python -m venv venv && venv\Scripts\activate      # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python manage.py test trips                       # 13 tests
python manage.py runserver

# Web  (http://localhost:5173)
cd frontend
copy .env.example .env                            # macOS/Linux: cp .env.example .env
npm install
npm run dev
```

## API
`POST /api/plan-trip/`
```json
{ "current_location": "Richmond, VA", "pickup_location": "Baltimore, MD",
  "dropoff_location": "Newark, NJ", "current_cycle_used": 20, "start_time": "2026-10-05T08:00" }
```
Returns `summary`, `route` (geometry and instructions), `stops`, `logs` (per-day segments in minutes from midnight, remarks, totals) and `assumptions`. Also `GET /api/geocode/?q=` (autocomplete) and `GET /api/health/`. Full details in `backend/README.md`.

## Deploy
1. **API on Render:** New, Blueprint, pick this repo (it reads `render.yaml`). Leave `CORS_ALLOWED_ORIGINS` empty for now.
2. **Web on Vercel:** import this repo, set **Root Directory** to `frontend`, add env var `VITE_API_URL=https://<your-render-service>.onrender.com/api`.
3. Back on Render, set `CORS_ALLOWED_ORIGINS` to your Vercel URL (no trailing slash) and redeploy.
