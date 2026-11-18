"""Sentiment backends. Both return (signed_score in [-1, 1], confidence in [0, 1])."""
from .tokenization import split_sentences


class LexiconSentiment:
    """CPU-only fallback (VADER). Used for tests/offline demos."""

    name = "vader-lite"
    neutral_band = 0.25

    def __init__(self):
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._sia = SentimentIntensityAnalyzer()

    def score(self, text: str) -> tuple[float, float]:
        c = self._sia.polarity_scores(text)["compound"]
        return c, abs(c)

    def token_count(self, text: str) -> int:
        return len(text.split())


class DistilBertSentiment:
    """DistilBERT fine-tuned on SST-2.

    Long articles are split into sentence chunks (<= ~200 words, well inside BERT's 512-token window),
    each chunk is tokenized + classified in one batch, and the signed scores are averaged.
    signed = P(positive) - P(negative). SST-2 is binary, so |signed| < neutral_band is reported as neutral.
    """

    name = "distilbert-sst2"
    neutral_band = 0.5

    def __init__(self, model_name: str, max_chunks: int = 4, chunk_words: int = 200):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).eval()
        labels = {int(i): l.lower() for i, l in self.model.config.id2label.items()}
        self._pos = next(i for i, l in labels.items() if l.startswith("pos"))
        self._neg = next(i for i, l in labels.items() if l.startswith("neg"))
        self.max_chunks, self.chunk_words = max_chunks, chunk_words

    def token_count(self, text: str) -> int:
        return len(self.tokenizer.encode(text, add_special_tokens=False, truncation=False))

    def _chunks(self, text: str) -> list[str]:
        chunks, cur, n = [], [], 0
        for s in split_sentences(text) or [text]:
            w = len(s.split())
            if cur and n + w > self.chunk_words:
                chunks.append(" ".join(cur))
                cur, n = [], 0
            cur.append(s)
            n += w
        if cur:
            chunks.append(" ".join(cur))
        return chunks[: self.max_chunks]

    def score(self, text: str) -> tuple[float, float]:
        chunks = self._chunks(text)
        if not chunks:
            return 0.0, 0.0
        enc = self.tokenizer(chunks, truncation=True, max_length=512, padding=True, return_tensors="pt")
        with self._torch.no_grad():
            probs = self._torch.softmax(self.model(**enc).logits, dim=-1)
        signed = (probs[:, self._pos] - probs[:, self._neg]).mean().item()
        conf = probs.max(dim=-1).values.mean().item()
        return signed, conf
