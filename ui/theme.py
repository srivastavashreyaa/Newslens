"""Colors, CSS and HTML component builders for the Streamlit UI."""
import colorsys
import hashlib
import html
import re
from datetime import datetime

import streamlit as st

# Semantic palette (dark-surface steps of the validated dataviz palette).
POS, NEU, NEG = "#3987e5", "#8d8b84", "#e66767"
LEFT, CENTER, RIGHT = "#9085e9", "#8d8b84", "#eb6834"
SENT_COLOR = {"positive": POS, "neutral": NEU, "negative": NEG}
BIAS_COLOR = {"left": LEFT, "center": CENTER, "right": RIGHT}
SENT_LABEL = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
BIAS_LABEL = {"left": "Left-leaning", "center": "Center", "right": "Right-leaning"}
DIVERGING = [[0, NEG], [0.5, "#3a3d46"], [1, POS]]
CATEGORICAL = ["#3987e5", "#d95926", "#199e70", "#d55181", "#c98500", "#0ca30c", "#9085e9", "#e66767"]
BG = "#0e1117"

THEMES = {
    "Aurora": ("#6da7ec", "#9085e9", "#eb6834"),
    "Emerald": ("#34d399", "#22d3ee", "#a3e635"),
    "Sunset": ("#fb7185", "#f59e0b", "#a855f7"),
    "Ice": ("#93c5fd", "#e0f2fe", "#67e8f9"),
}

