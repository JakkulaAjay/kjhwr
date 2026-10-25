# Design notes (for the technical review)

## Data flow
```
Elexon FUELHH ─┐                                  ┌─ /api/decision?delivery_date=
               ├─ store.py (snapshot|live) ─ analytics.build_joined ─┤
Elexon WINDFOR ┘                                  └─ /api/accuracy?date_from=&date_to=
```
`build_joined` yields one row per target half-hour: decision forecast (+ its publish time and lead time), latest pre-delivery
forecast, actual, naive baseline, error, and rolling bands. Both endpoints are cheap slices of this table, computed once at startup.

## Why snapshot + live
Vercel functions are short-lived; fetching ~80k WINDFOR rows per cold start is slow and fragile. `build_snapshot.py`
downloads once; `DATA_MODE=auto` uses the snapshot when present and falls back to live fetching (Docker/Heroku).

## Correctness checks (tests)
* Vintage published after gate closure is never selected; exactly-at-gate is included; targets with no eligible vintage are dropped, not back-filled.
* GMT vs BST gate-time conversion.
* Metric values and sign convention on hand-computed data.
* Bands for day D equal quantiles of errors from days ≤ D-2 (no look-ahead).
* API shape, 48 points/day, validation errors (422/404), error grows with lead time on synthetic data.

## Assumptions to confirm with the product manager
1. "Decisions made in January 2026" → decisions on 1–31 Jan for delivery 2 Jan–1 Feb (alternative: deliveries 1–31 Jan; change `DECISION_FROM/TO`).
2. Gate closure 09:20 London (EPEX). 09:50 (N2EX) is one env var away.
3. Elexon Insights API parameter names/response shapes were taken from public documentation; verify with the first real snapshot run.
