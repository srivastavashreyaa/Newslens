import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { SentimentTimeline, SourceBias, SourceSentiment, SourceTable } from "./components/Charts";
import { AnalyzePanel, Feed, Stories, Trends } from "./components/Panels";
import { fmtSigned, timeAgo } from "./components/common";
import { useLive } from "./useLive";

const WINDOWS = [["24h", 24], ["3d", 72], ["7d", 168]];
const EMPTY = { q: "", source: "", sentiment: "", bias: "", keyword: "" };
const PAGE = 15;

export default function App() {
  const [hours, setHours] = useState(168);
  const bucket = hours <= 72 ? "hour" : "day";
  const [overview, setOverview] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [sources, setSources] = useState([]);
  const [trends, setTrends] = useState([]);
  const [stories, setStories] = useState([]);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState("");

  const [filters, setFilters] = useState(EMPTY);
  const [feed, setFeed] = useState({ items: [], total: 0 });
  const [loading, setLoading] = useState(false);
  const [fresh, setFresh] = useState(new Set());
  const [pending, setPending] = useState(0);
  const [ingesting, setIngesting] = useState(false);
  const refreshTimer = useRef();

  const loadStats = useCallback(async () => {
    try {
      const [o, t, s, tr, st, h] = await Promise.all([
        api.overview(hours), api.timeline(hours, bucket), api.sources(hours), api.trends(Math.min(hours, 72)), api.stories(Math.max(hours, 48)), api.health(),
      ]);
      setOverview(o); setTimeline(t); setSources(s); setTrends(tr); setStories(st); setHealth(h); setError("");
    } catch (e) {
      setError(`Cannot reach the API (${e.message}). Is the backend running on port 8000?`);
    }
  }, [hours, bucket]);

  const loadFeed = useCallback(async (offset = 0) => {
    setLoading(true);
    try {
      const r = await api.articles({ ...filters, hours, limit: PAGE, offset });
      setFeed((prev) => ({ total: r.total, items: offset ? [...prev.items, ...r.items] : r.items }));
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, [filters, hours]);

  useEffect(() => { loadStats(); }, [loadStats]);
  useEffect(() => {
    const id = setTimeout(() => loadFeed(0), filters.q ? 250 : 0); // debounce search typing
    return () => clearTimeout(id);
  }, [loadFeed, filters.q]);

  const status = useLive((article) => {
    setFresh((s) => new Set(s).add(article.id));
    const unfiltered = Object.values(filters).every((v) => !v);
    if (unfiltered) setFeed((f) => ({ total: f.total + 1, items: [article, ...f.items.filter((x) => x.id !== article.id)] }));
    else setPending((n) => n + 1);
    clearTimeout(refreshTimer.current);
    refreshTimer.current = setTimeout(loadStats, 1500); // batch chart refreshes while a feed is streaming in
  });

  const ingest = async () => {
    setIngesting(true);
    try { await api.ingest(); await loadStats(); await loadFeed(0); }
    catch (e) { setError(e.message); }
    finally { setIngesting(false); }
  };

  const o = overview;
  const negPct = o && o.articles ? Math.round((100 * o.sentiment.negative) / o.articles) : 0;
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>NewsLens</h1>
          <p>Multi-source news aggregation with BERT-powered sentiment, summaries and bias analysis</p>
        </div>
        <div className="controls">
          <span className="live" data-status={status}><i className="dot" />{status === "live" ? "Live" : status === "connecting" ? "Connecting…" : "Offline"}</span>
          <div className="seg" role="group" aria-label="Time window">
            {WINDOWS.map(([l, h]) => <button key={l} aria-pressed={hours === h} onClick={() => setHours(h)}>{l}</button>)}
          </div>
          <button className="btn" onClick={ingest} disabled={ingesting}>{ingesting ? "Fetching feeds…" : "Fetch latest"}</button>
        </div>
      </header>

      {error && <div className="banner" style={{ borderLeftColor: "var(--neg)" }}>{error}</div>}

      <section className="kpis">
        <div className="kpi"><div className="label">Articles analyzed</div><div className="value">{o?.articles ?? "–"}</div><div className="note">from {o?.sources ?? 0} sources</div></div>
        <div className="kpi"><div className="label">Average sentiment</div><div className="value">{o ? fmtSigned(o.avg_sentiment) : "–"}</div><div className="note">−1 negative … +1 positive</div></div>
        <div className="kpi"><div className="label">Negative coverage</div><div className="value">{o ? `${negPct}%` : "–"}</div><div className="note">{o?.sentiment.negative ?? 0} negative · {o?.sentiment.positive ?? 0} positive</div></div>
        <div className="kpi"><div className="label">Loaded language</div><div className="value">{o ? `${Math.round(o.avg_subjectivity * 100)}%` : "–"}</div><div className="note">avg charged-wording score</div></div>
        <div className="kpi"><div className="label">Latest article</div><div className="value" style={{ fontSize: 22 }}>{o ? timeAgo(o.latest) : "–"}</div><div className="note" title={JSON.stringify(health?.models)}>{health ? `${health.models.sentiment} · ${health.models.summarizer}` : ""}</div></div>
      </section>

      <div className="grid">
        <section className="card span-8">
          <h2>Sentiment over time</h2>
          <p className="sub">DistilBERT sentiment across all sources, by {bucket}</p>
          <SentimentTimeline data={timeline} bucket={bucket} />
        </section>
        <section className="card span-4">
          <h2>Trending topics</h2>
          <p className="sub">Keyword momentum vs the previous period · click to filter the feed</p>
          <Trends data={trends} onPick={(k) => { setFilters({ ...EMPTY, keyword: k }); document.getElementById("feed")?.scrollIntoView({ behavior: "smooth" }); }} />
        </section>

        <section className="card span-6">
          <h2>Tone by source</h2>
          <p className="sub">Average sentiment of each outlet's coverage</p>
          <SourceSentiment data={sources} />
        </section>
        <section className="card span-6">
          <h2>Media bias by source</h2>
          <p className="sub">Editorial lean (−1 left … +1 right)</p>
          <SourceBias data={sources} />
          <SourceTable data={sources} />
        </section>

        <section className="card span-7">
          <h2>Same story, different framing</h2>
          <p className="sub">Articles from different outlets clustered by TF-IDF similarity, with each outlet's sentiment and bias</p>
          <Stories data={stories} />
        </section>
        <section className="card span-5">
          <h2>Analyze any text</h2>
          <p className="sub">Run the NLP pipeline on an article you paste in</p>
          <AnalyzePanel />
        </section>

        <section className="card span-12" id="feed">
          <h2>Latest articles</h2>
          <p className="sub">{feed.total} matching · newest first</p>
          {pending > 0 && (
            <div className="banner"><span>{pending} new article{pending > 1 ? "s" : ""} arrived while filtered</span>
              <button className="btn" onClick={() => { setPending(0); loadFeed(0); }}>Refresh</button></div>
          )}
          <Feed items={feed.items} total={feed.total} filters={filters} setFilters={setFilters}
            sources={sources.map((s) => s.source).sort()} loading={loading} freshIds={fresh}
            onMore={() => loadFeed(feed.items.length)} />
        </section>
      </div>
    </div>
  );
}
