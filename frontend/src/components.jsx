import React from "react";

export function Kpi({ label, value, sub, tone }) {
  return (
    <div className={`kpi ${tone || ""}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}

export function Card({ title, subtitle, children }) {
  return (
    <section className="card">
      {title && <h3>{title}</h3>}
      {subtitle && <p className="muted">{subtitle}</p>}
      {children}
    </section>
  );
}

export function Loading({ error }) {
  return <div className={`state ${error ? "error" : ""}`}>{error ? `Something went wrong: ${error}` : "Loading…"}</div>;
}