BASE_CSS = """
<style>
:root { --a1:#6da7ec; --a2:#9085e9; --a3:#eb6834; --card:#141a28; --line:rgba(255,255,255,.08); --muted:#8e95a8; }
.block-container { padding-top: 1rem; max-width: 1380px; }
#MainMenu, footer { visibility: hidden; }

/* ---------- ticker ---------- */
.nl-ticker { overflow:hidden; white-space:nowrap; border-radius:12px; background:var(--card); border:1px solid var(--line); padding:9px 0; margin-bottom:12px;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent); mask-image: linear-gradient(90deg, transparent, #000 5%, #000 95%, transparent); }
.nl-ticker-track { display:inline-block; padding-left:100%; animation: nl-scroll 90s linear infinite; }
.nl-ticker:hover .nl-ticker-track { animation-play-state: paused; }
@keyframes nl-scroll { to { transform: translateX(-100%); } }
.nl-tk { display:inline-flex; align-items:center; gap:8px; margin-right:34px; font-size:.9rem; color:#d6dae6; }
.nl-tk i { width:8px; height:8px; border-radius:50%; display:inline-block; }
.nl-tk b { color:#fff; font-weight:600; }
.nl-live-tag { display:inline-flex; align-items:center; gap:6px; font-weight:700; font-size:11px; letter-spacing:.08em; color:#3ddc84; margin-right:24px; }
.nl-live-tag::before { content:""; width:7px; height:7px; border-radius:50%; background:#3ddc84; animation: nl-pulse 1.6s infinite; }
@keyframes nl-pulse { 0%{box-shadow:0 0 0 0 rgba(61,220,132,.6)} 70%{box-shadow:0 0 0 7px rgba(61,220,132,0)} 100%{box-shadow:0 0 0 0 rgba(61,220,132,0)} }

/* ---------- title bar ---------- */
.nl-hero { position:relative; overflow:hidden; border-radius:18px; padding:20px 26px; margin-bottom:14px;
  background: radial-gradient(800px 240px at 90% -30%, color-mix(in srgb, var(--a2) 40%, transparent), transparent 60%),
              radial-gradient(600px 220px at 5% 130%, color-mix(in srgb, var(--a1) 40%, transparent), transparent 60%), var(--card);
  border:1px solid var(--line); }
.nl-hero h1 { margin:0; font-size:1.9rem; letter-spacing:-.02em; }
.nl-hero h1 span { background: linear-gradient(90deg, var(--a1), var(--a2) 60%, var(--a3)); -webkit-background-clip:text; background-clip:text; color:transparent; }
.nl-hero p { margin:4px 0 0; color:#aab0c0; max-width: 820px; font-size:.95rem; }
.nl-pill-row { display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }
.nl-chip { font-size:12px; padding:3px 10px; border-radius:999px; border:1px solid rgba(255,255,255,.14); color:#c9cedb; background:rgba(255,255,255,.04); }
.nl-chip.live::before { content:""; display:inline-block; width:7px; height:7px; border-radius:50%; background:#3ddc84; margin-right:6px; animation: nl-pulse 1.6s infinite; }
.nl-chip.filter { border-color: color-mix(in srgb, var(--a1) 60%, transparent); color: var(--a1); }

/* ---------- metrics ---------- */
div[data-testid="stMetric"] { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:12px 16px; transition: transform .15s, border-color .15s; }
div[data-testid="stMetric"]:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--a1) 55%, transparent); }

/* ---------- top story ---------- */
.nl-top { position:relative; border-radius:18px; overflow:hidden; min-height:400px; display:flex; align-items:flex-end; border:1px solid var(--line);
  background-size:cover; background-position:center; }
.nl-top::before { content:""; position:absolute; inset:0; background: linear-gradient(180deg, rgba(8,10,16,.05) 10%, rgba(8,10,16,.88) 78%); }
.nl-top-in { position:relative; padding:24px 26px; width:100%; }
.nl-kicker { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.1em; text-transform:uppercase; padding:3px 10px; border-radius:999px; background:var(--a3); color:#fff; margin-bottom:10px; }
.nl-top h2 { margin:0 0 8px; font-size:1.75rem; line-height:1.18; letter-spacing:-.01em; color:#fff; }
.nl-top p { margin:0 0 10px; color:#d0d5e2; max-width:760px; }
.nl-side { display:flex; gap:12px; background:var(--card); border:1px solid var(--line); border-radius:14px; padding:10px; margin-bottom:10px; transition: transform .15s, border-color .15s; }
.nl-side:hover { transform: translateX(3px); border-color: color-mix(in srgb, var(--a1) 55%, transparent); }
.nl-thumb { width:104px; min-width:104px; height:78px; border-radius:10px; background-size:cover; background-position:center; }
.nl-side .t { font-weight:650; font-size:.93rem; line-height:1.3; color:#f2f4f9; margin:2px 0 5px; }

/* ---------- grid cards ---------- */
.nl-gcard { background:var(--card); border:1px solid var(--line); border-radius:16px; overflow:hidden; margin-bottom:8px; transition: transform .18s, border-color .18s, box-shadow .18s; }
.nl-gcard:hover { transform: translateY(-4px); border-color: color-mix(in srgb, var(--a1) 55%, transparent); box-shadow: 0 14px 32px rgba(0,0,0,.45); }
.nl-img { position:relative; height:170px; background-size:cover; background-position:center; overflow:hidden; }
.nl-img::after { content:""; position:absolute; inset:0; background: linear-gradient(180deg, transparent 55%, rgba(8,10,16,.65)); }
.nl-img .src { position:absolute; left:10px; bottom:9px; z-index:1; font-size:12px; font-weight:700; color:#fff; text-shadow:0 1px 6px rgba(0,0,0,.7); }
.nl-img .age { position:absolute; right:10px; bottom:9px; z-index:1; font-size:11px; color:#e6e9f2; }
.nl-img .mood { position:absolute; left:10px; top:10px; z-index:1; font-size:12px; font-weight:700; padding:2px 9px; border-radius:999px; color:#fff; }
.nl-img .new { position:absolute; right:10px; top:10px; z-index:1; font-size:10px; font-weight:800; letter-spacing:.08em; padding:2px 8px; border-radius:999px; background:#3ddc84; color:#04210f; }
.nl-gbody { padding:12px 14px 12px; }
.nl-gbody .nl-title { font-size:.98rem; }
.nl-title { color:#f2f4f9 !important; font-weight:650; line-height:1.3; text-decoration:none !important; display:block; margin-bottom:5px; }
a.nl-title:hover { text-decoration:underline !important; }
.nl-sum { color:#b4bacb; font-size:.86rem; margin:0 0 8px; }
.nl-badges { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:6px; }
.nl-badge { display:inline-flex; align-items:center; gap:6px; font-size:12px; padding:2px 9px; border-radius:999px; border:1px solid rgba(255,255,255,.12); color:#dfe3ee; background:rgba(255,255,255,.03); }
.nl-badge i { width:8px; height:8px; border-radius:50%; display:inline-block; }
.nl-kw { color:#7f88a0; font-size:12px; display:flex; gap:10px; flex-wrap:wrap; }
.nl-demo { font-size:10px; border:1px dashed #5b6277; color:var(--muted); border-radius:4px; padding:0 5px; }

/* ---------- misc cards ---------- */
.nl-card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 16px; margin-bottom:10px; transition: transform .15s, border-color .15s; }
.nl-card:hover { border-color: color-mix(in srgb, var(--a1) 45%, transparent); }
.nl-meta { color:var(--muted); font-size:12px; margin-bottom:4px; display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
.nl-meta b { color:#c9cedb; font-weight:600; }
.nl-wire { display:grid; gap:6px; }
.nl-wire-row { display:flex; gap:10px; align-items:center; background:var(--card); border:1px solid rgba(255,255,255,.06); border-radius:10px; padding:8px 12px; font-size:.9rem; animation: nl-slide .5s ease-out; }
.nl-wire-row .t { color:#7f88a0; font-size:12px; min-width:62px; }
.nl-wire-row .s { color:#c9cedb; font-weight:600; min-width:120px; }
@keyframes nl-slide { from { opacity:0; transform: translateX(-12px);} to { opacity:1; transform:none; } }
.nl-lb { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:12px 14px; height:100%; margin-bottom:16px; }
.nl-lb .k { color:var(--muted); font-size:12px; }
.nl-lb .v { font-size:1.15rem; font-weight:700; margin:2px 0; }
.nl-lb .d { color:#aab0c0; font-size:12px; }
.nl-empty { text-align:center; padding:48px 24px; border:1px dashed rgba(255,255,255,.18); border-radius:18px; background:rgba(255,255,255,.02); margin:12px 0; }
.nl-empty h3 { margin:0 0 6px; }
.nl-empty p { color:#aab0c0; margin:0 0 10px; }
mark.nl-loaded { background:rgba(235,104,52,.28); color:#ffd8c8; border-radius:4px; padding:0 3px; }
.stTabs [data-baseweb="tab-list"], .stTabs [role="tablist"] { gap:6px; }
.stTabs [role="tab"] { border-radius:10px 10px 0 0; padding:8px 14px; }
.stTabs [aria-selected="true"] { color: var(--a1) !important; }
</style>
"""


