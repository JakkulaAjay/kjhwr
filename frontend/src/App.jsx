import React, { useEffect, useState } from "react";
import AccuracyView from "./AccuracyView.jsx";
import DecisionView from "./DecisionView.jsx";
import Method from "./Method.jsx";
import { Loading } from "./components.jsx";
import { getMeta } from "./api.js";

const TABS = [
  ["decision", "Tomorrow's wind"],
  ["accuracy", "Forecast accuracy"],
  ["method", "Method"],
];

export default function App() {
  const [meta, setMeta] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("decision");

  useEffect(() => { getMeta().then(setMeta).catch((e) => setError(e.message)); }, []);

  return (
    <div className="app">
      <header>
        <div>
          <h1>Wind Forecast Decision Portal</h1>
          <p className="muted">GB national wind · day-ahead purchasing support · Elexon data</p>
        </div>
        <nav>
          {TABS.map(([k, label]) => (
            <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{label}</button>
          ))}
        </nav>
      </header>
      {meta?.source === "synthetic" && (
        <div className="banner">SYNTHETIC DEMO DATA — not real Elexon data. Do not use for decisions.</div>
      )}
      <main>
        {!meta ? <Loading error={error} /> : tab === "decision" ? <DecisionView meta={meta} />
          : tab === "accuracy" ? <AccuracyView meta={meta} /> : <Method meta={meta} />}
      </main>
    </div>
  );
}
