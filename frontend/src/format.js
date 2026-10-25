const TZ = "Europe/London";
const hm = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hour12: false });
const dt = new Intl.DateTimeFormat("en-GB", {
  timeZone: TZ, weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false,
});

export const fmtTime = (iso) => hm.format(new Date(iso));
export const fmtDateTime = (iso) => dt.format(new Date(iso));
export const mw = (v, d = 0) => (v == null ? "–" : `${Number(v).toLocaleString("en-GB", { maximumFractionDigits: d })} MW`);
export const gwh = (v) => (v == null ? "–" : `${(v / 1000).toLocaleString("en-GB", { maximumFractionDigits: 1 })} GWh`);
export const num = (v, d = 0) => (v == null ? "–" : Number(v).toLocaleString("en-GB", { maximumFractionDigits: d }));
export const pct = (v, d = 1) => (v == null ? "–" : `${Number(v).toFixed(d)}%`);
export const signed = (v, d = 0) => (v == null ? "–" : `${v > 0 ? "+" : ""}${Number(v).toLocaleString("en-GB", { maximumFractionDigits: d })}`);