def inject_css(theme: str = "Aurora"):
    a1, a2, a3 = THEMES.get(theme, THEMES["Aurora"])
    st.markdown(BASE_CSS + f"<style>:root{{--a1:{a1};--a2:{a2};--a3:{a3};}}</style>", unsafe_allow_html=True)


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def time_ago(dt: datetime, now: datetime) -> str:
    s = max(0, (now - dt).total_seconds())
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)}m ago"
    if s < 86400:
        return f"{int(s // 3600)}h ago"
    return f"{int(s // 86400)}d ago"


def fallback_gradient(source: str) -> str:
    """Deterministic per-outlet gradient used when an article has no (or a broken) image."""
    h = int(hashlib.md5(str(source).encode()).hexdigest(), 16)
    h1, h2 = (h % 360) / 360, ((h // 360) % 360) / 360

    def hexc(hh, l):
        r, g, b = colorsys.hls_to_rgb(hh, l, 0.55)
        return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))

    return f"linear-gradient(135deg,{hexc(h1, .32)},{hexc(h2, .45)})"


def bg_style(url: str, source: str) -> str:
    g = fallback_gradient(source)
    if url and url.startswith(("http://", "https://", "data:image/")):
        u = url
        for a, b in (("'", "%27"), ('"', "%22"), ("(", "%28"), (")", "%29"), ("<", "%3C"), (">", "%3E"), (" ", "%20")):
            u = u.replace(a, b)
        return f"background-image:url('{esc(u)}'),{g};"
    return f"background-image:{g};"


