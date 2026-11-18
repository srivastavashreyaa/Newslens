import { useState } from "react";
import { api } from "../api";
import { BiasPill, BIAS, SENT, SentimentPill, fmtSigned, timeAgo } from "./common";

export function Trends({ data, onPick }) {
  if (!data?.length) return <div className="empty">Not enough data to detect trends yet.</div>;
  return (
    <div>
      {data.map((t) => (
        <button key={t.keyword} className="trend" onClick={() => onPick(t.keyword)} title="Filter the feed by this topic">
          <span className="kw">{t.keyword}</span>
          <span className="growth" style={{ color: t.growth_pct > 0 ? "var(--text-primary)" : "var(--text-muted)" }}>
            {t.growth_pct > 0 ? "▲" : "▼"} {Math.abs(Math.round(t.growth_pct))}%
          </span>
          <span className="meta">
            {t.count} mentions · {t.sources} sources ·{" "}
            <i className="dot" style={{ background: t.avg_sentiment >= 0.25 ? SENT.positive.color : t.avg_sentiment <= -0.25 ? SENT.negative.color : SENT.neutral.color, width: 8, height: 8 }} />{" "}
            {t.avg_sentiment >= 0.25 ? "positive" : t.avg_sentiment <= -0.25 ? "negative" : "mixed"} tone
          </span>
        </button>
      ))}
    </div>
  );
}

export function Stories({ data }) {
  if (!data?.length) return <div className="empty">No multi-source stories found in this window.</div>;
  return (
    <div>
      {data.slice(0, 4).map((s) => (
        <div className="story" key={s.articles[0].id}>
          <h3>{s.headline}</h3>
          <div className="spread" style={{ marginBottom: 6 }}>
            {s.sources} outlets · tone spread {s.sentiment_spread.toFixed(2)}
            {s.sentiment_spread > 0.8 ? " — framing differs sharply" : ""}
          </div>
          {s.articles.map((a) => (
            <div className="srow" key={a.id}>
              <strong style={{ fontWeight: 600 }}>{a.source}</strong>
              <div>
                <a href={a.url} target="_blank" rel="noreferrer">{a.title}</a>
                <div className="pills"><SentimentPill label={a.sentiment_label} score={a.sentiment_score} /><BiasPill label={a.bias_label} score={a.bias_score} /></div>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

export function ArticleCard({ a, onKeyword, fresh }) {
  return (
    <article className={`article${fresh ? " fresh" : ""}`}>
      <div className="meta">
        <strong style={{ color: "var(--text-secondary)" }}>{a.source}</strong>
        <span>{timeAgo(a.published_at)}</span>
        {a.is_demo && <span className="demo-tag">demo data</span>}
      </div>
      <h3>{a.url.startsWith("http") && !a.is_demo ? <a href={a.url} target="_blank" rel="noreferrer">{a.title}</a> : a.title}</h3>
      {a.summary && <p>{a.summary}</p>}
      <div className="meta" style={{ marginBottom: 6 }}>
        <SentimentPill label={a.sentiment_label} score={a.sentiment_score} />
        <BiasPill label={a.bias_label} score={a.bias_score} />
        <span className="pill" title="Share of charged / loaded wording">Loaded language {Math.round(a.subjectivity * 100)}%</span>
      </div>
      <div className="kws">
        {a.keywords.slice(0, 6).map((k) => <button key={k} className="chip" onClick={() => onKeyword(k)}>#{k}</button>)}
      </div>
    </article>
  );
}

export function Feed({ items, total, filters, setFilters, sources, onMore, loading, freshIds }) {
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));
  return (
    <>
      <div className="filters">
        <input placeholder="Search headlines & summaries…" value={filters.q} onChange={set("q")} aria-label="Search" />
        <select value={filters.source} onChange={set("source")} aria-label="Source">
          <option value="">All sources</option>
          {sources.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select value={filters.sentiment} onChange={set("sentiment")} aria-label="Sentiment">
          <option value="">Any sentiment</option>
          {Object.entries(SENT).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        <select value={filters.bias} onChange={set("bias")} aria-label="Bias">
          <option value="">Any bias</option>
          {Object.entries(BIAS).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
        </select>
        {filters.keyword && (
          <button className="chip" onClick={() => setFilters((f) => ({ ...f, keyword: "" }))}>#{filters.keyword} ✕</button>
        )}
      </div>
      {items.map((a) => <ArticleCard key={a.id} a={a} fresh={freshIds.has(a.id)} onKeyword={(k) => setFilters((f) => ({ ...f, keyword: k }))} />)}
      {!items.length && !loading && <div className="empty">No articles match these filters.</div>}
      {items.length < total && (
        <button className="btn" onClick={onMore} disabled={loading} style={{ marginTop: 8 }}>
          {loading ? "Loading…" : `Load more (${total - items.length} left)`}
        </button>
      )}
    </>
  );
}

export function AnalyzePanel() {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async () => {
    setBusy(true); setErr("");
    try { setRes(await api.analyze({ title, text })); }
    catch (e) { setErr(e.message); setRes(null); }
    finally { setBusy(false); }
  };

  const pct = res ? ((res.sentiment_score + 1) / 2) * 100 : 50;
  const bpct = res ? ((res.bias_score + 1) / 2) * 100 : 50;
  return (
    <>
      <input className="in" style={{ width: "100%", marginBottom: 8, background: "var(--surface-0)", border: "1px solid var(--border)", borderRadius: 8, padding: "6px 10px" }}
        placeholder="Headline (optional)" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea className="in" placeholder="Paste any article text (20+ characters)…" value={text} onChange={(e) => setText(e.target.value)} />
      <button className="btn primary" onClick={run} disabled={busy || text.trim().length < 20}>{busy ? "Analyzing…" : "Analyze"}</button>
      {err && <div className="error" style={{ marginTop: 8 }}>{err}</div>}
      {res && (
        <div className="result">
          <div>
            <div style={{ marginBottom: 6 }}><SentimentPill label={res.sentiment_label} score={res.sentiment_score} /> <span style={{ color: "var(--text-muted)", fontSize: 12 }}>confidence {Math.round(res.sentiment_confidence * 100)}% · {res.token_count} tokens</span></div>
            <div className="meter"><span className="mid" /><span className="mark" style={{ left: `${pct}%` }} /></div>
            <div className="meter-labels"><span>Negative</span><span>Positive</span></div>
          </div>
          <div>
            <div style={{ marginBottom: 6 }}><BiasPill label={res.bias_label} score={res.bias_score} /> <span style={{ color: "var(--text-muted)", fontSize: 12 }}>loaded language {Math.round(res.subjectivity * 100)}% · {res.bias_method}</span></div>
            <div className="meter"><span className="mid" /><span className="mark" style={{ left: `${bpct}%` }} /></div>
            <div className="meter-labels"><span>Left</span><span>Right</span></div>
          </div>
          <div><strong>Summary</strong><p style={{ margin: "4px 0 0", color: "var(--text-secondary)" }}>{res.summary}</p></div>
          <div className="kws" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>{res.keywords.map((k) => <span className="chip" key={k}>#{k}</span>)}</div>
          <div style={{ color: "var(--text-muted)", fontSize: 12 }}>Models: {res.models.sentiment} · {res.models.summarizer}</div>
        </div>
      )}
    </>
  );
}
