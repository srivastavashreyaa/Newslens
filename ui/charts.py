"""Plotly figure builders (dark theme, hover-rich, click-selectable where useful)."""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .theme import (BG, BIAS_COLOR, BIAS_LABEL, CATEGORICAL, CENTER, DIVERGING, LEFT, NEG, NEU, POS, RIGHT, SENT_COLOR, SENT_LABEL)

FONT = dict(family="Inter, system-ui, sans-serif", color="#c9cedb", size=12)
GRID = "rgba(255,255,255,0.07)"


def _style(fig, height=340, **kw):
    opts = dict(
        template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=FONT,
        height=height, margin=dict(l=10, r=10, t=30, b=10),
        hoverlabel=dict(bgcolor="#1b2233", bordercolor="#3a4258", font_size=12),
    )
    opts.update(kw)  # caller overrides (e.g. margin)
    fig.update_layout(**opts)
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(255,255,255,.15)")
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="rgba(255,255,255,.15)")
    return fig


def empty_fig(msg="No data for the current filters", height=300):
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=14, color="#7f88a0"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return _style(fig, height)


def timeline(df: pd.DataFrame, bucket: str) -> go.Figure:
    if df.empty:
        return empty_fig(height=470)
    freq = "1h" if bucket == "hour" else "1D"
    g = df.set_index("published_at").sort_index()
    avg = g["sentiment_score"].resample(freq).mean()
    n = g["id"].resample(freq).count()
    cnt = g.groupby([pd.Grouper(freq=freq), "sentiment_label"]).size().unstack(fill_value=0)
    for k in ("negative", "neutral", "positive"):
        if k not in cnt:
            cnt[k] = 0

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.5, 0.5], vertical_spacing=0.07,
                        subplot_titles=("Average sentiment (−1 … +1)", "Articles by sentiment"))
    fig.add_trace(go.Scatter(x=avg.index, y=avg.values, mode="lines+markers", name="Avg sentiment", customdata=n.values,
                             line=dict(color="#e8eaf0", width=2.5, shape="spline", smoothing=0.6), marker=dict(size=7, line=dict(width=2, color=BG)),
                             fill="tozeroy", fillcolor="rgba(109,167,236,0.10)", connectgaps=True,
                             hovertemplate="Avg sentiment <b>%{y:+.2f}</b> · %{customdata} articles<extra></extra>"), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,.25)", width=1), row=1, col=1)
    for k in ("negative", "neutral", "positive"):
        fig.add_trace(go.Bar(x=cnt.index, y=cnt[k], name=SENT_LABEL[k], marker=dict(color=SENT_COLOR[k], line=dict(color=BG, width=2)),
                             hovertemplate=f"{SENT_LABEL[k]}: <b>%{{y}}</b><extra></extra>"), row=2, col=1)
    fig.update_layout(barmode="stack", hovermode="x unified", legend=dict(orientation="h", y=-0.16, x=0))
    fig.update_yaxes(range=[-1, 1], row=1, col=1)
    fig.update_annotations(font=dict(size=12, color="#8e95a8"), x=0, xanchor="left")
    return _style(fig, 490, margin=dict(l=10, r=10, t=30, b=50))


def donut(counts: dict, colors: dict, labels: dict, title: str) -> go.Figure:
    keys = [k for k in colors if counts.get(k, 0) > 0]
    if not keys:
        return empty_fig(height=260)
    fig = go.Figure(go.Pie(labels=[labels[k] for k in keys], values=[counts[k] for k in keys], hole=0.62, sort=False,
                           marker=dict(colors=[colors[k] for k in keys], line=dict(color=BG, width=3)), textinfo="percent",
                           hovertemplate="%{label}: <b>%{value}</b> (%{percent})<extra></extra>", pull=[0.02] * len(keys)))
    fig.add_annotation(text=f"<b>{sum(counts.values())}</b><br><span style='font-size:11px;color:#8e95a8'>{title}</span>", showarrow=False, font=dict(size=20))
    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.05, x=0.5, xanchor="center"))
    return _style(fig, 270, margin=dict(l=0, r=0, t=10, b=10))


