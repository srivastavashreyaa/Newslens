"""NewsLens – interactive news aggregator & analyzer (Streamlit).

Run locally:   streamlit run streamlit_app.py
Deploy:        Streamlit Community Cloud / Docker / Render (see README).
"""
import inspect
import time
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

st.set_page_config(page_title="NewsLens · News Aggregator & Analyzer", page_icon="📰", layout="wide", initial_sidebar_state="expanded")

from ui import charts  # noqa: E402
from ui import data as D  # noqa: E402
from ui.theme import (BIAS_COLOR, BIAS_LABEL, NEG, POS, SENT_COLOR, SENT_LABEL, THEMES, bg_style, bias_badge, esc, grid_card,  # noqa: E402
                      highlight_loaded, inject_css, leaderboard_card, loaded_badge, sent_badge, side_item, ticker_html, time_ago, top_story_card)
from app.nlp.tokenization import split_sentences  # noqa: E402

now = D.utcnow()
st.session_state.setdefault("saved", set())
SPARK_OK = "chart_data" in inspect.signature(st.metric).parameters


def reset_filters():
    st.session_state.update(f_src=[], f_sent=[], f_bias=[], f_q="")


def toggle_save(aid: int):
    st.session_state.saved.symmetric_difference_update({aid})


# --------------------------------------------------------------------------- first-run bootstrap
if "booted" not in st.session_state:
    st.session_state.booted = True
    if D.db_version()[0] == 0:
        with st.spinner("First run: fetching live feeds and analyzing articles…"):
            res = D.run_ingest()
        if not res or res["new"] == 0:
            with st.spinner("Live feeds unreachable from here – loading demo data instead…"):
                D.ensure_demo()
            st.session_state.boot_note = "Live news feeds couldn't be reached, so demo data is shown. Use **Fetch latest** in the sidebar to retry."
    _d = D.load_df()
    if _d["is_demo"].any() and (_d[_d["is_demo"]]["image_url"].fillna("") == "").all():
        D.ensure_demo()  # demo data created by an older version has no artwork -> regenerate
    st.session_state.data_mode = "Live news" if (~D.load_df()["is_demo"]).any() else "Demo data"

df_all = D.load_df()

# --------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### 📰 NewsLens")
    st.caption("BERT-powered news aggregation & analysis")
    mode = st.radio("Data source", ["Live news", "Demo data"], key="data_mode", horizontal=True,
                    help="Live = real RSS feeds. Demo = fictional outlets & stories so the app works offline.")
    is_demo = mode == "Demo data"
    if is_demo and not df_all["is_demo"].any():
        D.ensure_demo()
        st.rerun()

    pool = df_all[df_all["is_demo"] == is_demo]
    window_label = st.select_slider("Time window", options=list(D.WINDOWS), value="7d", key="window", help="Metrics compare against the previous window of equal length.")
    hours = D.WINDOWS[window_label]
    sources = st.multiselect("Sources", sorted(pool["source"].unique()), placeholder="All sources", key="f_src")
    sentiments = st.pills("Sentiment", list(SENT_LABEL), selection_mode="multi", format_func=lambda k: SENT_LABEL[k], key="f_sent") or []
    biases = st.pills("Bias", list(BIAS_LABEL), selection_mode="multi", format_func=lambda k: BIAS_LABEL[k], key="f_bias") or []
    query = st.text_input("Search", placeholder="e.g. solar, chip, flood…", key="f_q")
    st.button("↺ Reset filters", on_click=reset_filters, width="stretch")

    st.divider()
    if not is_demo:
        if st.button("⟳ Fetch latest", width="stretch", type="primary"):
            with st.spinner("Fetching feeds & running NLP…"):
                res = D.run_ingest()
            if res is None:
                st.toast("Another fetch is already running.")
            elif res["new"]:
                st.toast(f"{res['new']} new articles analyzed", icon="✅")
                st.rerun()
            else:
                st.toast("No new articles (feeds unreachable or up to date).", icon="ℹ️")
        auto = st.toggle("Auto-refresh", value=True, help="Keep fetching new articles while this page is open.")
        interval = st.slider("Every (min)", 5, 60, 15, 5, disabled=not auto)
    else:
        auto, interval = False, 15
        if st.button("Clear demo data", width="stretch"):
            D.clear_demo()
            st.session_state.data_mode = "Live news"
            st.rerun()
    theme = st.selectbox("🎨 Accent theme", list(THEMES), key="theme")
    eng = D.nlp_engine()
    st.caption(f"🧠 Sentiment: `{eng.description['sentiment']}`  \n📝 Summaries: `{eng.description['summarizer']}`  \n⚖️ Bias: `{eng.description['bias']}`")

