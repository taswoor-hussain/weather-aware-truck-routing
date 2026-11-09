# Weather-Aware Truck Routing

A React + Django app that helps a truck driver choose the safest route. It compares three truck routes using the forecast at the time the truck will actually reach each checkpoint, the load weight, and the travel time.

**Live app:** LIVE_URL_PLACEHOLDER
**Walkthrough:** LOOM_URL_PLACEHOLDER

## What it does

1. The driver enters an origin, destination, departure time and load weight.
2. TomTom returns three distinct truck routes.
3. Each route gets a checkpoint every 10, 25 or 50 miles (selectable), plus the origin and destination.
4. Each checkpoint is scored with the forecast for its own ETA, not the departure time.
5. The routes are ranked and the best one is recommended.
6. The map shows all routes, checkpoints, risk levels, ETAs and route summaries, with a 0–48 hour corridor heatmap.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | React, TypeScript, Vite | Requested stack, typed API contract |
| Map | MapLibre GL, OpenFreeMap tiles | GPU rendering, no map key |
| Backend | Django, Django REST Framework | Requested stack, declarative validation |
| Routing and place search | TomTom | Real truck routing that accepts vehicle weight |
| Weather | Open-Meteo | Free hourly forecasts for many locations in one request |

## Project layout

```
backend/planner/services/
  risk.py            Risk thresholds and load rules (pure functions)
  recommendation.py  Route scoring and ranking (pure functions)
  checkpoints.py     Checkpoint placement, ETAs, miles per checkpoint
  corridor.py        Heatmap grid around the routes
  routing.py         TomTom client, guarantees three distinct routes
  weather.py         Open-Meteo client, batching and caching
  planner.py         Orchestrates the above into the API response
frontend/src/components/
  RouteMap.tsx       MapLibre layers, popups and route labels
  ForecastSlider.tsx 0–48 hour slider and playback
  MapPanel.tsx       Holds slider state, isolated from the sidebar
  TripForm, PlaceInput, RouteList
```

## Risk rules

Each checkpoint takes the worst level across wind (after load rules), rain and snow.

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
| Rain (in/hr) | <0.10 | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow (in/hr) | <0.5 | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

Load rules: 45–54 mph with more than 30,000 lb is No Travel, and 35–44 mph with more than 40,000 lb is Severe.

### Decisions where the brief leaves room

- **Shared band edges:** rain and snow bands include their upper limit. The table's `<0.10` (Low) and `>1.00` (No Travel) require 0.10 to be Moderate and 1.00 to be Severe, and only upper-inclusive bands satisfy both.
- **Wind:** sustained 10 m wind speed, not gusts. Whole-mph bands extend to the next band, so 44.6 mph is still "35–44".
- **Timing:** wind is interpolated between hours. Rain and snow are hourly totals for the preceding hour, so a checkpoint uses the hour that ends at or after its ETA.

## Recommendation

Routes are compared in strict priority order:

1. Fewest No Travel miles (added: a forbidden route must never beat a merely risky one)
2. Fewest Severe miles
3. Fewest High miles
4. Lowest average risk (mile-weighted, Low = 0 to No Travel = 4)
5. Shortest travel time

Each checkpoint represents half of the road on either side of it, so its miles always add up to the exact route length. Miles are compared to the nearest mile and average risk to two decimals, so sampling noise cannot override a real difference in a lower-priority criterion. If every route crosses No Travel conditions, the app tells the driver not to depart.

## Heatmap performance

- All 49 hourly frames arrive once, stored as properties on a single GeoJSON source of at most about 170 cells.
- Moving the slider changes one paint expression. It does not call the API, rebuild data or re-render React outside the map panel.
- The expression blends adjacent hours, so playback moves continuously instead of stepping.
- Colors change hue only at a risk boundary, so a heatmap color always matches the checkpoint level. Shading inside a level shows how close conditions are to the next one.

## Run locally

Requires Python 3.10+, Node 20+ and a free [TomTom key](https://developer.tomtom.com/).

```bash
# Backend, on port 8000
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then add your TOMTOM_API_KEY
python manage.py runserver

# Frontend, on port 5173, in a second terminal
cd frontend
npm install
npm run dev
```

Run the tests with `python manage.py test planner` from `backend/`.

## Deployment

The `Dockerfile` builds React and serves it from Django with WhiteNoise, as one service. Set `TOMTOM_API_KEY` and `DJANGO_SECRET_KEY`.

## Known limitations

- ETAs assume continuous driving and do not include mandatory driver rest breaks. Long trips would arrive later than shown.
- The forecast cache is in memory and clears on restart.
- Open-Meteo's free tier allows 600 location lookups per minute. Each plan uses at most 300, and results are cached for 30 minutes. A production deployment would need a paid key.
- Coverage is limited to the US, Canada and Mexico, in miles and pounds.
