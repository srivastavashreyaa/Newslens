from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    """Naive UTC datetime (what we store everywhere)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns() -> None:
    """Add columns introduced after a database file was first created (tiny migration, no Alembic needed)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "articles" not in insp.get_table_names():
        return
    have = {c["name"] for c in insp.get_columns("articles")}
    with engine.begin() as conn:
        if "image_url" not in have:
            conn.execute(text("ALTER TABLE articles ADD COLUMN image_url TEXT DEFAULT ''"))
