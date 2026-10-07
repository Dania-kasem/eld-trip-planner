# ELD Trip Planner – React frontend

Vite + React 18 + Leaflet. No UI framework: theming is plain CSS variables.

## Run
```bash
cp .env.example .env      # set VITE_API_URL to your Django API (…/api)
npm install
npm run dev               # http://localhost:5173
npm run build             # static files in dist/
```

## Deploy (Vercel)
Import the repo, framework preset "Vite", add env var `VITE_API_URL=https://<your-api>/api`.
Then add the Vercel URL to `CORS_ALLOWED_ORIGINS` on the backend.

## Structure
* `src/App.jsx` – state and layout (CSS grid areas: form, summary, map, stops, log)
* `src/components/TripForm.jsx` – autocomplete inputs, cycle-hours gauge, optional log details
* `src/components/MapView.jsx` – Leaflet map, theme-aware tiles, typed markers, fly-to
* `src/components/Stops.jsx` – stop timeline and turn-by-turn directions
* `src/components/LogSheet.jsx` – the daily log drawn as SVG (grid, status line, remarks, totals, recap)
* `src/components/LogViewer.jsx` – day tabs and print
* `src/styles.css` – all colors live in variables at the top (`:root` light, `[data-theme="dark"]`)

## Themes
Follows the system setting on first visit; the header button overrides it and is remembered.
Text pairs are at least 4.5:1 and lines/borders at least 3:1 in both themes.
Printing always uses the light, white-paper version of the log.
