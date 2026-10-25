"""Thin, defensive client for the two Elexon Insights stream endpoints we need.

FUELHH  -> half-hourly actual generation by fuel type (we keep fuelType == WIND)
WINDFOR -> wind generation forecasts, many publishTimes per target startTime
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import httpx
import pandas as pd

from .config import ELEXON_BASE


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _rows(payload) -> list[dict]:
    # Stream endpoints return a bare JSON array; non-stream endpoints wrap in {"data": [...]}.
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    return payload or []


def _get(client: httpx.Client, path: str, params: dict, retries: int = 4) -> list[dict]:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = client.get(f"{ELEXON_BASE}{path}", params=params, timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            return _rows(r.json())
        except Exception as exc:  # noqa: BLE001 - retry on any transient failure
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Elexon request failed: {path} {params}: {last}")


def _chunks(start: datetime, end: datetime, days: int):
    cur = start
    while cur < end:
        nxt = min(cur + timedelta(days=days), end)
        yield cur, nxt
        cur = nxt


def fetch_actuals(d_from: date, d_to: date) -> pd.DataFrame:
    """Actual wind generation, columns: ts (UTC), actual_mw."""
    out: list[dict] = []
    with httpx.Client() as client:
        start = datetime.combine(d_from, datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(d_to, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
        for a, b in _chunks(start, end, 7):
            params = {
                "settlementDateFrom": a.date().isoformat(),
                "settlementDateTo": (b - timedelta(days=1)).date().isoformat(),
                "fuelType": "WIND",
                "format": "json",
            }
            out.extend(_get(client, "/datasets/FUELHH/stream", params))
    df = pd.DataFrame(out)
    if df.empty:
        return pd.DataFrame(columns=["ts", "actual_mw"])
    if "fuelType" in df:  # filter client-side as well, in case the server ignored the param
        df = df[df["fuelType"].astype(str).str.upper() == "WIND"]
    df["ts"] = pd.to_datetime(df["startTime"], utc=True)
    if "publishTime" in df:
        df = df.sort_values("publishTime")
    df = df.drop_duplicates("ts", keep="last")
    df["actual_mw"] = pd.to_numeric(df["generation"], errors="coerce")
    return df.dropna(subset=["actual_mw"])[["ts", "actual_mw"]].sort_values("ts").reset_index(drop=True)


def fetch_forecasts(publish_from: date, publish_to: date) -> pd.DataFrame:
    """All wind forecast vintages published in [from, to]; columns: ts, publish, forecast_mw (UTC)."""
    start = datetime.combine(publish_from, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(publish_to, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)
    windows = list(_chunks(start, end, 2))

    def one(w):
        a, b = w
        with httpx.Client() as client:
            return _get(client, "/datasets/WINDFOR/stream",
                        {"publishDateTimeFrom": _iso(a), "publishDateTimeTo": _iso(b), "format": "json"})

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = [r for chunk in pool.map(one, windows) for r in chunk]
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["ts", "publish", "forecast_mw"])
    df["ts"] = pd.to_datetime(df["startTime"], utc=True)
    df["publish"] = pd.to_datetime(df["publishTime"], utc=True)
    df["forecast_mw"] = pd.to_numeric(df["generation"], errors="coerce")
    df = df.dropna(subset=["forecast_mw"]).drop_duplicates(["ts", "publish"], keep="last")
    return df[["ts", "publish", "forecast_mw"]].sort_values(["ts", "publish"]).reset_index(drop=True)
