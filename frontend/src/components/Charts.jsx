import {
  Bar, BarChart, CartesianGrid, Cell, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { BIAS, Legend, SENT, Tip, fmtSigned } from "./common";

const axisProps = { stroke: "var(--axis)", tick: { fill: "var(--text-muted)", fontSize: 11 }, tickLine: false };

function fmtTime(iso, bucket) {
  const d = new Date(iso);
  return bucket === "day"
    ? d.toLocaleDateString(undefined, { month: "short", day: "numeric" })
    : d.toLocaleString(undefined, { weekday: "short", hour: "numeric" });
}

export function SentimentTimeline({ data, bucket }) {
  if (!data?.length) return <div className="empty">No articles in this window.</div>;
  const rows = data.map((d) => ({ ...d, label: fmtTime(d.t, bucket) }));
  return (
    <>
      <p className="sub" style={{ marginBottom: 4 }}>Average sentiment score (−1 negative … +1 positive)</p>
      <ResponsiveContainer width="100%" height={170}>
        <LineChart data={rows} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="label" {...axisProps} minTickGap={32} />
          <YAxis domain={[-1, 1]} ticks={[-1, -0.5, 0, 0.5, 1]} {...axisProps} />
          <ReferenceLine y={0} stroke="var(--axis)" />
          <Tooltip
            cursor={{ stroke: "var(--axis)" }}
            content={<Tip labelFormat={(l) => l} rows={(p) => [{ name: "Avg sentiment", value: fmtSigned(p[0].value), color: "var(--text-secondary)" }, { name: "Articles", value: p[0].payload.count, color: "var(--axis)" }]} />}
          />
          <Line type="monotone" dataKey="avg" stroke="var(--text-primary)" strokeWidth={2} dot={{ r: 3, fill: "var(--surface-1)", strokeWidth: 2 }} activeDot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>

      <p className="sub" style={{ margin: "12px 0 4px" }}>Articles per {bucket} by sentiment</p>
      <Legend items={[["Positive", SENT.positive.color], ["Neutral", SENT.neutral.color], ["Negative", SENT.negative.color]]} />
      <ResponsiveContainer width="100%" height={170}>
        <BarChart data={rows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }} barCategoryGap="18%">
          <CartesianGrid stroke="var(--grid)" vertical={false} />
          <XAxis dataKey="label" {...axisProps} minTickGap={32} />
          <YAxis allowDecimals={false} {...axisProps} />
          <Tooltip
            cursor={{ fill: "var(--grid)", opacity: 0.5 }}
            content={<Tip rows={(p) => [...p].reverse().map((x) => ({ name: SENT[x.dataKey].label, value: x.value, color: SENT[x.dataKey].color }))} />}
          />
          {["negative", "neutral", "positive"].map((k) => (
            <Bar key={k} dataKey={k} stackId="s" fill={SENT[k].color} stroke="var(--surface-1)" strokeWidth={2} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </>
  );
}

function HBar({ data, valueKey, colorFor, domain, format, name }) {
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 38 + 24)}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 0 }} barCategoryGap="28%">
        <CartesianGrid stroke="var(--grid)" horizontal={false} />
        <XAxis type="number" domain={domain} {...axisProps} />
        <YAxis type="category" dataKey="source" width={118} {...axisProps} tick={{ fill: "var(--text-secondary)", fontSize: 12 }} />
        <ReferenceLine x={0} stroke="var(--axis)" />
        <Tooltip
          cursor={{ fill: "var(--grid)", opacity: 0.5 }}
          content={<Tip labelFormat={(l) => l} rows={(p) => [{ name, value: format(p[0].value), color: colorFor(p[0].payload) }, { name: "Articles", value: p[0].payload.count, color: "var(--axis)" }]} />}
        />
        <Bar dataKey={valueKey} radius={[4, 4, 4, 4]} maxBarSize={18}>
          {data.map((d) => <Cell key={d.source} fill={colorFor(d)} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SourceSentiment({ data }) {
  if (!data?.length) return <div className="empty">No data.</div>;
  const sorted = [...data].sort((a, b) => b.avg_sentiment - a.avg_sentiment);
  return (
    <>
      <Legend items={[["Net positive tone", SENT.positive.color], ["Net negative tone", SENT.negative.color]]} />
      <HBar data={sorted} valueKey="avg_sentiment" name="Avg sentiment" domain={[-1, 1]} format={fmtSigned}
        colorFor={(d) => (d.avg_sentiment >= 0 ? SENT.positive.color : SENT.negative.color)} />
    </>
  );
}

export function SourceBias({ data }) {
  if (!data?.length) return <div className="empty">No data.</div>;
  return (
    <>
      <Legend items={[["Left", BIAS.left.color], ["Center", BIAS.center.color], ["Right", BIAS.right.color]]} />
      <HBar data={data} valueKey="avg_bias" name="Avg bias" domain={[-1, 1]} format={fmtSigned}
        colorFor={(d) => (d.avg_bias <= -0.25 ? BIAS.left.color : d.avg_bias >= 0.25 ? BIAS.right.color : BIAS.center.color)} />
    </>
  );
}

export function SourceTable({ data }) {
  if (!data?.length) return null;
  return (
    <details style={{ marginTop: 8 }}>
      <summary style={{ cursor: "pointer", color: "var(--text-secondary)", fontSize: 12 }}>Table view</summary>
      <table className="src">
        <thead><tr><th>Source</th><th>Articles</th><th>Avg sentiment</th><th>% negative</th><th>Bias</th><th>Loaded language</th></tr></thead>
        <tbody>
          {data.map((s) => (
            <tr key={s.source}>
              <td>{s.source}</td><td>{s.count}</td><td>{fmtSigned(s.avg_sentiment)}</td>
              <td>{s.pct_negative}%</td><td>{fmtSigned(s.avg_bias)}</td><td>{Math.round(s.avg_subjectivity * 100)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
