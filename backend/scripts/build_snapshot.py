"""Fetch real data from Elexon and write a snapshot used by the deployed app.

Run once (needs internet) from the repo root, then commit backend/data/*:

    python -m backend.scripts.build_snapshot            # real Elexon data
    python -m backend.scripts.build_snapshot --synthetic  # offline demo data (clearly flagged in the UI)
"""
import argparse

from backend.app import store
from backend.app.synthetic import make_synthetic


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true")
    args = ap.parse_args()
    if args.synthetic:
        act, fc = make_synthetic()
        source = "synthetic"
    else:
        act, fc = store.fetch_live()
        source = "elexon"
    if act.empty or fc.empty:
        raise SystemExit("No rows returned - check network access / Elexon API parameters.")
    store.save_snapshot(act, fc, source)
    print(f"[{source}] actuals={len(act)} forecasts={len(fc)} "
          f"actual range {act.ts.min()} .. {act.ts.max()}; forecast publish range {fc.publish.min()} .. {fc.publish.max()}")


if __name__ == "__main__":
    main()
