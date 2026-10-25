# Wind Forecast Decision Portal

Web app that helps a GB energy utility's day-ahead buying desk (1) see the wind forecast that was available at
gate closure for tomorrow's delivery day and (2) quantify how accurate that forecast has been, so the error can be
priced into the purchase decision.

**Live app:** https://kjhwr-kappa.vercel.app

> **AI assistance disclosure:** this project (code, tests, documentation and video script) was built with help from
> Claude (Anthropic), then reviewed and run by me.

## What it does

| Tab | Purpose |
|---|---|
| **Tomorrow's wind** | Pick a delivery day. Shows the half-hourly wind forecast the desk would have seen at gate closure (09:20 London time on D-1), a "prudent" ≈P90 line and 80 % range built from past errors, the later (post-gate) forecast revision, daily totals, 6-hour blocks and, once available, the actuals. |
| **Forecast accuracy** | MAE, RMSE, bias, P90/P95 error, skill vs a naive baseline; error by day, hour of day, forecast lead time and wind level; error distribution; calibration of the prudent line. |
| **Method** | Every assumption, stated plainly. |

Scope (per the brief): national GB wind only, Elexon FUELHH (actuals) + WINDFOR (forecasts); purchase decisions made in January 2026
(delivery days 2 Jan – 1 Feb 2026).

## Key design decisions

1. **"Latest forecast available at decision time"** = per target half-hour, the WINDFOR row with the greatest `publishTime ≤ 09:20 London on D-1`.
   Gate closure is configurable (`GATE_CLOSURE_LOCAL`); 09:20 is EPEX GB, N2EX is 09:50. We default to the earlier one so we never use a forecast the buyer could not have seen.
2. **No look-ahead anywhere.** Uncertainty bands for day D use errors from delivery days ≤ D-2 only.
3. **Sign convention:** error = forecast − actual; positive = over-forecast = risk of being short.
4. **Metrics chosen for the user:** MAE/RMSE/bias in MW, errors as % of mean output (not MAPE, which explodes at low wind), and a naive baseline ("same as 2 days ago", the latest fully-known day at the gate).
5. Pure analytics functions in `backend/app/analytics.py` (no I/O) → unit tested.

## Repository layout

```
backend/
  app/
    config.py      assumptions & env config (gate time, date window, data mode)
    elexon.py      Elexon Insights client (FUELHH, WINDFOR), retries + chunking
    analytics.py   decision-forecast selection, metrics, prediction bands, view builders
    store.py       loads data (snapshot | live | synthetic) and precomputes the joined table
    synthetic.py   synthetic data generator (tests / offline demo only)
    main.py        FastAPI: /api/meta, /api/decision, /api/accuracy, serves built UI
  scripts/build_snapshot.py   download Elexon data to backend/data/ (used by the deployed app)
  tests/           pytest suite
  data/            snapshot CSVs (commit these after running build_snapshot)
frontend/          React (Vite + Recharts) UI
api/index.py       Vercel serverless entrypoint
Dockerfile, docker-compose.yml, heroku.yml, vercel.json
docs/              DESIGN.md (architecture notes), VIDEO_SCRIPT.md
```

## Run it

**1. Get the data (needs internet; do this once)**

```bash
pip install -r backend/requirements-dev.txt
python -m backend.scripts.build_snapshot        # real Elexon data -> backend/data/
```
No internet? `python -m backend.scripts.build_snapshot --synthetic` creates demo data (the UI shows a red-flag banner).

**2a. Docker**

```bash
docker compose up --build        # http://localhost:8000
```

**2b. Local dev**

```bash
uvicorn backend.app.main:app --reload --port 8000
cd frontend && npm install && npm run dev      # http://localhost:5173 (proxies /api)
```

**Tests:** `python -m pytest backend/tests`

**Config (env):** `DATA_MODE` (auto|snapshot|live|synthetic), `GATE_CLOSURE_LOCAL` (default `09:20`), `DECISION_FROM`/`DECISION_TO`, `MIN_HISTORY_DAYS`.

## Deploy

* **Vercel:** import the repo; `vercel.json` builds the React app and serves FastAPI from `api/index.py`. Commit `backend/data/*` first (serverless cold starts should not call Elexon).
* **Heroku (container):** `heroku stack:set container && git push heroku main` (uses `heroku.yml` + `Dockerfile`).

## Known limitations / next steps

* National totals only; no demand, price or imbalance-cost model, so "what to buy" stays with the desk (subtract the wind line from your own demand forecast).
* Bands are unconditional empirical quantiles of ~30 days; with more history they should condition on wind level / season.
* One month of data: results describe January 2026, not the long-run skill of the forecast.
