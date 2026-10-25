# Video script (max 10 min total, unlisted YouTube)

Record the screen at 1080p, app already loaded on the real-data snapshot. **Replace every ⟨…⟩ with the number the app shows.**

## Part 1 – Customer pitch (≈4:30)

**0:00 – Hook (20 s)**
"Every morning before 09:20 your desk commits to tomorrow's power purchases, using a wind forecast. Two questions decide
how much you over- or under-buy: *what exactly was the forecast at that moment*, and *how wrong has it been?* This portal answers both."

**0:20 – Tomorrow's wind tab (100 s)**
- Pick a delivery day, e.g. 15 Jan. "The blue line is the forecast you'd have seen at gate closure – 09:20 the day before. Not the latest one, the one you could act on."
- Point at KPIs: "⟨X⟩ GWh of wind to deduct; average ⟨Y⟩ MW; peak ⟨Z⟩ MW at ⟨time⟩. Forecast was ⟨n⟩ hours old."
- "The shaded band and 'prudent' number come from the forecast's own past errors: you can count on ⟨P⟩ GWh with ~90 % confidence."
- "The grey dashed line is how the forecast changed after the auction closed – ⟨R⟩ GWh – relevant to your intraday plans."
- Scroll to six-hour blocks: "Ready to drop into your block purchases."
- Show a day with actuals: "And once the day is done, you see what really happened."

**2:00 – Accuracy tab (110 s)**
- "Over January: typical miss ⟨MAE⟩ MW, ⟨nMAE⟩ % of average output; 90 % of half-hours within ±⟨P90⟩ MW."
- "Bias: the forecast ⟨over/under⟩-estimates by ⟨bias⟩ MW – so buying exactly the implied residual leaves you ⟨short/long⟩ more often."
- Hour-of-day chart: "Riskiest hours are ⟨…⟩." Level table: "Errors grow with wind level – ⟨…⟩ MW MAE above 10 GW."
- Skill: "It beats 'same as two days ago' by ⟨S⟩ %, so it is worth using – but quantify the error."

**3:50 – Close (40 s)**
"This pilot uses national wind from Elexon only. Next: add your demand forecast and imbalance prices to turn this uncertainty into a £ hedge recommendation, and run it daily. Happy to show it on your own data."

## Part 2 – Tech lead review (≈4:30)

**5:00 – Architecture (60 s)** Show `docs/DESIGN.md` diagram. React/Vite → FastAPI → in-memory pandas table; Elexon FUELHH/WINDFOR; snapshot for serverless, live for Docker; one Dockerfile.

**6:00 – Core logic (120 s)** Open `analytics.py`.
- `forecast_as_of`: "latest vintage with publishTime ≤ gate closure – the one rule that makes the whole analysis honest."
- `gate_time_utc`: London local → UTC (DST safe).
- `add_rolling_bands`: D-2 lag, no look-ahead. Sign convention at top of file.
- `compute_metrics`: why nMAE not MAPE; naive baseline at t-48h.

**8:00 – Tests & practices (60 s)** Run `pytest`: gate-boundary tests, no-look-ahead test, API tests. Mention type-safe JSON cleaning (NaN→null), config via env, README, AI-assistance disclosure.

**9:00 – Assumptions & next steps (50 s)** January window interpretation, 09:20 vs 09:50, one month of data, unconditional bands → conditional/quantile model, add demand & price. "Everything is in the README."

*Timing check: stop recording at 9:50.*
