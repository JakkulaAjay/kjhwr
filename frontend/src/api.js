async function get(path, params) {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  const res = await fetch(`/api${path}${qs}`);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* ignore */ }
    throw new Error(detail);
  }
  return res.json();
}

export const getMeta = () => get("/meta");
export const getDecision = (delivery_date) => get("/decision", { delivery_date });
export const getAccuracy = (date_from, date_to) => get("/accuracy", { date_from, date_to });
