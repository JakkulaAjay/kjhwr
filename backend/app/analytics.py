"""Pure functions (no I/O) so they are easy to unit test.

Conventions
-----------
* All timestamps are tz-aware UTC; "delivery date" is the Europe/London calendar date of the target half-hour.
* error = forecast - actual.  Positive => over-forecast => the buyer under-procures thermal/market power
  and is exposed to being short.  Negative => under-forecast => over-procurement (long).
* The *decision forecast* for a target half-hour is the latest WINDFOR vintage with
  publishTime <= gate closure on the day before delivery.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Callable

import numpy as np
import pandas as pd

from .config import BAND_LAG_DAYS, LONDON, MIN_HISTORY_DAYS

HALF_HOUR_H = 0.5
NAIVE_LAG = pd.Timedelta(hours=48)  # last fully-known actuals at gate closure are two days old


# ----------------------------------------------------------------------------- time helpers
def local_midnight_utc(d: date) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(d, time(0, 0), tzinfo=LONDON)).tz_convert("UTC")


def gate_time_utc(delivery_date: date, gate: time) -> pd.Timestamp:
    """Gate closure instant (UTC) for deliveries on `delivery_date` = D-1 at `gate` London time."""
    d = delivery_date - timedelta(days=1)
    return pd.Timestamp(datetime.combine(d, gate, tzinfo=LONDON)).tz_convert("UTC")


def delivery_dates(ts: pd.Series) -> pd.Series:
    return ts.dt.tz_convert(LONDON).dt.date


# ----------------------------------------------------------------------------- forecast selection
def forecast_as_of(forecasts: pd.DataFrame, cutoff_for: Callable[[date], pd.Timestamp]) -> pd.DataFrame:
    """For every target `ts`, keep the latest vintage published at or before cutoff_for(delivery_date)."""
    f = forecasts.copy()
    f["delivery_date"] = delivery_dates(f["ts"])
    cutoffs = {d: cutoff_for(d) for d in f["delivery_date"].unique()}
    f = f[f["publish"] <= f["delivery_date"].map(cutoffs)]
    f = f.sort_values(["ts", "publish"]).drop_duplicates("ts", keep="last")
    return f.reset_index(drop=True)


# ----------------------------------------------------------------------------- metrics
def compute_metrics(df: pd.DataFrame) -> dict:
    d = df.dropna(subset=["actual_mw", "forecast_mw"])
    n = len(d)
    if n == 0:
        return {"n": 0}
    err = (d["forecast_mw"] - d["actual_mw"]).to_numpy()
    ae = np.abs(err)
    mean_actual = float(d["actual_mw"].mean())
    out = {
        "n": int(n),
        "mae": float(ae.mean()),
        "rmse": float(np.sqrt((err ** 2).mean())),
        "bias": float(err.mean()),
        "mean_actual": mean_actual,
        "mean_forecast": float(d["forecast_mw"].mean()),
        # MAE as % of mean actual output (== WAPE). MAPE is avoided: it explodes in calm periods.
        "nmae_pct": float(ae.mean() / mean_actual * 100) if mean_actual > 0 else None,
        "p50_abs": float(np.percentile(ae, 50)),
        "p90_abs": float(np.percentile(ae, 90)),
        "p95_abs": float(np.percentile(ae, 95)),
        "over_forecast_pct": float((err > 0).mean() * 100),
        "max_over": float(err.max()),
        "max_under": float(err.min()),
    }
    if "naive_mw" in d:
        nv = d.dropna(subset=["naive_mw"])
        if len(nv):
            mae_f = float(np.abs(nv["forecast_mw"] - nv["actual_mw"]).mean())
            mae_n = float(np.abs(nv["naive_mw"] - nv["actual_mw"]).mean())
            out["naive_mae"] = mae_n
            out["skill_vs_naive_pct"] = float((1 - mae_f / mae_n) * 100) if mae_n > 0 else None
    return out


# ----------------------------------------------------------------------------- joined table
def add_rolling_bands(j: pd.DataFrame) -> pd.DataFrame:
    """Empirical 10th/90th error quantiles per delivery day, using ONLY days <= D - BAND_LAG_DAYS.

    prudent_mw = wind we can count on with ~90% confidence  = forecast - q90(error)
    upper_mw   = wind exceeded only ~10% of the time        = forecast - q10(error)
    """
    j = j.copy()
    j["q10"] = np.nan
    j["q90"] = np.nan
    j["history_days"] = 0
    for d in sorted(j["delivery_date"].unique()):
        hist = j[(j["delivery_date"] <= d - timedelta(days=BAND_LAG_DAYS)) & j["error"].notna()]
        days = hist["delivery_date"].nunique()
        mask = j["delivery_date"] == d
        j.loc[mask, "history_days"] = days
        if days >= MIN_HISTORY_DAYS:
            j.loc[mask, "q10"] = np.percentile(hist["error"], 10)
            j.loc[mask, "q90"] = np.percentile(hist["error"], 90)
    j["prudent_mw"] = (j["forecast_mw"] - j["q90"]).clip(lower=0)
    j["upper_mw"] = (j["forecast_mw"] - j["q10"]).clip(lower=0)
    return j


def build_joined(actuals: pd.DataFrame, forecasts: pd.DataFrame, gate: time,
                 d_from: date, d_to: date) -> pd.DataFrame:
    """One row per target half-hour: decision forecast, latest pre-delivery forecast, actual, errors, bands."""
    dec = forecast_as_of(forecasts, lambda d: gate_time_utc(d, gate))
    dec = dec[(dec["delivery_date"] >= d_from + timedelta(days=1)) & (dec["delivery_date"] <= d_to + timedelta(days=1))]
    dec["horizon_h"] = (dec["ts"] - dec["publish"]) / pd.Timedelta(hours=1)

    late = forecast_as_of(forecasts, local_midnight_utc)[["ts", "publish", "forecast_mw"]]
    late = late.rename(columns={"publish": "latest_publish", "forecast_mw": "latest_mw"})

    j = dec.merge(actuals, on="ts", how="left").merge(late, on="ts", how="left")
    a_idx = actuals.set_index("ts")["actual_mw"]
    j["naive_mw"] = (j["ts"] - NAIVE_LAG).map(a_idx)
    j["error"] = j["forecast_mw"] - j["actual_mw"]
    j["hour"] = j["ts"].dt.tz_convert(LONDON).dt.hour
    return add_rolling_bands(j.sort_values("ts").reset_index(drop=True))


def horizon_table(actuals: pd.DataFrame, forecasts: pd.DataFrame, d_from: date, d_to: date) -> list[dict]:
    """Accuracy by forecast lead time using EVERY vintage (shows how quickly error grows with horizon)."""
    f = forecasts.copy()
    f["delivery_date"] = delivery_dates(f["ts"])
    f = f[(f["delivery_date"] >= d_from + timedelta(days=1)) & (f["delivery_date"] <= d_to + timedelta(days=1))]
    f = f.merge(actuals, on="ts", how="inner")
    f["horizon_h"] = (f["ts"] - f["publish"]) / pd.Timedelta(hours=1)
    f = f[f["horizon_h"] >= 0]
    edges = [0, 6, 12, 18, 24, 30, 36, 42, 48, np.inf]
    labels = ["0-6h", "6-12h", "12-18h", "18-24h", "24-30h", "30-36h", "36-42h", "42-48h", "48h+"]
    f["bucket"] = pd.cut(f["horizon_h"], edges, labels=labels, right=False)
    rows = []
    for lab in labels:
        g = f[f["bucket"] == lab]
        if len(g) == 0:
            continue
        e = g["forecast_mw"] - g["actual_mw"]
        rows.append({"bucket": lab, "n": int(len(g)), "mae": float(e.abs().mean()),
                     "rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean())})
    return rows


# ----------------------------------------------------------------------------- views
def _group_metrics(df: pd.DataFrame, key: str) -> list[dict]:
    rows = []
    for k, g in df.groupby(key, sort=True):
        m = compute_metrics(g)
        if m["n"]:
            rows.append({key: k if not isinstance(k, (np.integer,)) else int(k), **m})
    return rows


def accuracy_view(j: pd.DataFrame, horizon_rows: list[dict], d_from: date, d_to: date) -> dict:
    sel = j[(j["delivery_date"] >= d_from) & (j["delivery_date"] <= d_to)]
    scored = sel.dropna(subset=["actual_mw"]).copy()
    by_day = _group_metrics(scored, "delivery_date")
    for r in by_day:
        r["delivery_date"] = r["delivery_date"].isoformat()
    by_hour = _group_metrics(scored, "hour")

    bins = [0, 2000, 4000, 6000, 8000, 10000, 12000, np.inf]
    labs = ["<2 GW", "2-4 GW", "4-6 GW", "6-8 GW", "8-10 GW", "10-12 GW", ">12 GW"]
    scored["level"] = pd.cut(scored["forecast_mw"], bins, labels=labs, right=False)
    by_level = []
    for lab in labs:
        g = scored[scored["level"] == lab]
        if len(g):
            by_level.append({"level": lab, **compute_metrics(g)})

    hist = []
    if len(scored):
        lim = float(np.ceil(np.percentile(np.abs(scored["error"]), 99) / 500) * 500) or 500.0
        counts, edges = np.histogram(scored["error"].clip(-lim, lim), bins=np.linspace(-lim, lim, 21))
        hist = [{"from": float(edges[i]), "to": float(edges[i + 1]), "count": int(c)} for i, c in enumerate(counts)]

    banded = scored.dropna(subset=["q10", "q90"])
    calib = None
    if len(banded):
        calib = {
            "n": int(len(banded)),
            "prudent_hit_pct": float((banded["actual_mw"] >= banded["prudent_mw"]).mean() * 100),
            "inside_80_band_pct": float(((banded["actual_mw"] >= banded["prudent_mw"]) &
                                         (banded["actual_mw"] <= banded["upper_mw"])).mean() * 100),
        }
    return {
        "from": d_from.isoformat(), "to": d_to.isoformat(),
        "overall": compute_metrics(scored),
        "median_decision_horizon_h": float(sel["horizon_h"].median()) if len(sel) else None,
        "by_day": by_day, "by_hour": by_hour, "by_level": by_level,
        "histogram": hist, "by_horizon": horizon_rows, "calibration": calib,
    }


def decision_view(j: pd.DataFrame, delivery_date: date, gate: time) -> dict:
    start, end = local_midnight_utc(delivery_date), local_midnight_utc(delivery_date + timedelta(days=1))
    day = j[(j["ts"] >= start) & (j["ts"] < end)]
    decision_ts = gate_time_utc(delivery_date, gate)
    # WINDFOR targets can be hourly or half-hourly: use the data's own resolution for energy and coverage.
    step_min = float(day["ts"].sort_values().diff().dropna().median() / pd.Timedelta(minutes=1)) if len(day) > 1 else 30.0
    step_h = step_min / 60.0
    expected = int(round((end - start) / pd.Timedelta(minutes=step_min)))
    if day.empty:
        return {"delivery_date": delivery_date.isoformat(), "decision_time": decision_ts.isoformat(),
                "points": [], "summary": {"coverage_pct": 0.0, "expected_points": expected}}

    pts = []
    for r in day.itertuples():
        pts.append({
            "ts": r.ts.isoformat(), "forecast_mw": r.forecast_mw, "publish": r.publish.isoformat(),
            "latest_mw": None if pd.isna(r.latest_mw) else r.latest_mw,
            "actual_mw": None if pd.isna(r.actual_mw) else r.actual_mw,
            "prudent_mw": None if pd.isna(r.prudent_mw) else r.prudent_mw,
            "upper_mw": None if pd.isna(r.upper_mw) else r.upper_mw,
        })

    local = day["ts"].dt.tz_convert(LONDON).dt.hour
    blocks = []
    for lo, hi in [(0, 6), (6, 12), (12, 18), (18, 24)]:
        g = day[(local >= lo) & (local < hi)]
        if g.empty:
            continue
        blocks.append({
            "label": f"{lo:02d}:00-{hi % 24:02d}:00",
            "forecast_mw": float(g["forecast_mw"].mean()),
            "prudent_mw": None if g["prudent_mw"].isna().all() else float(g["prudent_mw"].mean()),
            "actual_mw": None if g["actual_mw"].isna().all() else float(g["actual_mw"].mean()),
        })

    peak = day.loc[day["forecast_mw"].idxmax()]
    low = day.loc[day["forecast_mw"].idxmin()]
    newest = day["publish"].max()
    summary = {
        "coverage_pct": float(len(day) / expected * 100), "expected_points": expected, "step_minutes": step_min,
        "mean_mw": float(day["forecast_mw"].mean()),
        "energy_mwh": float(day["forecast_mw"].sum() * step_h),
        "prudent_energy_mwh": None if day["prudent_mw"].isna().any() else float(day["prudent_mw"].sum() * step_h),
        "peak_mw": float(peak["forecast_mw"]), "peak_ts": peak["ts"].isoformat(),
        "min_mw": float(low["forecast_mw"]), "min_ts": low["ts"].isoformat(),
        "newest_publish": newest.isoformat(), "oldest_publish": day["publish"].min().isoformat(),
        "forecast_age_h": float((decision_ts - newest) / pd.Timedelta(hours=1)),
        "history_days": int(day["history_days"].max()),
        "band_q10": None if day["q10"].isna().all() else float(day["q10"].iloc[0]),
        "band_q90": None if day["q90"].isna().all() else float(day["q90"].iloc[0]),
        "revision_mwh": None if day["latest_mw"].isna().any()
        else float((day["latest_mw"] - day["forecast_mw"]).sum() * step_h),
    }
    scored = day.dropna(subset=["actual_mw"])
    if len(scored):
        summary["actual_energy_mwh"] = float(scored["actual_mw"].sum() * step_h)
        summary["day_metrics"] = compute_metrics(scored)
    return {"delivery_date": delivery_date.isoformat(), "decision_time": decision_ts.isoformat(),
            "points": pts, "blocks": blocks, "summary": summary}
