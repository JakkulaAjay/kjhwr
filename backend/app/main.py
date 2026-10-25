"""FastAPI entrypoint. API under /api; built React app (if present) is served at /."""
from __future__ import annotations

import math
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from . import analytics, config
from .store import store

app = FastAPI(title="Wind Forecast Decision Portal", version="1.0.0")


def clean(o):
    """Recursively turn NaN/inf into None so responses are valid JSON."""
    if isinstance(o, float):
        return None if math.isnan(o) or math.isinf(o) else o
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def ensure_loaded() -> None:
    try:
        store.load()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"Data not available: {exc}") from exc


def parse_date(s: str, name: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as exc:
        raise HTTPException(422, f"{name} must be YYYY-MM-DD") from exc


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    ensure_loaded()
    lo, hi = store.delivery_range()
    return clean({
        "source": store.meta.get("source"),
        "fetched_at": store.meta.get("fetched_at"),
        "gate_closure_local": config.GATE_CLOSURE.strftime("%H:%M"),
        "timezone": "Europe/London",
        "decision_from": config.DECISION_FROM.isoformat(), "decision_to": config.DECISION_TO.isoformat(),
        "delivery_from": lo.isoformat(), "delivery_to": hi.isoformat(),
        "delivery_dates": store.available_delivery_dates(),
        "rows": {"actuals": len(store.actuals), "forecasts": len(store.forecasts)},
    })


@app.get("/api/decision")
def decision(delivery_date: str = Query(..., description="YYYY-MM-DD delivery day")):
    ensure_loaded()
    d = parse_date(delivery_date, "delivery_date")
    lo, hi = store.delivery_range()
    if not (lo <= d <= hi):
        raise HTTPException(404, f"delivery_date must be within {lo} .. {hi}")
    return clean(analytics.decision_view(store.joined, d, config.GATE_CLOSURE))


@app.get("/api/accuracy")
def accuracy(date_from: str | None = None, date_to: str | None = None):
    ensure_loaded()
    lo, hi = store.delivery_range()
    a = parse_date(date_from, "date_from") if date_from else lo
    b = parse_date(date_to, "date_to") if date_to else hi
    if a > b:
        raise HTTPException(422, "date_from must be <= date_to")
    # horizon table is computed on the full range at load time; accuracy is filtered by day range.
    return clean(analytics.accuracy_view(store.joined, store.horizon, a, b))


if config.STATIC_DIR.exists():  # registered last so /api/* routes win
    app.mount("/", StaticFiles(directory=config.STATIC_DIR, html=True), name="static")
