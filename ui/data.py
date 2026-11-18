"""Data layer for the Streamlit app: reuses the backend NLP + ingestion code directly (no API server needed)."""
import asyncio
import os
import re
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

# Streamlit Cloud: values from the app's Secrets override defaults (all optional).
for _k in ("NLP_BACKEND", "SENTIMENT_MODEL", "SUMMARY_MODEL", "BIAS_MODEL_PATH", "MAX_PER_FEED"):
    try:
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass
os.environ.setdefault("NLP_BACKEND", "lite")  # lite = no model downloads; set "auto" to use DistilBERT/DistilBART
os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'news.db'}")
os.environ.setdefault("INGEST_ON_STARTUP", "false")
os.environ.setdefault("MAX_PER_FEED", "20")

from app import stats  # noqa: E402
from app.db import Base, SessionLocal, engine, ensure_columns, utcnow  # noqa: E402
from app.ingest import ingest_all, load_feeds, source_priors  # noqa: E402
from app.models import Article  # noqa: E402
from app.nlp.bias import LOADED  # noqa: E402
from app.nlp.engine import get_engine  # noqa: E402
from app.nlp.tokenization import STOPWORDS  # noqa: E402
from scripts.seed_demo import run as seed_demo  # noqa: E402

Base.metadata.create_all(engine)
ensure_columns()  # adds image_url to databases created by older versions

WINDOWS = {"6h": 6, "24h": 24, "3d": 72, "7d": 168, "30d": 720, "All": None}
COLS = ["id", "title", "source", "summary", "image_url", "content", "published_at", "sentiment_label", "sentiment_score",
        "sentiment_confidence", "bias_label", "bias_score", "subjectivity", "keywords", "url", "is_demo", "token_count"]


@st.cache_resource
def nlp_engine():
    return get_engine()


@st.cache_resource
def _ingest_state():
    return {"lock": threading.Lock(), "last": 0.0, "result": None}


def run_ingest() -> dict | None:
    """Fetch all feeds once. Returns None if another session is already ingesting."""
    state = _ingest_state()
    if not state["lock"].acquire(blocking=False):
        return None
    try:
        nlp_engine()
        res = asyncio.run(ingest_all())
        state["last"], state["result"] = time.time(), res
        return res
    finally:
        state["lock"].release()


def last_ingest() -> float:
    return _ingest_state()["last"]


def db_version() -> tuple[int, int]:
    with SessionLocal() as db:
        from sqlalchemy import func

        n, mx = db.query(func.count(Article.id), func.max(Article.id)).one()
    return int(n or 0), int(mx or 0)


@st.cache_data(ttl=300, show_spinner=False)
def _load(version: tuple[int, int]) -> pd.DataFrame:
    with SessionLocal() as db:
        rows = db.query(Article).order_by(Article.published_at.desc()).limit(4000).all()
    df = pd.DataFrame([{c: getattr(r, c) for c in COLS} for r in rows], columns=COLS)
    df["published_at"] = pd.to_datetime(df["published_at"])
    return df


def load_df() -> pd.DataFrame:
    return _load(db_version())


def ensure_demo():
    seed_demo()
    _clusters.clear()
    _load.clear()


def clear_demo():
    seed_demo(clear=True)
    _load.clear()


def latest_rows(demo: bool, n: int = 6) -> pd.DataFrame:
    with SessionLocal() as db:
        rows = (db.query(Article).filter(Article.is_demo.is_(demo)).order_by(Article.published_at.desc()).limit(n).all())
    return pd.DataFrame([{c: getattr(r, c) for c in COLS} for r in rows], columns=COLS)


def search_df(d: pd.DataFrame, q: str):
    """Word-based search over title, summary, keywords and outlet. Returns (frame, mode) with mode all|partial|none."""
    toks = [t for t in re.findall(r"[a-z0-9']+", q.lower()) if t not in STOPWORDS and len(t) > 1]
    if not toks or d.empty:
        return d, "all"
    hay = (d["title"] + " " + d["summary"] + " " + d["source"] + " " + d["keywords"].apply(" ".join)).str.lower()
    hits = pd.DataFrame({t: hay.str.contains(re.escape(t), regex=True) for t in toks})
    full = hits.all(axis=1)
    if full.any():
        return d[full], "all"
    n = hits.sum(axis=1)
    if (n > 0).any():
        return d.assign(_m=n)[n > 0].sort_values("_m", ascending=False).drop(columns="_m"), "partial"
    return d.iloc[0:0], "none"


def apply_filters(df, *, demo, sources, sentiments, biases, query, hours, now=None):
    """Returns (base, current-window, previous-window, search_note)."""
    now = now or utcnow()
    d = df[df["is_demo"] == demo]
    if sources:
        d = d[d["source"].isin(sources)]
    if sentiments:
        d = d[d["sentiment_label"].isin(sentiments)]
    if biases:
        d = d[d["bias_label"].isin(biases)]
    note = ""
    if query.strip():
        d, mode = search_df(d, query)
        note = "" if mode == "all" else mode
    base = d
    cur = d if hours is None else d[d["published_at"] >= now - timedelta(hours=hours)]
    prev = d.iloc[0:0] if hours is None else d[(d["published_at"] < now - timedelta(hours=hours)) & (d["published_at"] >= now - timedelta(hours=2 * hours))]
    return base, cur, prev, note


def source_table(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["source", "count", "avg_sentiment", "avg_bias", "avg_subjectivity", "pct_negative"])
    g = df.groupby("source")
    out = g.agg(count=("id", "count"), avg_sentiment=("sentiment_score", "mean"), avg_bias=("bias_score", "mean"),
                avg_subjectivity=("subjectivity", "mean")).reset_index()
    out["pct_negative"] = (g["sentiment_label"].apply(lambda s: (s == "negative").mean() * 100)).values
    return out.sort_values("avg_bias").reset_index(drop=True)


def keyword_table(cur: pd.DataFrame, prev: pd.DataFrame, min_count: int = 2) -> pd.DataFrame:
    def explode(d):
        e = d[["id", "source", "sentiment_score", "keywords"]].explode("keywords").dropna(subset=["keywords"])
        return e.rename(columns={"keywords": "keyword"})

    ce, pe = explode(cur), explode(prev)
    if ce.empty:
        return pd.DataFrame(columns=["keyword", "count", "previous", "growth_pct", "avg_sentiment", "sources", "score"])
    t = ce.groupby("keyword").agg(count=("id", "nunique"), avg_sentiment=("sentiment_score", "mean"), sources=("source", "nunique")).reset_index()
    pc = pe.groupby("keyword")["id"].nunique() if not pe.empty else pd.Series(dtype=int)
    t["previous"] = t["keyword"].map(pc).fillna(0).astype(int)
    t["growth_pct"] = (100 * (t["count"] - t["previous"]) / (t["previous"] + 1)).round(1)
    t["score"] = t["growth_pct"] * t["count"].clip(upper=6)
    t = t[t["count"] >= min_count]
    return t.sort_values(["score", "count"], ascending=False).reset_index(drop=True)


def clusters(df: pd.DataFrame, limit: int = 10) -> list[dict]:
    if len(df) < 2:
        return []
    return _clusters(tuple(df["id"].head(400).tolist()), limit)


@st.cache_data(ttl=300, show_spinner=False)
def _clusters(ids: tuple, limit: int) -> list[dict]:
    ids = list(ids)
    with SessionLocal() as db:
        arts = db.query(Article).filter(Article.id.in_(ids)).order_by(Article.published_at.desc()).all()
    return stats.cluster_articles(arts, limit=limit)


__all__ = [n for n in dir() if not n.startswith("__")]
