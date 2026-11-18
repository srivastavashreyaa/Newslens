"""Aggregations behind the dashboard: sentiment timeline, source/bias breakdowns, trends, story clusters."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .db import utcnow
from .models import Article


def _since(db: Session, hours: int | None, source: str | None = None):
    q = db.query(Article)
    if hours:
        q = q.filter(Article.published_at >= utcnow() - timedelta(hours=hours))
    if source:
        q = q.filter(Article.source == source)
    return q


def _z(dt: datetime) -> str:
    return dt.isoformat() + "Z"


def _mean(xs):
    return round(sum(xs) / len(xs), 3) if xs else 0.0


def overview(db: Session, hours: int | None = None) -> dict:
    rows = _since(db, hours).all()
    n = len(rows)
    sent = Counter(r.sentiment_label for r in rows)
    bias = Counter(r.bias_label for r in rows)
    return {
        "articles": n,
        "sources": len({r.source for r in rows}),
        "avg_sentiment": _mean([r.sentiment_score for r in rows]),
        "avg_subjectivity": _mean([r.subjectivity for r in rows]),
        "sentiment": {k: sent.get(k, 0) for k in ("positive", "neutral", "negative")},
        "bias": {k: bias.get(k, 0) for k in ("left", "center", "right")},
        "latest": _z(max((r.published_at for r in rows), default=utcnow())),
    }


def sentiment_timeline(db: Session, hours: int = 72, bucket: str = "hour", source: str | None = None) -> list[dict]:
    fmt_trunc = (lambda d: d.replace(minute=0, second=0, microsecond=0)) if bucket == "hour" else (
        lambda d: d.replace(hour=0, minute=0, second=0, microsecond=0)
    )
    groups: dict[datetime, list[Article]] = defaultdict(list)
    for r in _since(db, hours, source).all():
        groups[fmt_trunc(r.published_at)].append(r)
    out = []
    for t in sorted(groups):
        rs = groups[t]
        c = Counter(r.sentiment_label for r in rs)
        out.append(
            {
                "t": _z(t),
                "avg": _mean([r.sentiment_score for r in rs]),
                "positive": c.get("positive", 0),
                "neutral": c.get("neutral", 0),
                "negative": c.get("negative", 0),
                "count": len(rs),
            }
        )
    return out


def source_breakdown(db: Session, hours: int | None = None) -> list[dict]:
    groups: dict[str, list[Article]] = defaultdict(list)
    for r in _since(db, hours).all():
        groups[r.source].append(r)
    out = []
    for s, rs in groups.items():
        c = Counter(r.bias_label for r in rs)
        out.append(
            {
                "source": s,
                "count": len(rs),
                "avg_sentiment": _mean([r.sentiment_score for r in rs]),
                "avg_bias": _mean([r.bias_score for r in rs]),
                "avg_subjectivity": _mean([r.subjectivity for r in rs]),
                "pct_negative": round(100 * sum(r.sentiment_label == "negative" for r in rs) / len(rs), 1),
                "bias": {k: c.get(k, 0) for k in ("left", "center", "right")},
            }
        )
    return sorted(out, key=lambda d: d["avg_bias"])


def trending_keywords(db: Session, hours: int = 24, limit: int = 15, min_count: int = 2) -> list[dict]:
    """Keyword momentum: mentions in the latest window vs the window before it."""
    now = utcnow()
    cur_start, prev_start = now - timedelta(hours=hours), now - timedelta(hours=2 * hours)
    cur, prev = Counter(), Counter()
    sentiments: dict[str, list[float]] = defaultdict(list)
    sources: dict[str, set] = defaultdict(set)
    for r in db.query(Article).filter(Article.published_at >= prev_start).all():
        for kw in set(r.keywords or []):
            if r.published_at >= cur_start:
                cur[kw] += 1
                sentiments[kw].append(r.sentiment_score)
                sources[kw].add(r.source)
            else:
                prev[kw] += 1
    rows = []
    for kw, c in cur.items():
        if c < min_count:
            continue
        p = prev.get(kw, 0)
        rows.append(
            {
                "keyword": kw,
                "count": c,
                "previous": p,
                "growth_pct": round(100 * (c - p) / (p + 1), 1),
                "avg_sentiment": _mean(sentiments[kw]),
                "sources": len(sources[kw]),
            }
        )
    rows.sort(key=lambda d: (d["growth_pct"] * min(d["count"], 6), d["count"]), reverse=True)
    return rows[:limit]


def story_clusters(db: Session, hours: int = 48, threshold: float = 0.17, limit: int = 12) -> list[dict]:
    arts = _since(db, hours).order_by(Article.published_at.desc()).limit(400).all()
    return cluster_articles(arts, threshold, limit)


def cluster_articles(arts: list, threshold: float = 0.17, limit: int = 12) -> list[dict]:
    """Group articles from different outlets covering the same story (TF-IDF cosine + union-find)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    if len(arts) < 2:
        return []
    docs = [f"{a.title}. {a.title}. {a.summary}" for a in arts]
    tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True).fit_transform(docs)
    sim = cosine_similarity(tfidf)

    parent = list(range(len(arts)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(arts)):
        for j in range(i + 1, len(arts)):
            close_in_time = abs((arts[i].published_at - arts[j].published_at).total_seconds()) <= 24 * 3600
            if sim[i, j] >= threshold and close_in_time and arts[i].source != arts[j].source:
                parent[find(i)] = find(j)

    clusters: dict[int, list[Article]] = defaultdict(list)
    for i, a in enumerate(arts):
        clusters[find(i)].append(a)

    out = []
    for members in clusters.values():
        latest_per_source = {}
        for m in sorted(members, key=lambda m: m.published_at):
            latest_per_source[m.source] = m  # one article per outlet: its most recent take
        members = sorted(latest_per_source.values(), key=lambda m: m.published_at)
        if len(members) < 2:
            continue
        spread = max(m.sentiment_score for m in members) - min(m.sentiment_score for m in members)
        kw = Counter(k for m in members for k in (m.keywords or []))
        out.append(
            {
                "headline": members[0].title,
                "keywords": [k for k, _ in kw.most_common(4)],
                "sources": len({m.source for m in members}),
                "sentiment_spread": round(spread, 3),
                "articles": [
                    {
                        "id": m.id,
                        "source": m.source,
                        "title": m.title,
                        "url": m.url,
                        "sentiment_label": m.sentiment_label,
                        "sentiment_score": m.sentiment_score,
                        "bias_label": m.bias_label,
                        "bias_score": m.bias_score,
                        "subjectivity": m.subjectivity,
                    }
                    for m in members
                ],
            }
        )
    out.sort(key=lambda c: (c["sources"], c["sentiment_spread"]), reverse=True)
    return out[:limit]
