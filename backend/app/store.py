"""In-memory data store. Loads once (snapshot -> live -> synthetic) and precomputes the joined table."""
from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from . import analytics, config, elexon
from .synthetic import make_synthetic

ACT_FILE = "actuals.csv.gz"
FC_FILE = "forecasts.csv.gz"
META_FILE = "meta.json"


def fetch_live() -> tuple[pd.DataFrame, pd.DataFrame]:
    first_delivery = config.DECISION_FROM + timedelta(days=1)
    last_delivery = config.DECISION_TO + timedelta(days=1)
    # forecasts published 2 days before first delivery to the end of the last delivery day;
    # actuals reach back 3 days for the naive (t-48h) baseline.
    fc = elexon.fetch_forecasts(first_delivery - timedelta(days=3), last_delivery)
    act = elexon.fetch_actuals(first_delivery - timedelta(days=3), last_delivery)
    return act, fc


def save_snapshot(act: pd.DataFrame, fc: pd.DataFrame, source: str = "elexon") -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    act.to_csv(config.DATA_DIR / ACT_FILE, index=False)
    fc.to_csv(config.DATA_DIR / FC_FILE, index=False)
    (config.DATA_DIR / META_FILE).write_text(json.dumps({
        "source": source, "fetched_at": datetime.now(timezone.utc).isoformat(),
        "decision_from": config.DECISION_FROM.isoformat(), "decision_to": config.DECISION_TO.isoformat()}))


def _snapshot_exists() -> bool:
    return (config.DATA_DIR / ACT_FILE).exists() and (config.DATA_DIR / FC_FILE).exists()


def _load_snapshot() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    act = pd.read_csv(config.DATA_DIR / ACT_FILE, parse_dates=["ts"])
    fc = pd.read_csv(config.DATA_DIR / FC_FILE, parse_dates=["ts", "publish"])
    for df, cols in ((act, ["ts"]), (fc, ["ts", "publish"])):
        for c in cols:
            df[c] = pd.to_datetime(df[c], utc=True)
    meta_path = config.DATA_DIR / META_FILE
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"source": "elexon"}
    return act, fc, meta


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.ready = False

    def load(self) -> None:
        with self._lock:
            if self.ready:
                return
            mode = config.DATA_MODE
            if mode == "auto":
                mode = "snapshot" if _snapshot_exists() else "live"
            if mode == "snapshot":
                act, fc, meta = _load_snapshot()
            elif mode == "live":
                act, fc = fetch_live()
                meta = {"source": "elexon", "fetched_at": datetime.now(timezone.utc).isoformat()}
            elif mode == "synthetic":
                act, fc = make_synthetic()
                meta = {"source": "synthetic", "fetched_at": datetime.now(timezone.utc).isoformat()}
            else:
                raise ValueError(f"Unknown DATA_MODE {mode!r}")
            self.set_data(act, fc, meta)

    def set_data(self, act: pd.DataFrame, fc: pd.DataFrame, meta: dict) -> None:
        self.actuals, self.forecasts, self.meta = act, fc, meta
        self.joined = analytics.build_joined(act, fc, config.GATE_CLOSURE, config.DECISION_FROM, config.DECISION_TO)
        self.horizon = analytics.horizon_table(act, fc, config.DECISION_FROM, config.DECISION_TO)
        self.ready = True

    # convenience ---------------------------------------------------------------
    def delivery_range(self) -> tuple[date, date]:
        return config.DECISION_FROM + timedelta(days=1), config.DECISION_TO + timedelta(days=1)

    def available_delivery_dates(self) -> list[str]:
        return sorted(d.isoformat() for d in self.joined["delivery_date"].unique())


store = DataStore()
