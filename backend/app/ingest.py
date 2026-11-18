"""Multi-source RSS ingestion -> NLP analysis -> database -> live broadcast."""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from calendar import timegm

import feedparser
import httpx

from .config import settings
from .db import SessionLocal, utcnow
from .models import Article
from .nlp.engine import get_engine
from .nlp.tokenization import clean_text
from .realtime import manager
from .schemas import ArticleOut

log = logging.getLogger("ingest")
FEEDS_FILE = Path(__file__).parent / "feeds.json"
HEADERS = {"User-Agent": "NewsLens/1.0 (+news aggregator project)"}


def load_feeds() -> list[dict]:
    return json.loads(FEEDS_FILE.read_text())


def source_priors() -> dict[str, float]:
    return {f["name"]: f.get("bias_prior", 0.0) for f in load_feeds()}


def _entry_time(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None) or entry.get(key)
        if t:
            return datetime.fromtimestamp(timegm(t), tz=timezone.utc).replace(tzinfo=None)
    return utcnow()


_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif")
_IMG_TAG = re.compile(r"<img[^>]+src=[\"']([^\"']+)", re.I)


def _ok_image(url: str | None) -> bool:
    return bool(url) and url.startswith(("http://", "https://")) and len(url) < 1000


def _entry_image(entry) -> str:
    """Best-effort thumbnail from media:content / media:thumbnail / enclosures / inline <img>."""
    for key in ("media_content", "media_thumbnail"):
        for m in entry.get(key) or []:
            url, kind, medium = m.get("url"), m.get("type", ""), m.get("medium", "")
            if _ok_image(url) and (kind.startswith("image") or medium == "image" or (not kind and not medium and url.lower().split("?")[0].endswith(_IMG_EXT))):
                return url
    for enc in list(entry.get("enclosures") or []) + list(entry.get("links") or []):
        url = enc.get("href") or enc.get("url")
        if _ok_image(url) and (enc.get("type", "").startswith("image") or url.lower().split("?")[0].endswith(_IMG_EXT)):
            return url
    blob = (entry.get("summary", "") or "") + " ".join(c.get("value", "") for c in entry.get("content") or [])
    m = _IMG_TAG.search(blob)
    return m.group(1) if m and _ok_image(m.group(1)) else ""


def _entry_text(entry) -> str:
    parts = []
    if entry.get("content"):
        parts.append(entry["content"][0].get("value", ""))
    parts.append(entry.get("summary", "") or entry.get("description", ""))
    return clean_text(max(parts, key=len))


async def fetch_feed(client: httpx.AsyncClient, feed: dict) -> list[dict]:
    try:
        r = await client.get(feed["url"], follow_redirects=True)
        r.raise_for_status()
    except Exception as exc:
        log.warning("feed %s failed: %s", feed["name"], exc)
        return []
    parsed = feedparser.parse(r.content)
    items = []
    for e in parsed.entries[: settings.max_per_feed]:
        url, title = e.get("link"), clean_text(e.get("title", ""))
        if url and title:
            items.append(
                {
                    "url": url,
                    "title": title,
                    "source": feed["name"],
                    "text": _entry_text(e),
                    "image_url": _entry_image(e),
                    "published_at": _entry_time(e),
                    "prior": feed.get("bias_prior", 0.0),
                }
            )
    return items


async def _full_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        import trafilatura

        r = await client.get(url, follow_redirects=True)
        return clean_text(trafilatura.extract(r.text) or "")
    except Exception:
        return ""


def _store(item: dict, text: str) -> Article | None:
    """Analyze (blocking, runs in a worker thread) and persist one article."""
    a = get_engine().analyze(item["title"], text, item["prior"])
    with SessionLocal() as db:
        if db.query(Article.id).filter(Article.url == item["url"]).first():
            return None
        art = Article(
            url=item["url"],
            title=item["title"],
            source=item["source"],
            content=text,
            image_url=item.get("image_url", ""),
            published_at=item["published_at"],
            **a.__dict__,
        )
        db.add(art)
        db.commit()
        return art


async def ingest_all() -> dict:
    feeds = load_feeds()
    async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
        results = await asyncio.gather(*(fetch_feed(client, f) for f in feeds))
        new, seen = 0, 0
        for items in results:
            for item in items:
                seen += 1
                with SessionLocal() as db:
                    if db.query(Article.id).filter(Article.url == item["url"]).first():
                        continue
                text = item["text"]
                if settings.fetch_full_text:
                    text = await _full_text(client, item["url"]) or text
                art = await asyncio.to_thread(_store, item, text)
                if art:
                    new += 1
                    await manager.broadcast({"type": "article", "data": json.loads(ArticleOut.model_validate(art).model_dump_json())})
    log.info("ingest finished: %d new of %d seen", new, seen)
    return {"fetched": seen, "new": new, "feeds": len(feeds)}