def source_day_heatmap(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_fig(height=300)
    d = df.assign(day=df["published_at"].dt.floor("D"))
    piv = d.pivot_table(index="source", columns="day", values="sentiment_score", aggfunc="mean")
    cnt = d.pivot_table(index="source", columns="day", values="id", aggfunc="count").reindex_like(piv)
    fig = go.Figure(go.Heatmap(z=piv.values, x=piv.columns, y=piv.index, zmin=-1, zmax=1, colorscale=DIVERGING, xgap=3, ygap=3,
                               customdata=cnt.values, colorbar=dict(title="Avg", thickness=10, len=0.8),
                               hovertemplate="<b>%{y}</b><br>%{x|%b %d}<br>Avg sentiment %{z:+.2f} · %{customdata} articles<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    return _style(fig, max(260, 46 * len(piv) + 70))


def bias_bubble(src: pd.DataFrame, selected: list[int] | None = None) -> go.Figure:
    if src.empty:
        return empty_fig(height=430)
    fig = go.Figure()
    for x0, x1, c, name in ((-1, -0.25, LEFT, "LEFT"), (-0.25, 0.25, CENTER, "CENTER"), (0.25, 1, RIGHT, "RIGHT")):
        fig.add_vrect(x0=x0, x1=x1, fillcolor=c, opacity=0.07, line_width=0, layer="below")
        fig.add_annotation(x=(x0 + x1) / 2, y=1.0, yref="paper", text=name, showarrow=False, font=dict(size=11, color=c), yanchor="bottom")
    colors = [LEFT if b <= -0.25 else RIGHT if b >= 0.25 else CENTER for b in src["avg_bias"]]
    size = 18 + 46 * (src["count"] / src["count"].max())
    fig.add_trace(go.Scatter(
        x=src["avg_bias"], y=src["avg_sentiment"], mode="markers+text", text=src["source"], textposition="top center",
        marker=dict(size=size, color=colors, opacity=0.9, line=dict(width=2.5, color="#fff")),
        selectedpoints=selected, unselected=dict(marker=dict(opacity=0.25)),
        customdata=src[["count", "avg_subjectivity", "pct_negative"]].values,
        hovertemplate="<b>%{text}</b><br>Bias %{x:+.2f} · Sentiment %{y:+.2f}<br>%{customdata[0]} articles · loaded language %{customdata[1]:.0%}"
                      "<br>%{customdata[2]:.0f}% negative<extra></extra>"))
    fig.add_hline(y=0, line=dict(color="rgba(255,255,255,.25)", width=1))
    fig.update_xaxes(range=[-1, 1], title="← Left        Editorial lean        Right →")
    fig.update_yaxes(range=[-1, 1], title="Average sentiment")
    return _style(fig, 430, clickmode="event+select", dragmode="select", margin=dict(l=10, r=10, t=40, b=10))


def loaded_bars(src: pd.DataFrame) -> go.Figure:
    if src.empty:
        return empty_fig(height=300)
    s = src.sort_values("avg_subjectivity")
    fig = go.Figure(go.Bar(x=s["avg_subjectivity"], y=s["source"], orientation="h",
                           marker=dict(color=s["avg_subjectivity"], colorscale=[[0, "#3a4258"], [1, RIGHT]], line=dict(color=BG, width=2)),
                           hovertemplate="<b>%{y}</b><br>Loaded language %{x:.0%}<extra></extra>"))
    fig.update_xaxes(tickformat=".0%", rangemode="tozero")
    return _style(fig, max(260, 44 * len(s) + 50))


def momentum_bars(kw: pd.DataFrame, top: int = 12) -> go.Figure:
    if kw.empty:
        return empty_fig("Not enough repeated topics yet", 380)
    k = kw.head(top).iloc[::-1]
    fig = go.Figure(go.Bar(x=k["growth_pct"], y=k["keyword"], orientation="h",
                           marker=dict(color=k["avg_sentiment"], colorscale=DIVERGING, cmin=-1, cmax=1, line=dict(color=BG, width=2),
                                       colorbar=dict(title="Tone", thickness=10, len=0.7)),
                           customdata=k[["count", "previous", "sources", "avg_sentiment"]].values,
                           hovertemplate="<b>%{y}</b><br>%{customdata[0]} mentions (was %{customdata[1]})<br>%{customdata[2]} sources · tone %{customdata[3]:+.2f}"
                                         "<br>Momentum <b>%{x:+.0f}%</b><extra></extra>"))
    fig.update_xaxes(ticksuffix="%")
    return _style(fig, 380)


def topic_treemap(kw: pd.DataFrame, top: int = 40) -> go.Figure:
    if kw.empty:
        return empty_fig("Not enough repeated topics yet", 380)
    k = kw.sort_values("count", ascending=False).head(top)
    fig = go.Figure(go.Treemap(labels=k["keyword"], parents=[""] * len(k), values=k["count"], customdata=k[["avg_sentiment", "sources"]].values,
                               marker=dict(colors=k["avg_sentiment"], colorscale=DIVERGING, cmin=-1, cmax=1, line=dict(width=3, color=BG)),
                               texttemplate="<b>%{label}</b><br>%{value}", textfont=dict(size=14),
                               hovertemplate="<b>%{label}</b><br>%{value} mentions · %{customdata[1]} sources<br>Tone %{customdata[0]:+.2f}<extra></extra>"))
    return _style(fig, 380, margin=dict(l=0, r=0, t=10, b=0))


def keyword_timeline(df: pd.DataFrame, keyword: str, bucket: str) -> go.Figure:
    d = df[df["keywords"].apply(lambda ks: keyword in ks)]
    if d.empty:
        return empty_fig(height=260)
    freq = "1h" if bucket == "hour" else "1D"
    g = d.set_index("published_at").sort_index()
    n = g["id"].resample(freq).count()
    tone = g["sentiment_score"].resample(freq).mean()
    fig = go.Figure(go.Bar(x=n.index, y=n.values, customdata=tone.values,
                           marker=dict(color=tone.values, colorscale=DIVERGING, cmin=-1, cmax=1, line=dict(color=BG, width=2)),
                           hovertemplate="%{y} mentions · tone %{customdata:+.2f}<extra></extra>"))
    fig.update_layout(hovermode="x unified")
    return _style(fig, 260)


def story_strip(articles: list[dict]) -> go.Figure:
    a = sorted(articles, key=lambda x: x["sentiment_score"])
    fig = go.Figure()
    fig.add_vline(x=0, line=dict(color="rgba(255,255,255,.25)", width=1))
    fig.add_trace(go.Scatter(
        x=[x["sentiment_score"] for x in a], y=[x["source"] for x in a], mode="markers+text",
        text=[BIAS_LABEL[x["bias_label"]] for x in a], textposition="middle right",
        marker=dict(size=[16 + 30 * x["subjectivity"] for x in a], color=[SENT_COLOR[x["sentiment_label"]] for x in a], line=dict(width=2, color="#fff")),
        customdata=[[x["title"], x["subjectivity"]] for x in a],
        hovertemplate="<b>%{y}</b><br>%{customdata[0]}<br>Sentiment %{x:+.2f} · loaded %{customdata[1]:.0%}<extra></extra>"))
    fig.update_xaxes(range=[-1.15, 1.9], title="Sentiment (marker size = loaded language)")
    return _style(fig, 90 + 52 * len(a), showlegend=False)


def gauge(value: float, title: str, kind: str = "sentiment") -> go.Figure:
    lo, mid, hi = (NEG, NEU, POS) if kind == "sentiment" else (LEFT, CENTER, RIGHT)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=value, number=dict(valueformat="+.2f", font=dict(size=34)), title=dict(text=title, font=dict(size=14, color="#aab0c0")),
        gauge=dict(axis=dict(range=[-1, 1], tickvals=[-1, -0.5, 0, 0.5, 1]), bar=dict(color="rgba(0,0,0,0)", thickness=0.0), bgcolor="rgba(0,0,0,0)", borderwidth=0,
                   threshold=dict(line=dict(color="#ffffff", width=5), thickness=0.95, value=value),
                   steps=[dict(range=[-1, -0.25], color=lo), dict(range=[-0.25, 0.25], color=mid), dict(range=[0.25, 1], color=hi)])))
    return _style(fig, 230, margin=dict(l=20, r=20, t=40, b=0))


def sentence_flow(sentences: list[str], scores: list[float]) -> go.Figure:
    colors = [POS if s >= 0.25 else NEG if s <= -0.25 else NEU for s in scores]
    fig = go.Figure(go.Bar(x=list(range(1, len(scores) + 1)), y=scores, marker=dict(color=colors, line=dict(color=BG, width=2)),
                           customdata=[s if len(s) < 160 else s[:157] + "…" for s in sentences],
                           hovertemplate="Sentence %{x} · <b>%{y:+.2f}</b><br>%{customdata}<extra></extra>"))
    fig.update_xaxes(title="Sentence #", dtick=1)
    fig.update_yaxes(range=[-1, 1], title="Sentiment")
    return _style(fig, 260)


def _rgba(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def mood_label(v: float) -> str:
    return "Gloomy" if v < -0.45 else "Tense" if v < -0.15 else "Balanced" if v < 0.15 else "Upbeat" if v < 0.45 else "Euphoric"


def mood_gauge(avg: float) -> go.Figure:
    """News Mood Index: avg sentiment (-1..1) mapped to 0..100."""
    val = round((avg + 1) * 50)
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=val, number=dict(font=dict(size=46)),
        title=dict(text=f"News Mood Index · <b>{mood_label(avg)}</b>", font=dict(size=14, color="#aab0c0")),
        gauge=dict(axis=dict(range=[0, 100], tickvals=[0, 25, 50, 75, 100]), bar=dict(color="rgba(0,0,0,0)", thickness=0),
                   bgcolor="rgba(0,0,0,0)", borderwidth=0,
                   threshold=dict(line=dict(color="#ffffff", width=5), thickness=0.95, value=val),
                   steps=[dict(range=[0, 25], color=NEG), dict(range=[25, 42], color="#a05a66"), dict(range=[42, 58], color="#4a4d57"),
                          dict(range=[58, 75], color="#4a74b0"), dict(range=[75, 100], color=POS)])))
    return _style(fig, 250, margin=dict(l=25, r=25, t=50, b=0))


