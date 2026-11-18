from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def _z(dt: datetime) -> str:
    return dt.isoformat() + "Z"


class ArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: str
    source: str
    summary: str
    image_url: str = ""
    published_at: datetime
    sentiment_label: str
    sentiment_score: float
    sentiment_confidence: float
    bias_label: str
    bias_score: float
    subjectivity: float
    bias_method: str
    keywords: list[str]
    token_count: int
    is_demo: bool = False

    @field_serializer("published_at")
    def _ser(self, v: datetime) -> str:
        return _z(v)


class ArticleList(BaseModel):
    total: int
    items: list[ArticleOut]


class AnalyzeRequest(BaseModel):
    title: str = Field("", max_length=600)
    text: str = Field(..., min_length=20, max_length=20000)
    source: str | None = None


class AnalyzeResponse(BaseModel):
    summary: str
    sentiment_label: str
    sentiment_score: float
    sentiment_confidence: float
    bias_label: str
    bias_score: float
    subjectivity: float
    bias_method: str
    keywords: list[str]
    token_count: int
    models: dict
