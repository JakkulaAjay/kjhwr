import React, { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAccuracy } from "./api.js";
import { Card, Kpi, Loading } from "./components.jsx";
import { num, pct, signed } from "./format.js";

export default function AccuracyView({ meta }) {
  const [range, setRange] = useState({ from: meta.delivery_from, to: meta.delivery_to });
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setError(null);
    getAccuracy(range.from, range.to).then(setData).catch((e) => setError(e.message));
  }, [range]);

  const dates = meta.delivery_dates;
  return (
    <>
      <Card>
        <div className="picker">
          <label>From<select value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })}>
            {dates.map((d) => <option key={d}>{d}</option>)}</select></label>
          <label>To<select value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })}>
            {dates.map((d) => <option key={d}>{d}</option>)}</select></label>
          <span className="muted">Delivery days. Every number below uses the forecast you could see at gate closure.</span>
        </div>
      </Card>
      {!data ? <Loading error={error} /> : data.overall.n ? <Body d={data} /> : <Loading error="No actuals available for this range yet." />}
    </>
  );
}

function Body({ d }) {
  const o = d.overall;
  const byDay = d.by_day.map((r) => ({ day: r.delivery_date.slice(5), mae: r.mae, bias: r.bias }));
  const byHour = d.by_hour.map((r) => ({ hour: String(r.hour).padStart(2, "0"), mae: r.mae, bias: r.bias }));
  const hist = d.histogram.map((h) => ({ bin: `${num((h.from + h.to) / 2)}`, count: h.count, from: h.from, to: h.to }));
  const worstDay = [...d.by_day].sort((a, b) => b.mae - a.mae)[0];

  return (
    <>
      <div className="kpis">
        <Kpi label="Mean absolute error" value={`${num(o.mae)} MW`} sub={`${pct(o.nmae_pct)} of average output (${num(o.mean_actual)} MW)`} tone="primary" />
        <Kpi label="RMSE" value={`${num(o.rmse)} MW`} sub="penalises large misses" />
        <Kpi label="Bias (forecast − actual)" value={`${signed(o.bias)} MW`} sub={`over-forecast in ${pct(o.over_forecast_pct, 0)} of periods`} />
        <Kpi label="90% of errors within" value={`±${num(o.p90_abs)} MW`} sub={`95%: ±${num(o.p95_abs)} MW`} />
        <Kpi label="Skill vs naive" value={o.skill_vs_naive_pct != null ? pct(o.skill_vs_naive_pct, 0) : "–"}
             sub="better than 'same as 2 days ago' (known at gate)" />
      </div>

      <Card title="What this means for the buying decision">
        <ul className="insights">
          <li>Typical miss is <b>{num(o.mae)} MW</b> per forecast period ({pct(o.nmae_pct, 0)} of average wind output). A single period can be wrong by up to <b>{num(o.max_over)} MW</b> too high or <b>{num(-o.max_under)} MW</b> too low.</li>
          <li>The forecast {o.bias >= 0 ? "tends to over-estimate" : "tends to under-estimate"} wind by <b>{num(Math.abs(o.bias))} MW</b> on average — {o.bias >= 0
            ? "so buying exactly the residual implied by the forecast leaves you short more often than long."
            : "so buying exactly the residual implied by the forecast leaves you long more often than short."}</li>
          {d.calibration && <li>Using the prudent line (forecast minus the 90th-percentile over-forecast), actual wind was at or above it in <b>{pct(d.calibration.prudent_hit_pct, 0)}</b> of periods (target 90%); the shaded 80% band contained actuals <b>{pct(d.calibration.inside_80_band_pct, 0)}</b> of the time.</li>}
          {worstDay && <li>Hardest day to forecast: <b>{worstDay.delivery_date}</b> (MAE {num(worstDay.mae)} MW).</li>}
        </ul>
      </Card>

      <Card title="Error by delivery day" subtitle="MAE (bars) and bias (line), MW.">
        <ResponsiveContainer width="100%" height={300}>
          <ComposedChart data={byDay}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="day" tick={{ fontSize: 11 }} /><YAxis /><Tooltip formatter={(v) => `${num(v)} MW`} /><Legend />
            <ReferenceLine y={0} stroke="#6b7280" />
            <Bar dataKey="mae" name="MAE" fill="#60a5fa" isAnimationActive={false} />
            <Line dataKey="bias" name="Bias" stroke="#dc2626" dot={false} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </Card>

      <div className="grid2">
        <Card title="Error by hour of day (London)" subtitle="Which delivery hours are riskiest?">
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={byHour}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="hour" /><YAxis /><Tooltip formatter={(v) => `${num(v)} MW`} /><Legend />
              <ReferenceLine y={0} stroke="#6b7280" />
              <Bar dataKey="mae" name="MAE" fill="#60a5fa" isAnimationActive={false} />
              <Line dataKey="bias" name="Bias" stroke="#dc2626" dot={false} isAnimationActive={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Error vs forecast lead time" subtitle="All published vintages: error grows the further ahead the forecast is made.">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={d.by_horizon}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="bucket" tick={{ fontSize: 11 }} /><YAxis /><Tooltip formatter={(v) => `${num(v)} MW`} />
              <Bar dataKey="mae" name="MAE" fill="#818cf8" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
          {d.median_decision_horizon_h != null && <p className="muted">Median lead time of the decision forecast: {num(d.median_decision_horizon_h, 1)} h.</p>}
        </Card>
      </div>

      <div className="grid2">
        <Card title="Distribution of errors (forecast − actual)" subtitle="Right of zero = over-forecast (you'd be short).">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={hist}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="bin" tick={{ fontSize: 10 }} /><YAxis />
              <Tooltip labelFormatter={(l) => `≈ ${l} MW`} />
              <Bar dataKey="count" name="Half-hours" fill="#34d399" isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </Card>
        <Card title="Error by forecast wind level" subtitle="Errors are larger when more wind is forecast.">
          <table>
            <thead><tr><th>Forecast</th><th>n</th><th>MAE</th><th>Bias</th><th>P90 abs</th></tr></thead>
            <tbody>{d.by_level.map((r) => (
              <tr key={r.level}><td>{r.level}</td><td>{num(r.n)}</td><td>{num(r.mae)}</td><td>{signed(r.bias)}</td><td>{num(r.p90_abs)}</td></tr>
            ))}</tbody>
          </table>
        </Card>
      </div>
    </>
  );
}