def sankey(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_fig(height=420)
    srcs = sorted(df["source"].unique())
    sents, biases = ["positive", "neutral", "negative"], ["left", "center", "right"]
    labels = srcs + [SENT_LABEL[x] for x in sents] + [BIAS_LABEL[x] for x in biases]
    colors = [CATEGORICAL[i % len(CATEGORICAL)] for i in range(len(srcs))] + [SENT_COLOR[x] for x in sents] + [BIAS_COLOR[x] for x in biases]
    si = {s: i for i, s in enumerate(srcs)}
    ti = {s: len(srcs) + i for i, s in enumerate(sents)}
    bi = {b: len(srcs) + 3 + i for i, b in enumerate(biases)}
    sources_, targets, values, lcol = [], [], [], []
    for (s, t), n in df.groupby(["source", "sentiment_label"]).size().items():
        sources_.append(si[s]); targets.append(ti[t]); values.append(int(n)); lcol.append(_rgba(colors[si[s]], 0.35))
    for (t, b), n in df.groupby(["sentiment_label", "bias_label"]).size().items():
        sources_.append(ti[t]); targets.append(bi[b]); values.append(int(n)); lcol.append(_rgba(SENT_COLOR[t], 0.35))
    fig = go.Figure(go.Sankey(
        arrangement="snap", node=dict(label=labels, color=colors, pad=18, thickness=16, line=dict(color=BG, width=1),
                                      hovertemplate="%{label}<br>%{value} articles<extra></extra>"),
        link=dict(source=sources_, target=targets, value=values, color=lcol, hovertemplate="%{source.label} → %{target.label}<br>%{value} articles<extra></extra>")))
    return _style(fig, 440, margin=dict(l=10, r=10, t=10, b=10))


def sunburst(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_fig(height=440)
    ids, labels, parents, values, colors = ["All"], ["All"], [""], [len(df)], ["#2a3146"]
    srcs = sorted(df["source"].unique())
    for i, s in enumerate(srcs):
        d = df[df["source"] == s]
        ids.append(s); labels.append(s); parents.append("All"); values.append(len(d)); colors.append(CATEGORICAL[i % len(CATEGORICAL)])
        for sl in ("positive", "neutral", "negative"):
            ds = d[d["sentiment_label"] == sl]
            if ds.empty:
                continue
            sid = f"{s}|{sl}"
            ids.append(sid); labels.append(SENT_LABEL[sl]); parents.append(s); values.append(len(ds)); colors.append(SENT_COLOR[sl])
            for bl in ("left", "center", "right"):
                n = int((ds["bias_label"] == bl).sum())
                if n:
                    ids.append(f"{sid}|{bl}"); labels.append(BIAS_LABEL[bl]); parents.append(sid); values.append(n); colors.append(BIAS_COLOR[bl])
    fig = go.Figure(go.Sunburst(ids=ids, labels=labels, parents=parents, values=values, branchvalues="total", marker=dict(colors=colors, line=dict(color=BG, width=2)),
                                hovertemplate="<b>%{label}</b><br>%{value} articles (%{percentParent:.0%} of parent)<extra></extra>", insidetextorientation="radial"))
    return _style(fig, 440, margin=dict(l=0, r=0, t=10, b=0))


def race(df: pd.DataFrame) -> go.Figure:
    """Animated bars: each outlet's cumulative average sentiment, day by day (press Play)."""
    if df.empty:
        return empty_fig(height=380)
    d = df.assign(day=df["published_at"].dt.floor("D")).sort_values("day")
    days = sorted(d["day"].unique())
    srcs = sorted(d["source"].unique())

    def frame_data(day):
        sub = d[d["day"] <= day].groupby("source")["sentiment_score"].agg(["mean", "count"]).reindex(srcs).fillna(0).sort_values("mean")
        return sub

    def bar(sub):
        return go.Bar(x=sub["mean"], y=sub.index, orientation="h", marker=dict(color=[POS if v >= 0 else NEG for v in sub["mean"]], line=dict(color=BG, width=2)),
                      customdata=sub["count"], text=[f"{v:+.2f}" for v in sub["mean"]], textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{y}</b><br>Avg sentiment %{x:+.2f} · %{customdata:.0f} articles so far<extra></extra>")

    first = frame_data(days[0])
    frames = [go.Frame(name=str(pd.Timestamp(day).date()), data=[bar(frame_data(day))], layout=dict(title=dict(text=f"Up to {pd.Timestamp(day):%b %d}", font=dict(size=13, color="#aab0c0"))))
              for day in days]
    fig = go.Figure(data=[bar(first)], frames=frames)
    fig.update_xaxes(range=[-1.2, 1.2], zeroline=True, zerolinecolor="rgba(255,255,255,.3)")
    fig.update_layout(
        title=dict(text=f"Up to {pd.Timestamp(days[0]):%b %d}", font=dict(size=13, color="#aab0c0")),
        updatemenus=[dict(type="buttons", direction="left", x=0, y=-0.12, xanchor="left", yanchor="top", showactive=False, bgcolor="#1b2233", bordercolor="#3a4258",
                          buttons=[dict(label="▶ Play", method="animate", args=[None, dict(frame=dict(duration=900, redraw=True), fromcurrent=True, transition=dict(duration=500))]),
                                   dict(label="❚❚ Pause", method="animate", args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")])])],
        sliders=[dict(active=0, x=0.18, y=-0.1, len=0.82, currentvalue=dict(visible=False), pad=dict(t=0, b=0), bgcolor="#2a3146", activebgcolor="#6da7ec",
                      steps=[dict(label=f.name[5:], method="animate", args=[[f.name], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=300))]) for f in frames])])
    return _style(fig, 400, margin=dict(l=10, r=40, t=40, b=70))


def radar(src: pd.DataFrame, picks: list[str]) -> go.Figure:
    if src.empty or not picks:
        return empty_fig("Pick outlets to compare", 420)
    s = src.copy()
    mx = max(1, s["count"].max())
    axes = ["Positivity", "Negativity", "Loaded language", "Partisan lean", "Volume"]
    fig = go.Figure()
    for i, name in enumerate(picks):
        r = s[s["source"] == name]
        if r.empty:
            continue
        r = r.iloc[0]
        neg = r["pct_negative"] / 100
        vals = [max(0, (r["avg_sentiment"] + 1) / 2), neg, min(1, r["avg_subjectivity"] * 2.5), abs(r["avg_bias"]), r["count"] / mx]
        c = CATEGORICAL[i % len(CATEGORICAL)]
        fig.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=axes + axes[:1], name=name, fill="toself", line=dict(color=c, width=2.5), fillcolor=_rgba(c, 0.18),
                                      hovertemplate="%{theta}: <b>%{r:.2f}</b><extra>" + name + "</extra>"))
    fig.update_polars(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0, 1], gridcolor=GRID, showticklabels=False), angularaxis=dict(gridcolor=GRID))
    fig.update_layout(legend=dict(orientation="h", y=-0.08))
    return _style(fig, 430, margin=dict(l=40, r=40, t=20, b=30))


def hour_heatmap(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty_fig(height=280)
    d = df.assign(dow=df["published_at"].dt.dayofweek, hour=df["published_at"].dt.hour)
    grid = d.groupby(["dow", "hour"]).size().unstack(fill_value=0).reindex(index=range(7), columns=range(24), fill_value=0)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig = go.Figure(go.Heatmap(z=grid.values, x=[f"{h:02d}" for h in range(24)], y=days, xgap=3, ygap=3, colorscale=[[0, "#1a2133"], [1, "#6da7ec"]],
                               colorbar=dict(title="Articles", thickness=10, len=0.8), hovertemplate="%{y} %{x}:00 UTC · <b>%{z}</b> articles<extra></extra>"))
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Hour of day (UTC)", dtick=2)
    return _style(fig, 290)
