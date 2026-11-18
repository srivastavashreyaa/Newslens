import asyncio
import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import router
from .config import settings
from .db import Base, SessionLocal, engine, ensure_columns
from .ingest import ingest_all
from .models import Article
from .nlp.engine import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("app")


async def _safe_ingest():
    try:
        await ingest_all()
    except Exception:
        log.exception("scheduled ingest failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    ensure_columns()
    await asyncio.to_thread(get_engine)  # load BERT models once, before serving
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_safe_ingest, "interval", minutes=settings.fetch_interval_minutes, id="ingest")
    scheduler.start()
    if settings.ingest_on_startup:
        with SessionLocal() as db:
            empty = db.query(Article.id).first() is None
        if empty:
            asyncio.create_task(_safe_ingest())
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="NewsLens - News Aggregator & Analyzer", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
