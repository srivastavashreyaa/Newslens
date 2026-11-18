"""Media bias detection.

Two independent signals are reported:

* direction  (bias_score in [-1, +1], label left/center/right)
    - default: the outlet's editorial-lean prior (see feeds.json; approximate, editable)
    - if a fine-tuned BERT classifier is available (BIAS_MODEL_PATH, trained with scripts/train_bias.py),
      the text-level prediction P(right) - P(left) is blended with the source prior (70/30).
* subjectivity (0..1): density of emotionally charged / loaded wording (direction-neutral).
"""
import re

from .tokenization import tokenize_words

LOADED = set(
    """slams slammed blasts blasted destroys destroyed devastating shocking outrageous disastrous catastrophic
    horrific appalling stunning explosive furious fury chaos crisis scandal radical extremist extreme
    dangerous reckless corrupt disgraceful shameful heroic miracle triumph historic unprecedented brutal
    savage vicious ruthless betrayal betrayed lies liar fraud sham farce meltdown nightmare bombshell
    slashes crushes skyrockets plummets soars plunges stunned slammed erupts rages outcry backlash
    mocks vows defiant desperate bizarre insane absurd ridiculous so-called""".split()
)
_ABSOLUTES = set("always never everyone nobody totally absolutely completely utterly obviously clearly".split())


def subjectivity_score(text: str) -> float:
    words = tokenize_words(text)
    if not words:
        return 0.0
    loaded = sum(1 for w in words if w in LOADED)
    absolutes = sum(1 for w in words if w in _ABSOLUTES)
    exclaim = text.count("!")
    caps = len(re.findall(r"\b[A-Z]{4,}\b", text))
    density = (2.0 * loaded + 1.0 * absolutes + 1.5 * exclaim + 1.0 * caps) / len(words)
    return round(min(1.0, density * 6), 3)


def label_from_score(score: float, band: float = 0.25) -> str:
    return "left" if score <= -band else "right" if score >= band else "center"


class BiasDetector:
    def __init__(self, model_path: str = ""):
        self.model = None
        self.method = "source-prior"
        if model_path:
            self._load(model_path)

    def _load(self, path: str):
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        self._torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(path)
        self.model = AutoModelForSequenceClassification.from_pretrained(path).eval()
        labels = {int(i): l.lower() for i, l in self.model.config.id2label.items()}
        self._left = next(i for i, l in labels.items() if l.startswith("left"))
        self._right = next(i for i, l in labels.items() if l.startswith("right"))
        self.method = "bert-classifier+source-prior"

    def detect(self, title: str, text: str, source_prior: float = 0.0) -> tuple[str, float, float, str]:
        subj = subjectivity_score(f"{title}. {text}")
        score = source_prior
        if self.model is not None:
            enc = self.tokenizer(f"{title}. {text}", truncation=True, max_length=512, return_tensors="pt")
            with self._torch.no_grad():
                p = self._torch.softmax(self.model(**enc).logits, dim=-1)[0]
            score = 0.7 * (p[self._right] - p[self._left]).item() + 0.3 * source_prior
        score = max(-1.0, min(1.0, score))
        return label_from_score(score), round(score, 3), subj, self.method
