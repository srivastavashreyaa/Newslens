from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(600))
    source: Mapped[str] = mapped_column(String(120), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=utcnow)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    # Sentiment (DistilBERT): label + signed score in [-1, 1] + model confidence in [0, 1]
    sentiment_label: Mapped[str] = mapped_column(String(10), index=True, default="neutral")
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment_confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Bias: left/center/right, signed score in [-1 (left), +1 (right)], loaded-language intensity in [0, 1]
    bias_label: Mapped[str] = mapped_column(String(10), index=True, default="center")
    bias_score: Mapped[float] = mapped_column(Float, default=0.0)
    subjectivity: Mapped[float] = mapped_column(Float, default=0.0)
    bias_method: Mapped[str] = mapped_column(String(60), default="")

    keywords: Mapped[list] = mapped_column(JSON, default=list)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
