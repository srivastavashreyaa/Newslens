import os

os.environ["NLP_BACKEND"] = "lite"
os.environ["DATABASE_URL"] = "sqlite:///./test_news.db"
os.environ["INGEST_ON_STARTUP"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, engine
from app.main import app
from app.nlp.engine import get_engine
from app.nlp.tokenization import extract_keywords, split_sentences
from scripts.seed_demo import run as seed


@pytest.fixture(scope="module")
def client():
    Base.metadata.drop_all(engine)
    seed()
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(engine)
    if os.path.exists("test_news.db"):
        os.remove("test_news.db")


def test_tokenization():
    assert len(split_sentences("It rose. Then it fell! Was that all? Yes.")) == 4
    kws = extract_keywords("Central Bank holds rates", "The Central Bank held rates. Inflation is easing.")
    assert "central bank" in kws and "inflation" in kws


def test_sentiment_direction():
    nlp = get_engine()
    good = nlp.analyze("Great news", "Residents celebrate a wonderful, successful and joyful festival.")
    bad = nlp.analyze("Terrible disaster", "A horrific crash killed many and devastated the town.")
    assert good.sentiment_label == "positive" and bad.sentiment_label == "negative"
    assert bad.subjectivity > 0


def test_bias_uses_source_prior():
    nlp = get_engine()
    assert nlp.analyze("Headline", "Some plain text about a budget vote.", 0.7).bias_label == "right"
    assert nlp.analyze("Headline", "Some plain text about a budget vote.", -0.6).bias_label == "left"
    assert nlp.analyze("Headline", "Some plain text about a budget vote.", 0.0).bias_label == "center"


def test_health_and_articles(client):
    assert client.get("/api/health").json()["status"] == "ok"
    r = client.get("/api/articles?limit=5").json()
    assert r["total"] > 50 and len(r["items"]) == 5
    assert r["items"][0]["published_at"].endswith("Z")
    neg = client.get("/api/articles?sentiment=negative&limit=100").json()
    assert all(a["sentiment_label"] == "negative" for a in neg["items"])
    assert client.get("/api/articles?sentiment=bogus").status_code == 422
    assert client.get("/api/articles/999999").status_code == 404


def test_search_and_keyword_filters(client):
    r = client.get("/api/articles?q=solar").json()
    assert r["total"] > 0 and all("solar" in (a["title"] + a["summary"]).lower() for a in r["items"])
    k = client.get("/api/articles?keyword=solar").json()
    assert k["total"] > 0


def test_stats_endpoints(client):
    o = client.get("/api/stats/overview").json()
    assert o["articles"] > 50 and sum(o["sentiment"].values()) == o["articles"]
    t = client.get("/api/stats/sentiment-timeline?hours=200&bucket=day").json()
    assert len(t) >= 5 and {"t", "avg", "positive", "negative"} <= t[0].keys()
    s = client.get("/api/stats/sources").json()
    assert len(s) == 5 and s[0]["avg_bias"] < s[-1]["avg_bias"]
    assert client.get("/api/stats/trends?hours=24").json() is not None


def test_story_clusters(client):
    stories = client.get("/api/stories?hours=200").json()
    assert stories and all(c["sources"] >= 2 for c in stories)


def test_analyze_endpoint(client):
    r = client.post("/api/analyze", json={"title": "Plan", "text": "The council approved a wonderful new park. Residents are thrilled and delighted."})
    assert r.status_code == 200 and r.json()["sentiment_label"] == "positive"
    assert client.post("/api/analyze", json={"text": "short"}).status_code == 422


def test_websocket_receives_broadcast(client):
    import asyncio

    from app.realtime import manager

    with client.websocket_connect("/ws/stream") as ws:
        assert manager.count == 1
        ws.send_text("ping")


def test_rss_image_extraction():
    import feedparser

    from app.ingest import _entry_image

    xml = """<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/"><channel>
    <item><title>a</title><media:thumbnail url="https://img.example/a.jpg" width="240"/></item>
    <item><title>b</title><enclosure url="https://img.example/b.png" type="image/png" length="1"/></item>
    <item><title>c</title><description>&lt;p&gt;&lt;img src="https://img.example/c.webp"/&gt;text&lt;/p&gt;</description></item>
    <item><title>d</title><media:content url="https://vid.example/d.mp4" type="video/mp4"/></item>
    <item><title>e</title><enclosure url="javascript:alert(1)" type="image/png" length="1"/></item>
    </channel></rss>"""
    got = [_entry_image(e) for e in feedparser.parse(xml).entries]
    assert got == ["https://img.example/a.jpg", "https://img.example/b.png", "https://img.example/c.webp", "", ""]

