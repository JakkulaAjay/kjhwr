import React from "react";
import { Card } from "./components.jsx";

export default function Method({ meta }) {
  return (
    <>
      <Card title="Method & assumptions">
        <ul className="insights">
          <li><b>Data:</b> Elexon Insights API only — FUELHH (actual wind, half-hourly) and WINDFOR (wind forecasts, many publish times per target half-hour).</li>
          <li><b>Decision forecast:</b> for each half-hour of delivery day D, the latest WINDFOR vintage with publishTime ≤ <b>{meta.gate_closure_local} London time on D−1</b> (EPEX GB day-ahead gate closure; N2EX closes at 09:50, so this is the conservative choice). Forecasts published later are never used.</li>
          <li><b>Scope:</b> purchase decisions taken {meta.decision_from} → {meta.decision_to}, i.e. delivery days {meta.delivery_from} → {meta.delivery_to}.</li>
          <li><b>Error:</b> forecast − actual. Positive = over-forecast (risk of being short); negative = under-forecast (risk of being long).</li>
          <li><b>Prudent line / 80% range:</b> empirical 10th/90th percentile of past decision-time errors, using only delivery days up to D−2 (actuals for D−1 are not known at the gate). No look-ahead; unavailable until two prior days exist.</li>
          <li><b>Naive baseline:</b> actual wind at the same half-hour two days earlier (the latest fully-known day at gate closure). Skill = 1 − MAE(forecast)/MAE(naive).</li>
          <li><b>Not included:</b> demand, prices, solar, embedded generation, imbalance costs. National totals only.</li>
        </ul>
      </Card>
      <Card title="Data status">
        <p>Source: <b>{meta.source}</b>{meta.fetched_at ? ` · fetched ${meta.fetched_at}` : ""} · {meta.rows.actuals.toLocaleString()} actual rows · {meta.rows.forecasts.toLocaleString()} forecast rows.</p>
      </Card>
    </>
  );
}
