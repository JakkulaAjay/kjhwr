"""Central configuration. Everything that encodes a business assumption lives here."""
import os
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")
UTC = ZoneInfo("UTC")

ELEXON_BASE = os.getenv("ELEXON_BASE", "https://data.elexon.co.uk/bmrs/api/v1")

# Day-ahead gate closure (London local time, on the day BEFORE delivery).
# EPEX GB 60-min auction closes 09:20, N2EX (Nord Pool) closes 09:50.
# We default to the earlier one so a forecast is never used that the buyer could not have seen.
_gate = os.getenv("GATE_CLOSURE_LOCAL", "09:20").split(":")
GATE_CLOSURE = time(int(_gate[0]), int(_gate[1]))

# "Purchase decisions to be made in January 2026": decisions are taken on each day of
# January 2026 (gate closure on day D-1) for delivery on D = decision date + 1.
DECISION_FROM = date.fromisoformat(os.getenv("DECISION_FROM", "2026-01-01"))
DECISION_TO = date.fromisoformat(os.getenv("DECISION_TO", "2026-01-31"))

# Prediction band: minimum number of fully-observed prior delivery days required.
MIN_HISTORY_DAYS = int(os.getenv("MIN_HISTORY_DAYS", "2"))
# Actuals for delivery day D-1 are not known at the D-1 gate, so errors are only
# used from delivery days <= D - BAND_LAG_DAYS (no look-ahead).
BAND_LAG_DAYS = 2

DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
# auto: snapshot if present, else live Elexon.  Other values: snapshot | live | synthetic
DATA_MODE = os.getenv("DATA_MODE", "auto").lower()
STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
