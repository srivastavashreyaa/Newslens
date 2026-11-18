"""Text cleaning, sentence/word tokenization and keyword extraction."""
import html
import re
from collections import Counter

STOPWORDS = set(
    """a about above after again against all also am an and any are as at be because been before being below
    between both but by can could did do does doing down during each few for from further had has have having he
    her here hers him his how i if in into is it its just like may me might more most much must my new no nor not
    now of off on once one only or other our out over own said say says same she should so some such than that the
    their them then there these they this those through to too under until up us very was we were what when where
    which while who whom why will with would you your according added also amid around still told since week year
    years day days time first last next monday tuesday wednesday thursday friday saturday sunday today yesterday
    people many make made get got going went take took including via per percent""".split()
)

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“‘'(])")
_WORD = re.compile(r"[A-Za-z][A-Za-z'\-]+")
_PROPER = re.compile(r"\b(?:[A-Z][a-zA-Z]+)(?:\s+(?:of|the|de|and)\s+[A-Z][a-zA-Z]+|\s+[A-Z][a-zA-Z]+)+\b")


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = _TAG.sub(" ", text)
    return _WS.sub(" ", text).strip()


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 1]


def tokenize_words(text: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(text or "")]


def extract_keywords(title: str, text: str, k: int = 8) -> list[str]:
    """Frequency-based keywords + proper-noun phrases. Title terms count triple."""
    title, text = clean_text(title), clean_text(text)
    scores: Counter = Counter()

    for blob, weight in ((title, 3), (text, 1)):
        for phrase in _PROPER.findall(blob):
            scores[phrase.lower()] += 2 * weight
        for w in tokenize_words(blob):
            if len(w) > 3 and w not in STOPWORDS:
                scores[w] += weight

    ranked = [t for t, _ in scores.most_common(k * 3)]
    out: list[str] = []
    for term in ranked:
        # skip unigrams already covered by a chosen phrase (and vice versa)
        if any(term != o and (term in o.split() or o in term.split()) for o in out):
            continue
        out.append(term)
        if len(out) == k:
            break
    return out
