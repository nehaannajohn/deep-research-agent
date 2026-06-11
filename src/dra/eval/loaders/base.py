"""Seeded, label-stratified sampling shared by loaders. SAMPLE_CAP = 1000 per dataset (decided)."""
from __future__ import annotations

import random

SAMPLE_CAP = 1000

# FEVER/SciFact 3-way -> our label space
LABEL_MAP = {
    "SUPPORTS": "supported", "REFUTES": "refuted", "NOT ENOUGH INFO": "insufficient",
    "SUPPORT": "supported", "CONTRADICT": "refuted", "NOINFO": "insufficient",
}


def stratified_sample(examples, n=SAMPLE_CAP, seed=13):
    """Up to n examples, balanced across gold_label as evenly as the data allows, seeded.
    Returns all if len(examples) <= n."""
    if len(examples) <= n:
        return list(examples)
    by_label = {}
    for ex in examples:
        by_label.setdefault(ex.gold_label, []).append(ex)
    rng = random.Random(seed)
    for v in by_label.values():
        rng.shuffle(v)
    out, labels = [], sorted(by_label)
    i = 0
    while len(out) < n and any(by_label[l] for l in labels):
        lab = labels[i % len(labels)]
        if by_label[lab]:
            out.append(by_label[lab].pop())
        i += 1
    return out[:n]
