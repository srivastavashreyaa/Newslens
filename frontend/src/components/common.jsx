export const SENT = {
  positive: { label: "Positive", color: "var(--pos)" },
  neutral: { label: "Neutral", color: "var(--neu)" },
  negative: { label: "Negative", color: "var(--neg)" },
};
export const BIAS = {
  left: { label: "Left-leaning", color: "var(--left)" },
  center: { label: "Center", color: "var(--center)" },
  right: { label: "Right-leaning", color: "var(--right)" },
};

export const SentimentPill = ({ label, score }) => (
  <span className="pill" title={`Sentiment score ${score?.toFixed?.(2)}`}>
    <i style={{ background: SENT[label]?.color }} />
    {SENT[label]?.label}
    {score !== undefined && <span style={{ color: "var(--text-muted)" }}>{score > 0 ? "+" : ""}{score.toFixed(2)}</span>}
  </span>
);

export const BiasPill = ({ label, score }) => (
  <span className="pill" title={`Bias score ${score?.toFixed?.(2)} (-1 left … +1 right)`}>
    <i style={{ background: BIAS[label]?.color }} />
    {BIAS[label]?.label}
  </span>
);

export function timeAgo(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export const fmtSigned = (n) => `${n > 0 ? "+" : ""}${n.toFixed(2)}`;

export function Tip({ active, payload, label, labelFormat, rows }) {
  if (!active || !payload?.length) return null;
  const items = rows ? rows(payload) : payload.map((p) => ({ name: p.name, value: p.value, color: p.color || p.fill }));
  return (
    <div className="tooltip">
      <b>{labelFormat ? labelFormat(label, payload) : label}</b>
      {items.map((r) => (
        <div className="row" key={r.name}>
          <span><i style={{ background: r.color }} />{r.name}</span>
          <span>{r.value}</span>
        </div>
      ))}
    </div>
  );
}

export const Legend = ({ items }) => (
  <div className="legend">
    {items.map(([name, color]) => (
      <span key={name}><i style={{ background: color }} />{name}</span>
    ))}
  </div>
);
