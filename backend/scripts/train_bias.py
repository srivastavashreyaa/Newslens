"""Fine-tune BERT / DistilBERT for political-leaning classification (left / center / right) and report REAL metrics.

Needs a labelled CSV with columns `text,label` (label in left|center|right). Public starting points include
AllSides-labelled article datasets and the BABE / POLUSA corpora (check each licence before use).

    pip install -r requirements-ml.txt
    python -m scripts.train_bias --csv data/bias.csv --out models/bias-distilbert --epochs 3

Then set BIAS_MODEL_PATH=models/bias-distilbert in .env. The held-out test accuracy / macro-F1 printed at the
end are the numbers you can honestly quote for "media bias detection accuracy".
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments

LABELS = ["left", "center", "right"]


class DS(Dataset):
    def __init__(self, enc, labels):
        self.enc, self.labels = enc, labels

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, i):
        item = {k: torch.tensor(v[i]) for k, v in self.enc.items()}
        item["labels"] = torch.tensor(self.labels[i])
        return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", default="models/bias-distilbert")
    ap.add_argument("--base", default="distilbert-base-uncased")  # or bert-base-uncased
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max-len", type=int, default=256)
    args = ap.parse_args()

    df = pd.read_csv(args.csv).dropna(subset=["text", "label"])
    df["label"] = df["label"].str.lower().str.strip()
    df = df[df["label"].isin(LABELS)]
    y = df["label"].map({l: i for i, l in enumerate(LABELS)}).tolist()
    X_tr, X_tmp, y_tr, y_tmp = train_test_split(df["text"].tolist(), y, test_size=0.3, stratify=y, random_state=42)
    X_val, X_te, y_val, y_te = train_test_split(X_tmp, y_tmp, test_size=0.5, stratify=y_tmp, random_state=42)

    tok = AutoTokenizer.from_pretrained(args.base)
    enc = lambda xs: tok(xs, truncation=True, padding=True, max_length=args.max_len)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base, num_labels=3, id2label=dict(enumerate(LABELS)), label2id={l: i for i, l in enumerate(LABELS)}
    )

    def metrics(p):
        preds = np.argmax(p.predictions, axis=-1)
        return {"accuracy": accuracy_score(p.label_ids, preds), "macro_f1": f1_score(p.label_ids, preds, average="macro")}

    trainer = Trainer(
        model=model,
        args=TrainingArguments(
            output_dir=args.out,
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch,
            per_device_eval_batch_size=args.batch * 2,
            eval_strategy="epoch",
            save_strategy="epoch",
            load_best_model_at_end=True,
            metric_for_best_model="macro_f1",
            learning_rate=3e-5,
            weight_decay=0.01,
            report_to="none",
        ),
        train_dataset=DS(enc(X_tr), y_tr),
        eval_dataset=DS(enc(X_val), y_val),
        compute_metrics=metrics,
    )
    trainer.train()

    pred = trainer.predict(DS(enc(X_te), y_te))
    preds = np.argmax(pred.predictions, axis=-1)
    report = classification_report(y_te, preds, target_names=LABELS, output_dict=True)
    print(classification_report(y_te, preds, target_names=LABELS))
    print(f"TEST accuracy={accuracy_score(y_te, preds):.4f} macro_f1={f1_score(y_te, preds, average='macro'):.4f}")

    trainer.save_model(args.out)
    tok.save_pretrained(args.out)
    Path(args.out, "test_metrics.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
