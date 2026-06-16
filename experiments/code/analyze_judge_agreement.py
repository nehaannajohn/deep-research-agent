"""Inter-judge agreement for the Layer-2 panel (relevance + quality).

Reads a compact per-judge dump — a JSON list of ``{"id", "relevance": [s1,s2,s3],
"quality": [s1,s2,s3]}`` (the ``per_judge`` lists pulled from a pipeline ``per_item.json``)
— and reports, per metric:

  * per-judge **disagreement rate** (how often a judge departs from the panel majority),
    plus each judge's mean score (leniency) and outlier behaviour;
  * **inter-annotator agreement**: exact pairwise agreement, pairwise Cohen's κ
    (quadratic-weighted), and Krippendorff's α (interval). Both are ordinal-aware — the
    1–5 scores are ordinal, so a nominal coefficient (e.g. Fleiss' κ) would treat "4 vs 5"
    as no closer than "1 vs 5" and understate agreement; it is deliberately not reported.

Judge order matches ``BEDROCK_PANEL_MODELS``: GPT-OSS 120B · Opus 4.8 · DeepSeek R1.

Run:  ``python -m experiments.code.analyze_judge_agreement <per_judge.json>``
"""
from __future__ import annotations

import itertools
import json
import sys
from collections import Counter

JUDGES = ["GPT-OSS 120B", "Opus 4.8", "DeepSeek R1"]
SCALE = [1, 2, 3, 4, 5]
METRICS = ["relevance", "quality"]


def _cohen_kappa_quadratic(a: list[int], b: list[int]) -> float | None:
    """Quadratic-weighted Cohen's κ for two raters over the fixed 1–5 scale — the penalty
    grows with the squared score gap, so adjacent disagreements (4 vs 5) count as near-
    agreement. None if undefined (zero expected disagreement)."""
    n = len(a)
    idx = {c: i for i, c in enumerate(SCALE)}
    k = len(SCALE)
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        obs[idx[x]][idx[y]] += 1
    row = [sum(obs[i]) / n for i in range(k)]
    col = [sum(obs[i][j] for i in range(k)) / n for j in range(k)]
    d = [[((i - j) / (k - 1)) ** 2 for j in range(k)] for i in range(k)]
    num = sum(d[i][j] * obs[i][j] / n for i in range(k) for j in range(k))
    den = sum(d[i][j] * row[i] * col[j] for i in range(k) for j in range(k))
    return None if den == 0 else 1 - num / den


def _krippendorff_alpha_interval(rows: list[list[int]]) -> float | None:
    """Krippendorff's α with an interval difference metric ((c-k)^2)."""
    # coincidence matrix over value pairs within each unit (all units have m=len ratings)
    coincidence: Counter = Counter()
    for scores in rows:
        m = len(scores)
        if m < 2:
            continue
        for c, k in itertools.permutations(scores, 2):
            coincidence[(c, k)] += 1 / (m - 1)
    n_c = Counter()
    for (c, _k), v in coincidence.items():
        n_c[c] += v
    n = sum(n_c.values())
    if n <= 1:
        return None
    D_o = sum(v * (c - k) ** 2 for (c, k), v in coincidence.items()) / n
    D_e = sum(n_c[c] * n_c[k] * (c - k) ** 2 for c in n_c for k in n_c) / (n * (n - 1))
    return None if D_e == 0 else 1 - D_o / D_e


def _fmt(x: float | None) -> str:
    return "undefined" if x is None else f"{x:+.3f}"


def analyze(metric: str, rows: list[list[int]]) -> None:
    N = len(rows)
    print(f"\n{'='*70}\n{metric.upper()}  (n = {N} items, 3 judges)\n{'='*70}")

    # per-judge score distribution + mean (leniency)
    print("\nPer-judge score distribution & mean:")
    for j, name in enumerate(JUDGES):
        col = [r[j] for r in rows]
        dist = {s: col.count(s) for s in SCALE if col.count(s)}
        print(f"  {name:14s} mean={sum(col)/N:.3f}  dist={dist}")

    # per-judge disagreement vs the panel majority
    print("\nPer-judge disagreement rate (score != panel majority):")
    disagree = [0] * 3
    sole_outlier = [0] * 3
    for r in rows:
        maj = Counter(r).most_common(1)[0][0]
        diff = [j for j in range(3) if r[j] != maj]
        for j in diff:
            disagree[j] += 1
        if len(diff) == 1:
            sole_outlier[diff[0]] += 1
    for j, name in enumerate(JUDGES):
        print(f"  {name:14s} {disagree[j]:3d}/{N} = {disagree[j]/N:6.1%}   "
              f"(sole outlier on {sole_outlier[j]} items)")

    # inter-annotator agreement (ordinal-aware only — scores are 1–5 ordinal)
    print("\nInter-annotator agreement — pairwise:")
    print(f"  {'pair':28s}{'exact':>8s}{'κ_quad':>9s}")
    for i, j in itertools.combinations(range(3), 2):
        a, b = [r[i] for r in rows], [r[j] for r in rows]
        exact = sum(x == y for x, y in zip(a, b)) / N
        k_w = _cohen_kappa_quadratic(a, b)
        print(f"  {JUDGES[i]+' / '+JUDGES[j]:28s}{exact:8.1%}{_fmt(k_w):>9s}")

    print("\nInter-annotator agreement — overall (3 raters):")
    print(f"  Krippendorff's α (interval)  {_fmt(_krippendorff_alpha_interval(rows))}")


def main(argv: list[str]) -> None:
    data = json.load(open(argv[0], encoding="utf-8"))
    print(f"Loaded {len(data)} items from {argv[0]}")
    for metric in METRICS:
        rows = [it[metric] for it in data
                if isinstance(it.get(metric), list) and len(it[metric]) == 3]
        dropped = len(data) - len(rows)
        if dropped:
            print(f"\n[{metric}] dropped {dropped} item(s) without a full 3-judge panel")
        if rows:
            analyze(metric, rows)


if __name__ == "__main__":
    main(sys.argv[1:])
