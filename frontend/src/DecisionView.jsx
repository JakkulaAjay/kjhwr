import React, { useEffect, useState } from "react";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDecision } from "./api.js";
import { Card, Kpi, Loading } from "./components.jsx";
import { fmtDateTime, fmtTime, gwh, mw, num, signed } from "./format.js";

export default function DecisionView({ meta }) {
  const dates = meta.delivery_dates;
  const [date, setDate] = useState(dates[Math.min(13, dates.length - 1)]); // default mid-month
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null); setError(null);
    getDecision(date).then(setData).catch((e) => setError(e.message));
  }, [date]);

  const idx = dates.indexOf(date);
  const step = (n) => setDate(dates[Math.min(Math.max(idx + n, 0), dates.length - 1)]);

  return (
    <>
      <Card>
        <div className="picker">
          <button onClick={() => step(-1)} disabled={idx <= 0} aria-label="Previous day">‹</button>
          <label>
            Delivery day to buy for
            <select value={date} onChange={(e) => setDate(e.target.value)}>
              {dates.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </label>
          <button onClick={() => step(1)} disabled={idx >= dates.length - 1} aria-label="Next day">›</button>
          {data && <span className="muted">Decision made by gate closure: <b>{fmtDateTime(data.decision_time)}</b> (London)</span>}
        </div>
      </Card>
      {!data ? <Loading error={error} /> : <Body data={data} />}
    </>
  );
}

function Body({ data }) {
  const s = data.summary;
  if (!data.points.length) return <Loading error="No forecast was available at gate closure for this day." />;

  const chart = data.points.map((p) => ({
    label: fmtTime(p.ts),
    forecast: p.forecast_mw,
    latest: p.latest_mw,
    actual: p.actual_mw,
    band: p.prudent_mw != null && p.upper_mw != null ? [p.prudent_mw, p.upper_mw] : null,
  }));
  const hasActual = chart.some((c) => c.actual != null);
  const hasBand = chart.some((c) => c.band);

  return (
    <>
      <div className="kpis">
        <Kpi label="Wind to deduct (decision forecast)" value={gwh(s.energy_mwh)} sub={`avg ${mw(s.mean_mw)}`} tone="primary" />
        <Kpi label="Prudent wind (≈90% confidence)" value={s.prudent_energy_mwh != null ? gwh(s.prudent_energy_mwh) : "n/a yet"}
             sub={s.prudent_energy_mwh != null ? `${signed((s.prudent_energy_mwh - s.energy_mwh) / 1000, 1)} GWh vs forecast`
               : `needs ≥2 prior days of errors (have ${s.history_days})`} />
        <Kpi label="Peak / lowest forecast" value={`${num(s.peak_mw)} / ${num(s.min_mw)} MW`}
             sub={`peak at ${fmtTime(s.peak_ts)}, low at ${fmtTime(s.min_ts)}`} />
        <Kpi label="Forecast freshness at gate" value={`${num(s.forecast_age_h, 1)} h old`}
             sub={`newest vintage ${fmtDateTime(s.newest_publish)}`} />
        <Kpi label="Later revision (after gate)" value={s.revision_mwh != null ? `${signed(s.revision_mwh / 1000, 2)} GWh` : "–"}
             sub="latest pre-delivery forecast minus decision forecast" />
      </div>

      <Card title="Wind generation: forecast available at decision time"
            subtitle={`Delivery ${data.delivery_date}, London time, at the forecast's native resolution. Solid = forecast you would have seen at gate closure${hasBand ? "; shaded = 80% range from past forecast errors" : ""}${hasActual ? "; orange = what actually happened" : ""}.`}>
        <ResponsiveContainer width="100%" height={380}>
          <ComposedChart data={chart} margin={{ top: 10, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis dataKey="label" interval={5} tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} domain={[0, "auto"]} tickFormatter={(v) => `${(v / 1000).toFixed(1)} GW`} />
            <Tooltip formatter={(v) => (Array.isArray(v) ? `${num(v[0])} – ${num(v[1])} MW` : `${num(v)} MW`)} />
            <Legend />
            {hasBand && <Area dataKey="band" name="80% range" stroke="none" fill="#93c5fd" fillOpacity={0.45} isAnimationActive={false} />}
            <Line dataKey="forecast" name="Decision forecast" stroke="#2563eb" strokeWidth={2.5} dot={false} isAnimationActive={false} />
            <Line dataKey="latest" name="Latest forecast before delivery" stroke="#9ca3af" strokeDasharray="5 4" dot={false} isAnimationActive={false} />
            {hasActual && <Line dataKey="actual" name="Actual" stroke="#f97316" strokeWidth={2.5} dot={false} isAnimationActive={false} />}
          </ComposedChart>
        </ResponsiveContainer>
        {s.coverage_pct < 100 && <p className="warn">Forecast covers {s.coverage_pct.toFixed(0)}% of the day's {s.step_minutes}-minute periods.</p>}
      </Card>

      <Card title="Six-hour blocks" subtitle="Average wind to deduct from your demand forecast in each block (MW).">
        <table>
          <thead><tr><th>Block</th><th>Forecast</th><th>Prudent (≈P90)</th><th>Actual</th></tr></thead>
          <tbody>
            {data.blocks.map((b) => (
              <tr key={b.label}><td>{b.label}</td><td>{num(b.forecast_mw)}</td><td>{num(b.prudent_mw)}</td><td>{num(b.actual_mw)}</td></tr>
            ))}
          </tbody>
        </table>
      </Card>

      {s.day_metrics && (
        <Card title="How this day turned out" subtitle="Available once actuals are published.">
          <div className="kpis">
            <Kpi label="Mean absolute error" value={mw(s.day_metrics.mae)} sub={`${num(s.day_metrics.nmae_pct, 1)}% of average output`} />
            <Kpi label="Bias (forecast − actual)" value={`${signed(s.day_metrics.bias)} MW`}
                 sub={s.day_metrics.bias > 0 ? "over-forecast: risk of being short" : "under-forecast: risk of being long"} />
            <Kpi label="Actual energy" value={gwh(s.actual_energy_mwh)} sub={`forecast ${gwh(s.energy_mwh)}`} />
          </div>
        </Card>
      )}
    </>
  );
}
