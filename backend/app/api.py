import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from . import stats
from .db import get_db
from .ingest import ingest_all, load_feeds, source_priors
from .models import Article
from .nlp.engine import get_engine
from .realtime import manager
from .schemas import AnalyzeRequest, AnalyzeResponse, ArticleList, ArticleOut

router = APIRouter()
_ingest_lock = asyncio.Lock()


@router.get("/api/health")
def health():
    engine = get_engine()
    return {"status": "ok", "models": engine.description, "live_clients": manager.count}


@router.get("/api/sources")
def sources():
    return load_feeds()


@router.get("/api/articles", response_model=ArticleList)
def list_articles(
    q: str | None = None,
    source: str | None = None,
    sentiment: str | None = Query(None, pattern="^(positive|neutral|negative)$"),
    bias: str | None = Query(None, pattern="^(left|center|right)$"),
    keyword: str | None = None,
    hours: int | None = Query(None, ge=1, le=24 * 30),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    query = stats._since(db, hours)
    if source:
        query = query.filter(Article.source == source)
    if sentiment:
        query = query.filter(Article.sentiment_label == sentiment)
    if bias:
        query = query.filter(Article.bias_label == bias)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Article.title.ilike(like), Article.summary.ilike(like)))
    if keyword:
        query = query.filter(cast(Article.keywords, String).ilike(f'%"{keyword}"%'))
    total = query.count()
    items = query.order_by(Article.published_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": items}


@router.get("/api/articles/{article_id}", response_model=ArticleOut)
def get_article(article_id: int, db: Session = Depends(get_db)):
    art = db.get(Article, article_id)
    if not art:
        raise HTTPException(404, "Article not found")
    return art


@router.get("/api/stats/overview")
def overview(hours: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    return stats.overview(db, hours)


@router.get("/api/stats/sentiment-timeline")
def timeline(
    hours: int = Query(72, ge=1, le=24 * 30),
    bucket: str = Query("hour", pattern="^(hour|day)$"),
    source: str | None = None,
    db: Session = Depends(get_db),
):
    return stats.sentiment_timeline(db, hours, bucket, source)


@router.get("/api/stats/sources")
def by_source(hours: int | None = Query(None, ge=1), db: Session = Depends(get_db)):
    return stats.source_breakdown(db, hours)


@router.get("/api/stats/trends")
def trends(hours: int = Query(24, ge=1, le=24 * 14), limit: int = Query(15, ge=1, le=50), db: Session = Depends(get_db)):
    return stats.trending_keywords(db, hours, limit)


@router.get("/api/stories")
def stories(hours: int = Query(48, ge=1, le=24 * 14), db: Session = Depends(get_db)):
    return stats.story_clusters(db, hours)


@router.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest):
    engine = get_engine()
    prior = source_priors().get(body.source or "", 0.0)
    result = await asyncio.to_thread(engine.analyze, body.title, body.text, prior)
    return {**result.__dict__, "models": engine.description}


@router.post("/api/ingest")
async def trigger_ingest():
    if _ingest_lock.locked():
        raise HTTPException(409, "An ingest run is already in progress")
    async with _ingest_lock:
        return await ingest_all()


@router.websocket("/ws/stream")
async def stream(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive pings from the client
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(ws)
