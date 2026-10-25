from datetime import date, time

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.app import analytics as an
from backend.app.main import app
from backend.app.store import store
from backend.app.synthetic import make_synthetic

GATE = time(9, 20)
U = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731


def test_gate_time_is_day_before_london_local():
    # January = GMT, so London == UTC
    assert an.gate_time_utc(date(2026, 1, 15), GATE) == U("2026-01-14 09:20")
    # BST: 09:20 London == 08:20 UTC
    assert an.gate_time_utc(date(2026, 7, 15), GATE) == U("2026-07-14 08:20")


def test_decision_forecast_ignores_vintages_after_gate_closure():
    ts = U("2026-01-15 12:00")
    fc = pd.DataFrame({
        "ts": [ts] * 4,
        "publish": [U("2026-01-13 21:00"), U("2026-01-14 09:00"), U("2026-01-14 09:30"), U("2026-01-14 18:00")],
        "forecast_mw": [1000.0, 2000.0, 3000.0, 4000.0],
    })
    out = an.forecast_as_of(fc, lambda d: an.gate_time_utc(d, GATE))
    assert len(out) == 1
    assert out.loc[0, "forecast_mw"] == 2000.0          # 09:00 is the last vintage <= 09:20
    assert out.loc[0, "publish"] == U("2026-01-14 09:00")


def test_decision_forecast_exactly_at_gate_is_included():
    ts = U("2026-01-15 12:00")
    fc = pd.DataFrame({"ts": [ts], "publish": [U("2026-01-14 09:20")], "forecast_mw": [5.0]})
    assert len(an.forecast_as_of(fc, lambda d: an.gate_time_utc(d, GATE))) == 1


def test_target_without_eligible_vintage_is_dropped_not_filled():
    ts = U("2026-01-15 12:00")
    fc = pd.DataFrame({"ts": [ts], "publish": [U("2026-01-14 12:00")], "forecast_mw": [5.0]})
    assert an.forecast_as_of(fc, lambda d: an.gate_time_utc(d, GATE)).empty


def test_metrics_sign_and_values():
    df = pd.DataFrame({"forecast_mw": [110.0, 90.0, 150.0], "actual_mw": [100.0, 100.0, 100.0]})
    m = an.compute_metrics(df)
    assert m["bias"] == pytest.approx((10 - 10 + 50) / 3)       # positive = over-forecast
    assert m["mae"] == pytest.approx(70 / 3)
    assert m["rmse"] == pytest.approx(np.sqrt((100 + 100 + 2500) / 3))
    assert m["over_forecast_pct"] == pytest.approx(200 / 3)
    assert m["nmae_pct"] == pytest.approx(70 / 3)


def test_metrics_skip_missing_actuals():
    df = pd.DataFrame({"forecast_mw": [1.0, 2.0], "actual_mw": [1.0, np.nan]})
    assert an.compute_metrics(df)["n"] == 1


def test_bands_use_no_lookahead():
    actuals, fc = make_synthetic()
    j = an.build_joined(actuals, fc, GATE, date(2026, 1, 1), date(2026, 1, 31))
    first = j[j["delivery_date"] == date(2026, 1, 2)]
    assert first["q90"].isna().all()                          # no history yet -> no band
    d = date(2026, 1, 10)
    row = j[j["delivery_date"] == d].iloc[0]
    hist = j[j["delivery_date"] <= date(2026, 1, 8)]["error"]  # D-2 and earlier only
    assert row["q90"] == pytest.approx(np.percentile(hist, 90))
    assert (j["prudent_mw"].dropna() >= 0).all()
    assert (j.dropna(subset=["prudent_mw"])["prudent_mw"] <= j.dropna(subset=["prudent_mw"])["upper_mw"]).all()


@pytest.fixture(scope="module")
def client():
    actuals, fc = make_synthetic()
    store.set_data(actuals, fc, {"source": "synthetic"})
    return TestClient(app)


def test_api_meta_and_decision(client):
    m = client.get("/api/meta").json()
    assert m["delivery_from"] == "2026-01-02" and m["delivery_to"] == "2026-02-01"
    d = client.get("/api/decision", params={"delivery_date": "2026-01-15"}).json()
    assert len(d["points"]) == 48
    assert d["summary"]["coverage_pct"] == 100.0
    assert d["decision_time"].startswith("2026-01-14T09:20")
    # every forecast used was published at or before gate closure
    assert all(p["publish"] <= d["decision_time"] for p in d["points"])
    assert d["summary"]["forecast_age_h"] >= 0


def test_api_accuracy(client):
    a = client.get("/api/accuracy").json()
    assert a["overall"]["n"] == 31 * 48
    assert len(a["by_day"]) == 31 and len(a["by_hour"]) == 24
    horizons = [r["mae"] for r in a["by_horizon"]]
    assert horizons[0] < horizons[-1]                          # error grows with lead time
    assert a["calibration"]["n"] > 0


def test_api_validation(client):
    assert client.get("/api/decision", params={"delivery_date": "nope"}).status_code == 422
    assert client.get("/api/decision", params={"delivery_date": "2025-06-01"}).status_code == 404
    assert client.get("/api/accuracy", params={"date_from": "2026-01-10", "date_to": "2026-01-02"}).status_code == 422


def test_energy_uses_native_resolution_hourly_forecasts():
    """WINDFOR is hourly: 24 flat points of 1000 MW must be 24 GWh/day and 100% coverage."""
    ts = pd.date_range("2026-01-15", periods=24, freq="1h", tz="UTC")
    fc = pd.DataFrame({"ts": ts, "publish": U("2026-01-14 07:30"), "forecast_mw": 1000.0})
    act = pd.DataFrame({"ts": pd.date_range("2026-01-13", "2026-01-16", freq="30min", tz="UTC", inclusive="left"),
                        "actual_mw": 900.0})
    j = an.build_joined(act, fc, GATE, date(2026, 1, 1), date(2026, 1, 31))
    s = an.decision_view(j, date(2026, 1, 15), GATE)["summary"]
    assert s["energy_mwh"] == pytest.approx(24000.0)
    assert s["actual_energy_mwh"] == pytest.approx(21600.0)
    assert s["coverage_pct"] == pytest.approx(100.0)
    assert s["step_minutes"] == 60.0
