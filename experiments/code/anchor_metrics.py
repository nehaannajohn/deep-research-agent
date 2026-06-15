"""After anchor.csv is hand-labeled (human_label column filled), compute:
  - grounding-judge(silver) vs human Cohen's kappa
  - count of disagreements
Run locally; pure read + kappa. Usage: python -m experiments.code.anchor_metrics
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dra.eval.calibrate import cohen_kappa  # noqa: E402

CSVP = REPO / "eval" / "verifier_b_data" / "anchor.csv"


def main():
    silver, human = [], []
    with open(CSVP, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            h = (row.get("human_label") or "").strip()
            if h:
                silver.append(row["silver_label"].strip())
                human.append(h)
    if not human:
        print("no human labels yet; fill the human_label column in anchor.csv")
        return
    k = cohen_kappa(silver, human)
    agree = sum(1 for s, h in zip(silver, human) if s == h)
    print(f"n={len(human)}  silver-vs-human agreement={agree}/{len(human)}  kappa={k:.3f}")


if __name__ == "__main__":
    main()