inject_css(theme)
base, cur, prev, note = D.apply_filters(df_all, demo=is_demo, sources=sources, sentiments=sentiments, biases=biases, query=query, hours=hours, now=now)
bucket = "hour" if (hours is not None and hours <= 48) else "day"

# --------------------------------------------------------------------------- ticker + title bar
ticker_rows = D.latest_rows(is_demo, 16)
if len(ticker_rows):
    st.markdown(ticker_html(ticker_rows.itertuples(), now), unsafe_allow_html=True)

active = [f"🔎 “{query}”"] if query.strip() else []
active += [f"📰 {s}" for s in sources] + [f"😀 {SENT_LABEL[s]}" for s in sentiments] + [f"⚖️ {BIAS_LABEL[b]}" for b in biases]
last = D.last_ingest()
chips = "".join(f'<span class="nl-chip filter">{esc(a)}</span>' for a in active)
st.markdown(
    f"""<div class="nl-hero"><h1>News<span>Lens</span></h1>
    <p>Aggregates news from multiple outlets, scores sentiment with DistilBERT, summarizes with DistilBART, estimates media bias and tracks which topics are heating up.</p>
    <div class="nl-pill-row"><span class="nl-chip live">{'Demo mode' if is_demo else 'Live feeds'}</span>
    <span class="nl-chip">{len(cur)} articles in window</span><span class="nl-chip">{cur['source'].nunique() if len(cur) else 0} sources</span>
    <span class="nl-chip">{'feeds checked ' + time_ago(datetime.fromtimestamp(last, timezone.utc).replace(tzinfo=None), now) if last else 'times in UTC'}</span>{chips}</div></div>""",
    unsafe_allow_html=True,
)
if msg := st.session_state.pop("boot_note", None):
    st.info(msg)

