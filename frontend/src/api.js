const BASE = import.meta.env.VITE_API_URL || "";

async function request(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail?.[0]?.msg || detail.detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const qs = (params) => {
  const p = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && v !== null && p.set(k, v));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  health: () => request("/api/health"),
  overview: (hours) => request(`/api/stats/overview${qs({ hours })}`),
  timeline: (hours, bucket) => request(`/api/stats/sentiment-timeline${qs({ hours, bucket })}`),
  sources: (hours) => request(`/api/stats/sources${qs({ hours })}`),
  trends: (hours) => request(`/api/stats/trends${qs({ hours, limit: 8 })}`),
  stories: (hours) => request(`/api/stories${qs({ hours })}`),
  articles: (params) => request(`/api/articles${qs(params)}`),
  analyze: (body) =>
    request("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  ingest: () => request("/api/ingest", { method: "POST" }),
};

export function wsUrl() {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${window.location.host}/ws/stream`;
}
