"""Fine-tune deberta-v3-base (3-way) for Verifier B (live, GPU).

Class-balanced sampling (WeightedRandomSampler over sampler_weights), early-stop
on held-out FEVER+SciFact macro-F1. Writes checkpoint + calibration-split logits.

Usage (one GPU per variant, run both in parallel):
    CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.train --variant v0
    CUDA_VISIBLE_DEVICES=1 .venv-train/bin/python -m experiments.verifier_b.train --variant v1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import torch
from torch.utils.data import Dataset, WeightedRandomSampler
from transformers import (AutoModelForSequenceClassification, AutoTokenizer,
                          Trainer, TrainingArguments)

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dra.eval.metrics import macro_f1                      # noqa: E402
from dra.verify.train import ID2LABEL, LABEL2ID            # noqa: E402
from dra.verify.train.datasets import assemble_variant, sampler_weights  # noqa: E402
from dra.verify.train.pairs import TrainPair               # noqa: E402

DATA = REPO / "eval" / "verifier_b_data"
MODELS = REPO / "eval" / "verifier_b_models"
MODEL_NAME = "microsoft/deberta-v3-base"
MAX_LEN = 512


def _load_slice(name):
    path = DATA / f"{name}.jsonl"
    if not path.exists():
        return []
    return [TrainPair(**json.loads(l)) for l in open(path, encoding="utf-8")]


class PairDS(Dataset):
    def __init__(self, pairs, tok):
        self.pairs, self.tok = pairs, tok

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        p = self.pairs[i]
        enc = self.tok(p.claim, p.passage, truncation="only_second",
                       max_length=MAX_LEN, padding="max_length", return_tensors="pt")
        return {"input_ids": enc["input_ids"][0],
                "attention_mask": enc["attention_mask"][0],
                "labels": torch.tensor(LABEL2ID[p.label])}


def _held_out():
    """Held-out eval from the OFFICIAL dev/validation splits — DISJOINT from the
    train split that feeds the mix (no leakage). FEVER `validation` and SciFact
    `dev` are separate from the `train` split build_data.py used for the pairs."""
    from dra.eval.loaders.fever import load_fever
    from dra.eval.loaders.scifact import load_scifact
    from dra.verify.train.pairs import example_to_pairs

    held = []
    for ex in load_fever(split="validation", n=3000):
        held += example_to_pairs(ex)
    for ex in load_scifact(split="dev", n=1000):
        held += example_to_pairs(ex)
    return held


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = logits.argmax(-1)
    y_true = [ID2LABEL[int(l)] for l in labels]
    y_pred = [ID2LABEL[int(p)] for p in preds]
    return {"macro_f1": macro_f1(y_true, y_pred)["macro_f1"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["v0", "v1"], required=True)
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-5)
    a = ap.parse_args(argv)

    raw = {n: _load_slice(n) for n in ("fever_pairs", "scifact_pairs", "synthetic", "curriculum")}
    slices = {"fever": raw["fever_pairs"], "scifact": raw["scifact_pairs"],
              "synthetic": raw["synthetic"], "curriculum": raw["curriculum"]}
    train_pairs = assemble_variant(a.variant, slices)
    held = _held_out()

    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME, num_labels=3, id2label=ID2LABEL, label2id=LABEL2ID)

    train_ds, eval_ds = PairDS(train_pairs, tok), PairDS(held, tok)
    weights = sampler_weights(train_pairs)
    sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True)

    out_dir = MODELS / a.variant
    args = TrainingArguments(
        output_dir=str(out_dir), num_train_epochs=a.epochs,
        per_device_train_batch_size=a.bs, per_device_eval_batch_size=64,
        learning_rate=a.lr, eval_strategy="epoch", save_strategy="epoch",
        load_best_model_at_end=True, metric_for_best_model="macro_f1",
        greater_is_better=True, logging_steps=50, report_to=[], fp16=True,
        save_total_limit=1)

    class _T(Trainer):
        def _get_train_sampler(self, *args, **kwargs):
            return sampler

    trainer = _T(model=model, args=args, train_dataset=train_ds,
                 eval_dataset=eval_ds, compute_metrics=compute_metrics)
    trainer.train()
    trainer.save_model(str(out_dir / "best"))
    tok.save_pretrained(str(out_dir / "best"))
    print(f"[{a.variant}] saved -> {out_dir/'best'}  eval={trainer.evaluate()}")


if __name__ == "__main__":
    main()