# --------------------------------------------------------------------------- empty states (explain *why* it is empty)
if not is_demo and not (~df_all["is_demo"]).any():
    st.markdown('<div class="nl-empty"><h3>📡 No live articles yet</h3><p>The live RSS feeds haven\'t returned anything yet (blocked network or first run).</p></div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    if c1.button("⟳ Fetch live news now", type="primary", width="stretch"):
        with st.spinner("Fetching…"):
            D.run_ingest()
        st.rerun()
    if c2.button("Use demo data", width="stretch"):
        st.session_state.data_mode = "Demo data"
        st.rerun()
    st.stop()

if cur.empty:
    why = "".join(f"<li>{esc(a)}</li>" for a in active) or "<li>the selected time window</li>"
    st.markdown(f'<div class="nl-empty"><h3>🔍 Nothing matches these filters</h3><p>Currently active:</p><ul style="display:inline-block;text-align:left;color:#c9cedb">{why}'
                f'<li>time window: {window_label}</li></ul></div>', unsafe_allow_html=True)
    c1, c2, _ = st.columns([1, 1, 2])
    c1.button("↺ Reset all filters", on_click=reset_filters, type="primary", width="stretch")
    if window_label != "All":
        c2.button("Show all time", on_click=lambda: st.session_state.update(window="All"), width="stretch")
    st.stop()
if note == "partial":
    st.info("No article contains **all** your search words, so these are the closest partial matches.")


# --------------------------------------------------------------------------- article details dialog
@st.dialog("Article details", width="large")
def show_article(aid: int):
    sub = df_all[df_all["id"] == aid]
    if sub.empty:
        st.warning("Article not found.")
        return
    r = next(sub.itertuples())
    st.markdown(top_story_card(r, D.utcnow(), r.source).replace("min-height:400px", ""), unsafe_allow_html=True)
    saved = r.id in st.session_state.saved
    b1, b2, _ = st.columns([1, 1, 2])
    b1.button("★ Saved" if saved else "☆ Save for later", key=f"dlg_save_{aid}", on_click=toggle_save, args=(aid,), width="stretch")
    if str(r.url).startswith("http") and not r.is_demo:
        b2.link_button("Open original ↗", r.url, width="stretch")
    st.success(r.summary or r.title)
    body = r.content or r.summary
    sents = split_sentences(body)[:40]
    if len(sents) > 1:
        st.markdown("**Sentiment flow** · hover a bar to read the sentence")
        scores = [D.nlp_engine().sentiment.score(x)[0] for x in sents]
        st.plotly_chart(charts.sentence_flow(sents, scores), width="stretch", key=f"dlg_flow_{aid}")
    st.markdown(" ".join(f"`#{k}`" for k in r.keywords))
    others = [c for c in D.clusters(cur) if any(a["id"] == aid for a in c["articles"])]
    if others:
        st.markdown(f"**Same story elsewhere** · {others[0]['sources']} outlets, framing gap {others[0]['sentiment_spread']:.2f}")
        st.dataframe(pd.DataFrame([{"Outlet": a["source"], "Headline": a["title"], "Sentiment": a["sentiment_score"], "Lean": BIAS_LABEL[a["bias_label"]]} for a in others[0]["articles"]]),
                     hide_index=True, width="stretch",
                     column_config={"Sentiment": st.column_config.ProgressColumn(min_value=-1, max_value=1, format="%+.2f")})


def render_grid(rows: pd.DataFrame, ctx: str, ncols: int = 3):
    cols = st.columns(ncols)
    for i, r in enumerate(rows.itertuples()):
        with cols[i % ncols]:
            st.markdown(grid_card(r, now), unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if b1.button("🔍 Details", key=f"{ctx}_d_{r.id}", width="stretch"):
                show_article(int(r.id))
            saved = r.id in st.session_state.saved
            b2.button("★ Saved" if saved else "☆ Save", key=f"{ctx}_s_{r.id}", on_click=toggle_save, args=(int(r.id),), width="stretch")


def dedupe(d: pd.DataFrame) -> pd.DataFrame:
    return d.assign(_k=d["title"].str.lower().str.strip()).drop_duplicates("_k").drop(columns="_k")


# --------------------------------------------------------------------------- top stories
st.markdown("#### 🔥 Top stories")
rank_mode = st.segmented_control("Rank by", ["Most covered", "Newest", "Most positive", "Most negative"], default="Most covered", key="rank_mode", label_visibility="collapsed") or "Most covered"
extras: dict[int, str] = {}
if rank_mode == "Most covered":
    cl = sorted(D.clusters(cur), key=lambda c: (-c["sources"], -c["sentiment_spread"]))
    ids = []
    for c in cl:
        rep = c["articles"][-1]["id"]
        ids.append(rep)
        extras[rep] = f'<span class="nl-badge">🗞️ {c["sources"]} outlets · framing gap {c["sentiment_spread"]:.2f}</span>'
    ranked = pd.concat([cur.set_index("id").loc[ids].reset_index() if ids else cur.iloc[0:0], cur.sort_values("published_at", ascending=False)])
    ranked = dedupe(ranked.drop_duplicates("id"))
else:
    order = {"Newest": ("published_at", False), "Most positive": ("sentiment_score", False), "Most negative": ("sentiment_score", True)}[rank_mode]
    ranked = dedupe(cur.sort_values(order[0], ascending=order[1]))
ranked = ranked.head(4)
hero = next(ranked.head(1).itertuples())
tl, tr = st.columns([1.7, 1])
with tl:
    st.markdown(top_story_card(hero, now, rank_mode if rank_mode != "Most covered" else "Top story", extras.get(hero.id, "")), unsafe_allow_html=True)
    if st.button("🔍 Open top story", key="hero_d"):
        show_article(int(hero.id))
with tr:
    for r in ranked.iloc[1:4].itertuples():
        st.markdown(side_item(r, now), unsafe_allow_html=True)
        if st.button("Details", key=f"side_d_{r.id}"):
            show_article(int(r.id))

# --------------------------------------------------------------------------- KPIs with sparklines
ts = cur.set_index("published_at").sort_index()
freq = "1h" if bucket == "hour" else "1D"
s_cnt = ts["id"].resample(freq).count().tolist()
s_avg = ts["sentiment_score"].resample(freq).mean().fillna(0).tolist()
s_neg = (ts["sentiment_label"].eq("negative").astype(float).resample(freq).mean().fillna(0) * 100).tolist()
s_sub = ts["subjectivity"].resample(freq).mean().fillna(0).tolist()


def spark(series, kind="area"):
    return dict(chart_data=series, chart_type=kind) if SPARK_OK and len(series) >= 2 else {}


avg = cur["sentiment_score"].mean()
pavg = prev["sentiment_score"].mean() if len(prev) else None
neg = (cur["sentiment_label"] == "negative").mean() * 100
pneg = (prev["sentiment_label"] == "negative").mean() * 100 if len(prev) else None
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Articles", len(cur), delta=(len(cur) - len(prev)) if len(prev) else None, help="vs previous window", **spark(s_cnt, "bar"))
k2.metric("Avg sentiment", f"{avg:+.2f}", delta=f"{avg - pavg:+.2f}" if pavg is not None else None, **spark(s_avg, "line"))
k3.metric("Negative coverage", f"{neg:.0f}%", delta=f"{neg - pneg:+.0f} pts" if pneg is not None else None, delta_color="inverse", **spark(s_neg, "area"))
k4.metric("Loaded language", f"{cur['subjectivity'].mean():.0%}", **spark(s_sub, "line"))
k5.metric("Avg bias lean", f"{cur['bias_score'].mean():+.2f}", help="−1 left … +1 right")


# --------------------------------------------------------------------------- live wire (auto-updating fragment)
@st.fragment(run_every="30s")
def live_wire(demo: bool, auto: bool, interval_min: int):
    st.session_state["wire_ticks"] = st.session_state.get("wire_ticks", 0) + 1
    # never ingest on the very first render – keep page loads fast
    if auto and not demo and st.session_state["wire_ticks"] > 1 and time.time() - D.last_ingest() > interval_min * 60:
        res = D.run_ingest()
        if res and res["new"] > 0:
            st.rerun()
    rows = D.latest_rows(demo, 6)
    n = D.utcnow()
    html = "".join(
        f'<div class="nl-wire-row"><span class="t">{time_ago(r.published_at, n)}</span><span class="s">{esc(r.source)}</span>'
        f'<span style="flex:1">{esc(r.title)}</span>{sent_badge(r.sentiment_label, r.sentiment_score)}</div>' for r in rows.itertuples())
    st.markdown(f'<div class="nl-wire">{html or "<div class=nl-sum>Nothing yet.</div>"}</div>', unsafe_allow_html=True)


tab_over, tab_explore, tab_out, tab_trend, tab_story, tab_feed, tab_saved, tab_an = st.tabs(
    ["🏠 Overview", "🧭 Explore", "⚖️ Outlets", "📈 Trends", "🔀 Stories", "📰 Feed", "⭐ Saved", "🧪 Analyze"])
src = D.source_table(cur)

# --------------------------------------------------------------------------- overview
with tab_over:
    g1, g2 = st.columns([1, 2.4])
    with g1:
        st.plotly_chart(charts.mood_gauge(avg), width="stretch", key="mood")
        st.plotly_chart(charts.donut(cur["sentiment_label"].value_counts().to_dict(), SENT_COLOR, SENT_LABEL, "articles"), width="stretch", key="d1")
    with g2:
        st.markdown("##### Sentiment over time")
        st.plotly_chart(charts.timeline(cur, bucket), width="stretch", key="timeline")
    if len(src):
        up, gl, ld, pr = src.loc[src["avg_sentiment"].idxmax()], src.loc[src["avg_sentiment"].idxmin()], src.loc[src["avg_subjectivity"].idxmax()], src.loc[src["count"].idxmax()]
        lb = st.columns(4)
        lb[0].markdown(leaderboard_card("😊 Most upbeat outlet", up["source"], f"avg sentiment {up['avg_sentiment']:+.2f}", POS), unsafe_allow_html=True)
        lb[1].markdown(leaderboard_card("😟 Most gloomy outlet", gl["source"], f"avg sentiment {gl['avg_sentiment']:+.2f}", NEG), unsafe_allow_html=True)
        lb[2].markdown(leaderboard_card("🔥 Most loaded language", ld["source"], f"{ld['avg_subjectivity']:.0%} charged wording", "#eb6834"), unsafe_allow_html=True)
        lb[3].markdown(leaderboard_card("📰 Most prolific", pr["source"], f"{int(pr['count'])} articles", "#9085e9"), unsafe_allow_html=True)
    h1, h2 = st.columns([1.3, 1])
    with h1:
        st.markdown("##### Outlet mood, day by day")
        st.plotly_chart(charts.source_day_heatmap(cur), width="stretch", key="heat")
    with h2:
        st.markdown("##### When news is published")
        st.plotly_chart(charts.hour_heatmap(cur), width="stretch", key="hour")
        st.plotly_chart(charts.donut(cur["bias_label"].value_counts().to_dict(), BIAS_COLOR, BIAS_LABEL, "articles"), width="stretch", key="d2")
    st.markdown("##### ⚡ Live wire")
    live_wire(is_demo, auto, interval)

# --------------------------------------------------------------------------- explore
with tab_explore:
    st.markdown("##### How coverage flows: outlet → sentiment → bias")
    st.caption("Hover a band to see the counts. Wider = more articles.")
    st.plotly_chart(charts.sankey(cur), width="stretch", key="sankey")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("##### Sunburst · click a slice to zoom")
        st.plotly_chart(charts.sunburst(cur), width="stretch", key="sun")
    with e2:
        st.markdown("##### Sentiment race · press ▶ Play")
        st.plotly_chart(charts.race(cur), width="stretch", key="race")

# --------------------------------------------------------------------------- outlets
with tab_out:
    a, b = st.columns([1.5, 1])
    with a:
        st.markdown("##### Lean vs tone · click or box-select outlets to drill in")
        ev = st.plotly_chart(charts.bias_bubble(src), width="stretch", on_select="rerun", selection_mode=["points", "box"], key="bias_sel")
    with b:
        st.markdown("##### Compare outlets (radar)")
        picks = st.multiselect("Outlets", list(src["source"]), default=list(src["source"])[:4], key="radar_pick", label_visibility="collapsed")
        st.plotly_chart(charts.radar(src, picks), width="stretch", key="radar")
    picked = [src.iloc[p["point_index"]]["source"] for p in (ev.selection.points if ev and ev.selection else []) if p.get("point_index", 99) < len(src)]
    st.markdown("##### Loaded language by outlet")
    st.plotly_chart(charts.loaded_bars(src), width="stretch", key="loaded")
    st.markdown("##### Scorecard")
    st.dataframe(
        src.rename(columns={"source": "Outlet", "count": "Articles", "avg_sentiment": "Avg sentiment", "avg_bias": "Bias lean", "avg_subjectivity": "Loaded language", "pct_negative": "% negative"}),
        hide_index=True, width="stretch",
        column_config={"Avg sentiment": st.column_config.ProgressColumn(min_value=-1, max_value=1, format="%+.2f"),
                       "Bias lean": st.column_config.ProgressColumn(min_value=-1, max_value=1, format="%+.2f"),
                       "Loaded language": st.column_config.ProgressColumn(min_value=0, max_value=1, format="percent"),
                       "% negative": st.column_config.NumberColumn(format="%.0f%%")})
    if picked:
        st.markdown(f"##### Latest from {', '.join(picked)}")
        render_grid(cur[cur["source"].isin(picked)].head(6), "out")
    else:
        st.caption("Tip: select bubbles above to see those outlets' latest articles here.")

# --------------------------------------------------------------------------- trends
with tab_trend:
    kw = D.keyword_table(cur, prev if hours else cur.iloc[0:0])
    a, b = st.columns(2)
    with a:
        st.markdown("##### Momentum vs previous window")
        st.plotly_chart(charts.momentum_bars(kw), width="stretch", key="mom")
    with b:
        st.markdown("##### Topic map · size = mentions, color = tone")
        st.plotly_chart(charts.topic_treemap(kw), width="stretch", key="tree")
    if len(kw):
        st.markdown("##### Drill into a topic")
        topic = st.segmented_control("Topic", list(kw["keyword"].head(12)), default=kw["keyword"].iloc[0], label_visibility="collapsed", key="topic_pick")
        if topic:
            row = kw[kw["keyword"] == topic]
            if len(row):
                row = row.iloc[0]
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Mentions", int(row["count"]), delta=int(row["count"] - row["previous"]))
                m2.metric("Momentum", f"{row['growth_pct']:+.0f}%")
                m3.metric("Outlets covering", int(row["sources"]))
                m4.metric("Tone", f"{row['avg_sentiment']:+.2f}")
                st.plotly_chart(charts.keyword_timeline(cur, topic, bucket), width="stretch", key="kwt")
                render_grid(dedupe(cur[cur["keywords"].apply(lambda ks: topic in ks)]).head(3), "trend")

# --------------------------------------------------------------------------- stories
with tab_story:
    st.caption("Articles from different outlets about the same story (TF-IDF similarity within 24h), compared side by side.")
    cl = D.clusters(cur)
    if not cl:
        st.info("No stories covered by 2+ outlets in this window. Try a wider window or more sources.")
    else:
        order = st.segmented_control("Sort", ["Most outlets", "Biggest framing gap"], default="Biggest framing gap", key="story_sort")
        cl = sorted(cl, key=(lambda c: -c["sentiment_spread"]) if order == "Biggest framing gap" else (lambda c: (-c["sources"], -c["sentiment_spread"])))
        i = st.selectbox("Story", range(len(cl)), format_func=lambda k: f"{cl[k]['headline'][:90]}  ·  {cl[k]['sources']} outlets · gap {cl[k]['sentiment_spread']:.2f}")
        c = cl[i]
        a, b = st.columns([1.2, 1])
        with a:
            st.plotly_chart(charts.story_strip(c["articles"]), width="stretch", key="strip")
        with b:
            st.metric("Framing gap", f"{c['sentiment_spread']:.2f}", help="Max − min sentiment across outlets (0–2)")
            st.markdown(" ".join(f"`{esc(k)}`" for k in c["keywords"]))
        cols = st.columns(min(len(c["articles"]), 3))
        for j, art in enumerate(c["articles"]):
            full = df_all[df_all["id"] == art["id"]]
            img = full.iloc[0]["image_url"] if len(full) else ""
            with cols[j % len(cols)]:
                st.markdown(
                    f'<div class="nl-gcard"><div class="nl-img" style="height:110px;{bg_style(img, art["source"])}"><span class="src">{esc(art["source"])}</span></div><div class="nl-gbody">'
                    f'<span class="nl-title">{esc(art["title"])}</span><div class="nl-badges">{sent_badge(art["sentiment_label"], art["sentiment_score"])}'
                    f'{bias_badge(art["bias_label"], art["bias_score"])}{loaded_badge(art["subjectivity"])}</div></div></div>', unsafe_allow_html=True)

# --------------------------------------------------------------------------- feed
with tab_feed:
    f1, f2, f3 = st.columns([2.2, 1, 1])
    sort = f1.segmented_control("Sort by", ["Newest", "Most negative", "Most positive", "Most loaded"], default="Newest", key="feed_sort") or "Newest"
    imgs_only = f2.toggle("With images only", value=False)
    cols_n = f3.select_slider("Columns", [2, 3, 4], value=3)
    ordered = {"Newest": cur.sort_values("published_at", ascending=False), "Most negative": cur.sort_values("sentiment_score"),
               "Most positive": cur.sort_values("sentiment_score", ascending=False), "Most loaded": cur.sort_values("subjectivity", ascending=False)}[sort]
    if imgs_only:
        ordered = ordered[ordered["image_url"].fillna("") != ""]
    shown = st.session_state.setdefault("feed_n", 12)
    st.caption(f"{len(ordered)} articles")
    render_grid(ordered.head(shown), "feed", cols_n)
    if shown < len(ordered) and st.button(f"Show more ({len(ordered) - shown} left)", key="more"):
        st.session_state.feed_n += 12
        st.rerun()

# --------------------------------------------------------------------------- saved
with tab_saved:
    saved_ids = st.session_state.saved
    sv = df_all[df_all["id"].isin(saved_ids)]
    if sv.empty:
        st.info("Nothing saved yet. Press **☆ Save** on any article card to keep it here (for this session).")
    else:
        st.caption(f"{len(sv)} saved articles")
        st.button("Clear saved", on_click=lambda: st.session_state.saved.clear())
        render_grid(sv.sort_values("published_at", ascending=False), "saved")

# --------------------------------------------------------------------------- analyze
SAMPLES = {
    "😊 Upbeat": ("Council approves new riverside park", "The city council approved a new riverside park on Tuesday. Residents are delighted by the plan. Volunteers praised the brilliant design and the joyful community spirit. Construction begins next spring and will create dozens of jobs."),
    "😟 Alarming": ("Flood fears grow", "Heavy rain is threatening riverside homes and officials are accused of acting too late. Residents say they feel abandoned and terrified of another devastating disaster. Critics slammed the response as a shameful failure."),
    "😐 Neutral": ("Central bank holds rates", "The central bank held interest rates steady on Wednesday. Officials said inflation is easing gradually and hiring remains stable. Markets reacted calmly to the decision."),
}
with tab_an:
    st.caption("Run the NLP pipeline on any text, or inspect a collected article. The sentence chart shows where the tone shifts.")
    src_mode = st.segmented_control("Input", ["Paste text", "Pick a collected article"], default="Paste text", key="an_mode")
    title = text = source = ""
    if src_mode == "Pick a collected article":
        opts = cur.head(60)
        k = st.selectbox("Article", range(len(opts)), format_func=lambda i: f"{opts.iloc[i]['source']} — {opts.iloc[i]['title'][:90]}")
        r = opts.iloc[k]
        title, text, source = r["title"], (r["content"] or r["summary"]), r["source"]
    else:
        sc = st.columns(len(SAMPLES) + 1)
        for col, (name, (t, x)) in zip(sc, SAMPLES.items()):
            if col.button(name, width="stretch"):
                st.session_state.an_title, st.session_state.an_text = t, x
        title = st.text_input("Headline (optional)", key="an_title")
        text = st.text_area("Article text", key="an_text", height=150, placeholder="Paste an article (20+ characters)…")
        source = st.selectbox("Outlet (adds its editorial-lean prior)", ["(none)"] + [f["name"] for f in D.load_feeds()])
        source = "" if source == "(none)" else source

    if len(text.strip()) >= 20:
        eng = D.nlp_engine()
        with st.spinner("Analyzing…"):
            res = eng.analyze(title, text, D.source_priors().get(source, 0.0))
            sents = split_sentences(text)[:40]
            scores = [eng.sentiment.score(s)[0] for s in sents]
        g1, g2, g3 = st.columns([1, 1, 1.3])
        g1.plotly_chart(charts.gauge(res.sentiment_score, f"Sentiment · {SENT_LABEL[res.sentiment_label]}"), width="stretch", key="g1")
        g2.plotly_chart(charts.gauge(res.bias_score, f"Bias · {BIAS_LABEL[res.bias_label]}", "bias"), width="stretch", key="g2")
        with g3:
            st.metric("Loaded language", f"{res.subjectivity:.0%}")
            st.metric("BERT tokens", res.token_count)
            st.caption(f"Confidence {res.sentiment_confidence:.0%} · method `{res.bias_method}`")
        st.markdown("**Summary**")
        st.success(res.summary or "—")
        st.markdown(" ".join(f"`#{k}`" for k in res.keywords))
        if sents:
            st.markdown("**Sentiment flow** · hover a bar to read the sentence")
            st.plotly_chart(charts.sentence_flow(sents, scores), width="stretch", key="flow")
        st.markdown("**Loaded wording highlighted**")
        st.markdown(f'<div class="nl-card" style="line-height:1.7">{highlight_loaded(text, D.LOADED)}</div>', unsafe_allow_html=True)

st.divider()
st.caption("Built with Streamlit · Plotly · Hugging Face Transformers (DistilBERT / DistilBART) · times in UTC. Bias direction uses outlet priors in backend/app/feeds.json unless a fine-tuned BERT model is configured.")
