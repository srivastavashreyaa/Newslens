"""Summarizers: DistilBART (abstractive) and a frequency-based extractive fallback."""
import math
from collections import Counter

from .tokenization import STOPWORDS, split_sentences, tokenize_words


class ExtractiveSummarizer:
    name = "extractive"

    def __init__(self, n_sentences: int = 2):
        self.n = n_sentences

    def summarize(self, title: str, text: str) -> str:
        sents = split_sentences(text)
        if len(sents) <= self.n:
            return " ".join(sents)
        freq = Counter(w for w in tokenize_words(text) if w not in STOPWORDS)
        title_terms = set(tokenize_words(title))
        scored = []
        for i, s in enumerate(sents):
            words = [w for w in tokenize_words(s) if w not in STOPWORDS]
            if not words:
                continue
            score = sum(freq[w] for w in words) / math.sqrt(len(words))
            score += 2 * sum(1 for w in words if w in title_terms)
            score *= 1.25 if i == 0 else 1.0  # lead-sentence bias typical for news
            scored.append((score, i))
        top = sorted(i for _, i in sorted(scored, reverse=True)[: self.n])
        return " ".join(sents[i] for i in top)


class DistilBartSummarizer:
    """Abstractive summaries with DistilBART-CNN (a distilled BART, trained on CNN/DailyMail)."""

    name = "distilbart-cnn"

    def __init__(self, model_name: str, min_words: int = 60):
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name).eval()
        self.min_words = min_words
        self._fallback = ExtractiveSummarizer()

    def summarize(self, title: str, text: str) -> str:
        # Too short to summarize abstractively -> keep the lead sentences.
        if len(text.split()) < self.min_words:
            return self._fallback.summarize(title, text)
        enc = self.tokenizer(text, truncation=True, max_length=1024, return_tensors="pt")
        with self._torch.no_grad():
            ids = self.model.generate(
                **enc, num_beams=4, max_length=90, min_length=25, no_repeat_ngram_size=3, early_stopping=True
            )
        return self.tokenizer.decode(ids[0], skip_special_tokens=True).strip()
