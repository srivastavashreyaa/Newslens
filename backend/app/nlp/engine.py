"""Single entry point that runs the whole NLP pipeline for one article."""
import logging
import threading
from dataclasses import dataclass, field

from ..config import settings
from .bias import BiasDetector
from .sentiment import DistilBertSentiment, LexiconSentiment
from .summarizer import DistilBartSummarizer, ExtractiveSummarizer
from .tokenization import clean_text, extract_keywords

log = logging.getLogger("nlp")


@dataclass
class Analysis:
    summary: str = ""
    sentiment_label: str = "neutral"
    sentiment_score: float = 0.0
    sentiment_confidence: float = 0.0
    bias_label: str = "center"
    bias_score: float = 0.0
    subjectivity: float = 0.0
    bias_method: str = ""
    keywords: list[str] = field(default_factory=list)
    token_count: int = 0


class NLPEngine:
    def __init__(self, sentiment, summarizer, bias: BiasDetector):
        self.sentiment, self.summarizer, self.bias = sentiment, summarizer, bias

    @property
    def description(self) -> dict:
        return {
            "sentiment": self.sentiment.name,
            "summarizer": self.summarizer.name,
            "bias": self.bias.method,
        }

    def analyze(self, title: str, text: str, source_prior: float = 0.0) -> Analysis:
        title, text = clean_text(title), clean_text(text)
        body = text or title
        full = f"{title}. {body}" if text else title

        score, conf = self.sentiment.score(full)
        band = self.sentiment.neutral_band
        label = "positive" if score >= band else "negative" if score <= -band else "neutral"
        b_label, b_score, subj, method = self.bias.detect(title, body, source_prior)

        return Analysis(
            summary=self.summarizer.summarize(title, body) if text else title,
            sentiment_label=label,
            sentiment_score=round(score, 3),
            sentiment_confidence=round(conf, 3),
            bias_label=b_label,
            bias_score=b_score,
            subjectivity=subj,
            bias_method=method,
            keywords=extract_keywords(title, body),
            token_count=self.sentiment.token_count(full),
        )


_engine: NLPEngine | None = None
_lock = threading.Lock()


def build_lite() -> NLPEngine:
    return NLPEngine(LexiconSentiment(), ExtractiveSummarizer(), BiasDetector())


def build_transformers() -> NLPEngine:
    return NLPEngine(
        DistilBertSentiment(settings.sentiment_model),
        DistilBartSummarizer(settings.summary_model),
        BiasDetector(settings.bias_model_path),
    )


def get_engine() -> NLPEngine:
    global _engine
    with _lock:
        if _engine is None:
            mode = settings.nlp_backend.lower()
            if mode == "lite":
                _engine = build_lite()
            else:
                try:
                    _engine = build_transformers()
                except Exception as exc:  # missing torch, offline, etc.
                    if mode == "transformers":
                        raise
                    log.warning("Transformer models unavailable (%s). Falling back to lite NLP backend.", exc)
                    _engine = build_lite()
            log.info("NLP engine ready: %s", _engine.description)
        return _engine


def set_engine(engine: NLPEngine | None) -> None:  # used by tests
    global _engine
    _engine = engine
