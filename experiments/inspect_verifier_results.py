"""Join the per-candidate verifier-experiment outputs into a side-by-side dataset
for manual inspection, and report confidence statistics.

Reads experiments/results/verifier/{sonnet,mistral,nova,ensemble}.json (all aligned
by example index) and writes a stratified 20-example comparison (CSV + Markdown +
a detailed JSON with reasoning). Offline — no AWS/network.

Run: .venv/bin/python -m experiments.inspect_verifier_results
"""
from __future__ import annotations

import csv
import json
import os
from collections import defaultdict

BASE = os.path.join("experiments", "results", "verifier")
CANDS = ["sonnet", "mistral", "nova", "ensemble"]
LABELS = ["supported", "refuted", "insufficient", "contested"]
PER_LABEL = 5  # 5 per intended label -> 20 examples


def _mean(xs):
    return round(sum(xs) / len(xs), 3) if xs else None


def main():
    data = {c: json.load(open(os.path.join(BASE, f"{c}.json"))) for c in CANDS}
    n = len(data["sonnet"])

    # --- stratified sample: up to PER_LABEL examples per intended label ---
    by_label = defaultdict(list)
    for i in range(n):
        by_label[data["sonnet"][i]["intended"]].append(i)
    sample = []
    for lab in LABELS:
        sample.extend(by_label[lab][:PER_LABEL])
    sample.sort()

    # --- detailed rows (full reasoning) + flat CSV rows ---
    detailed, csv_rows = [], []
    for i in sample:
        intended = data["sonnet"][i]["intended"]
        claim = data["sonnet"][i]["claim"]
        d = {"idx": i, "intended": intended, "claim": claim, "candidates": {}}
        row = {"idx": i, "intended": intended, "claim": claim}
        for c in CANDS:
            p = data[c][i]
            d["candidates"][c] = {"pred": p["pred"], "confidence": p["confidence"],
                                  "recommendation": p["recommendation"], "reasoning": p["reasoning"]}
            row[f"{c}_pred"] = p["pred"]
            row[f"{c}_conf"] = p["confidence"]
            row[f"{c}_rec"] = p["recommendation"]
        detailed.append(d)
        csv_rows.append(row)

    with open(os.path.join(BASE, "comparison_sample.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        w.writeheader()
        w.writerows(csv_rows)
    with open(os.path.join(BASE, "comparison_sample_detailed.json"), "w") as f:
        json.dump(detailed, f, indent=2)

    # --- compact Markdown table (pred/conf per candidate) ---
    md = ["# Verifier comparison — 20-example stratified sample\n",
          "conf = self-consistency agreement (solos, /5) or cross-model agreement (ensemble, /3)\n",
          "| idx | intended | " + " | ".join(f"{c} (pred·conf)" for c in CANDS) + " | claim |",
          "|---|---|" + "---|" * len(CANDS) + "---|"]
    for r in csv_rows:
        cells = " | ".join(f"{r[f'{c}_pred']}·{r[f'{c}_conf']}" for c in CANDS)
        md.append(f"| {r['idx']} | {r['intended']} | {cells} | {r['claim'][:70]} |")
    with open(os.path.join(BASE, "comparison_sample.md"), "w") as f:
        f.write("\n".join(md) + "\n")

    # --- confidence statistics (all 60 examples) ---
    print("=== confidence stats (all", n, "examples) ===")
    print(f"{'cand':10s} {'mean':>6s} {'when_correct':>12s} {'when_wrong':>11s} {'n_wrong':>8s}  distinct_conf_values")
    stats = {}
    for c in CANDS:
        confs = [p["confidence"] for p in data[c]]
        correct = [p["confidence"] for p in data[c] if p["pred"] == p["intended"]]
        wrong = [p["confidence"] for p in data[c] if p["pred"] != p["intended"]]
        distinct = sorted({round(x, 3) for x in confs})
        stats[c] = {"mean": _mean(confs), "mean_correct": _mean(correct),
                    "mean_wrong": _mean(wrong), "n_wrong": len(wrong)}
        print(f"{c:10s} {str(_mean(confs)):>6s} {str(_mean(correct)):>12s} "
              f"{str(_mean(wrong)):>11s} {len(wrong):>8d}  {distinct}")
    with open(os.path.join(BASE, "confidence_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(f"\nWrote: comparison_sample.csv, comparison_sample.md, "
          f"comparison_sample_detailed.json, confidence_stats.json (in {BASE}/)")


if __name__ == "__main__":
    main()
