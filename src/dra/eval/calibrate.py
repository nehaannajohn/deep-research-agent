"""Calibration metrics (ECE, Brier, AUROC, Cohen's κ) + a post-hoc Platt calibrator over the
binary supported-vs-not signal. Pure Python (no numpy/sklearn). Isotonic fallback deferred.
See docs/superpowers/specs/2026-06-11-layer1-verifier-eval-design.md §4-5."""
from __future__ import annotations

import math


def ece(probs, outcomes, bins: int = 15) -> float:
    """Expected calibration error: bin p(supported) into `bins` equal-width buckets (lo, hi];
    bucket 0 also includes p==0; ECE = sum over buckets of (n_bucket/N) * |mean_conf - accuracy|."""
    n = len(probs)
    if n == 0:
        return 0.0
    total = 0.0
    for k in range(bins):
        lo, hi = k / bins, (k + 1) / bins
        idx = [i for i, p in enumerate(probs) if (p > lo or (k == 0 and p >= lo)) and p <= hi]
        if not idx:
            continue
        conf = sum(probs[i] for i in idx) / len(idx)
        acc = sum(outcomes[i] for i in idx) / len(idx)
        total += (len(idx) / n) * abs(conf - acc)
    return total


def brier(probs, outcomes) -> float:
    n = len(probs)
    return sum((p - o) ** 2 for p, o in zip(probs, outcomes)) / n if n else 0.0


def auroc(probs, outcomes) -> float:
    """Area under ROC = P(score(pos) > score(neg)), tie-corrected via average ranks
    (Mann-Whitney U). Returns 0.0 if a class is absent."""
    n_pos = sum(1 for o in outcomes if o == 1)
    n_neg = len(outcomes) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.0
    order = sorted(range(len(probs)), key=lambda i: probs[i])
    ranks = [0.0] * len(probs)
    i = 0
    while i < len(order):
        j = i
        while j < len(order) and probs[order[j]] == probs[order[i]]:
            j += 1
        avg = (i + 1 + j) / 2.0  # average of 1-based ranks i+1..j
        for k in range(i, j):
            ranks[order[k]] = avg
        i = j
    sum_pos = sum(ranks[i] for i, o in enumerate(outcomes) if o == 1)
    return (sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)


def cohen_kappa(a, b) -> float:
    """Cohen's κ between two label sequences."""
    n = len(a)
    if n == 0:
        return 0.0
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    labels = set(a) | set(b)
    pe = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return (po - pe) / (1 - pe) if (1 - pe) != 0 else 1.0


class PlattCalibrator:
    """1-D Platt scaling: fit sigmoid(w*score + b) to outcomes via gradient descent on log-loss."""
    def __init__(self):
        self.w, self.b = 1.0, 0.0

    def fit(self, scores, outcomes, lr: float = 0.5, iters: int = 3000):
        w, b, n = 0.0, 0.0, max(1, len(scores))
        for _ in range(iters):
            gw = gb = 0.0
            for s, o in zip(scores, outcomes):
                p = 1.0 / (1.0 + math.exp(-(w * s + b)))
                gw += (p - o) * s
                gb += (p - o)
            w -= lr * gw / n
            b -= lr * gb / n
        self.w, self.b = w, b
        return self

    def apply(self, score: float) -> float:
        return 1.0 / (1.0 + math.exp(-(self.w * score + self.b)))


def ece_before_after(probs, outcomes, calibrator, bins: int = 15) -> dict:
    """Convenience: ECE/Brier on the raw probs vs the calibrator-applied probs."""
    cal = [calibrator.apply(p) for p in probs]
    return {"ece_before": ece(probs, outcomes, bins), "ece_after": ece(cal, outcomes, bins),
            "brier_before": brier(probs, outcomes), "brier_after": brier(cal, outcomes)}
