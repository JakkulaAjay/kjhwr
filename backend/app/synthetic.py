"""Synthetic wind data with a realistic *shape* (hourly forecast vintages, error growing with horizon).

FOR TESTS / OFFLINE DEMOS ONLY. The API reports source="synthetic" and the UI shows a banner.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _smooth_unit(rng: np.random.Generator, n: int, window: int) -> np.ndarray:
    x = np.convolve(rng.standard_normal(n + window), np.ones(window) / window, mode="valid")[:n]
    sd = x.std()
    return x / sd if sd > 0 else x


def make_synthetic(start="2025-12-28", end="2026-02-02", seed: int = 7) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    ts = pd.date_range(start, end, freq="30min", tz="UTC", inclusive="left")
    n = len(ts)
    level = 7000 + 3500 * _smooth_unit(rng, n, 96)
    actual = np.clip(level + 500 * _smooth_unit(rng, n, 6), 150, 17500)
    actuals = pd.DataFrame({"ts": ts, "actual_mw": actual})

    common = _smooth_unit(rng, n, 10)  # error shared by all vintages of a target
    idx = {t: i for i, t in enumerate(ts)}
    rows = []
    for p in pd.date_range(ts[0], ts[-1], freq="1h", tz="UTC"):
        tg = pd.date_range(p + pd.Timedelta(minutes=30), periods=96, freq="30min")  # up to 48h ahead
        tg = tg[tg <= ts[-1]]
        if len(tg) == 0:
            continue
        ii = np.array([idx[t] for t in tg])
        h = ((tg - p) / pd.Timedelta(hours=1)).to_numpy(dtype=float)
        sd = 250 + 95 * h
        own = _smooth_unit(rng, len(tg), 6)
        noise = sd * (0.7 * common[ii] + np.sqrt(1 - 0.49) * own) + 120  # slight over-forecast bias
        fc = np.clip(actual[ii] + noise, 0, 18000)
        rows.append(pd.DataFrame({"ts": tg, "publish": p, "forecast_mw": fc}))
    return actuals, pd.concat(rows, ignore_index=True)