def sent_badge(label: str, score: float) -> str:
    return f'<span class="nl-badge"><i style="background:{SENT_COLOR[label]}"></i>{SENT_LABEL[label]} {score:+.2f}</span>'


def bias_badge(label: str, score: float) -> str:
    return f'<span class="nl-badge" title="Bias {score:+.2f}"><i style="background:{BIAS_COLOR[label]}"></i>{BIAS_LABEL[label]}</span>'


def loaded_badge(v: float) -> str:
    return f'<span class="nl-badge" title="Share of charged wording">🔥 Loaded {round(v * 100)}%</span>'


def _clip(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def grid_card(row, now) -> str:
    fresh = (now - row.published_at).total_seconds() < 1800
    new = '<span class="new">NEW</span>' if fresh else ""
    link = row.url if str(row.url).startswith("http") and not row.is_demo else ""
    title = f'<a class="nl-title" href="{esc(link)}" target="_blank" rel="noopener">{esc(row.title)}</a>' if link else f'<span class="nl-title">{esc(row.title)}</span>'
    kws = " ".join(f"<span>#{esc(k)}</span>" for k in list(row.keywords)[:4])
    return (
        f'<div class="nl-gcard"><div class="nl-img" style="{bg_style(row.image_url, row.source)}">'
        f'<span class="mood" style="background:{SENT_COLOR[row.sentiment_label]}">{row.sentiment_score:+.2f}</span>{new}'
        f'<span class="src">{esc(row.source)}</span><span class="age">{time_ago(row.published_at, now)}</span></div>'
        f'<div class="nl-gbody">{title}<p class="nl-sum">{esc(_clip(row.summary, 150))}</p>'
        f'<div class="nl-badges">{bias_badge(row.bias_label, row.bias_score)}{loaded_badge(row.subjectivity)}</div>'
        f'<div class="nl-kw">{kws}</div></div></div>'
    )


def top_story_card(row, now, kicker: str, extra: str = "") -> str:
    return (
        f'<div class="nl-top" style="{bg_style(row.image_url, row.source)}"><div class="nl-top-in">'
        f'<span class="nl-kicker">{esc(kicker)}</span><h2>{esc(row.title)}</h2><p>{esc(_clip(row.summary, 260))}</p>'
        f'<div class="nl-badges">{sent_badge(row.sentiment_label, row.sentiment_score)}{bias_badge(row.bias_label, row.bias_score)}{loaded_badge(row.subjectivity)}'
        f'<span class="nl-badge">📰 {esc(row.source)} · {time_ago(row.published_at, now)}</span>{extra}</div></div></div>'
    )


def side_item(row, now) -> str:
    return (
        f'<div class="nl-side"><div class="nl-thumb" style="{bg_style(row.image_url, row.source)}"></div><div>'
        f'<div class="t">{esc(_clip(row.title, 95))}</div><div class="nl-badges" style="margin:0">{sent_badge(row.sentiment_label, row.sentiment_score)}'
        f'<span class="nl-badge">{esc(row.source)}</span></div></div></div>'
    )


def ticker_html(rows, now) -> str:
    items = "".join(
        f'<span class="nl-tk"><i style="background:{SENT_COLOR[r.sentiment_label]}"></i><b>{esc(r.source)}</b> {esc(_clip(r.title, 110))}</span>' for r in rows
    )
    return f'<div class="nl-ticker"><span class="nl-live-tag" style="margin-left:14px">LIVE</span><div class="nl-ticker-track">{items}</div></div>'


def leaderboard_card(kicker: str, value: str, detail: str, color: str) -> str:
    return f'<div class="nl-lb" style="border-top:3px solid {color}"><div class="k">{esc(kicker)}</div><div class="v">{esc(value)}</div><div class="d">{esc(detail)}</div></div>'


def highlight_loaded(text: str, loaded: set[str]) -> str:
    def repl(m):
        w = m.group(0)
        return f'<mark class="nl-loaded">{w}</mark>' if w.lower() in loaded else w

    return re.sub(r"[A-Za-z][A-Za-z'\-]+", repl, esc(text))
