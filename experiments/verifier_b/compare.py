"""Consolidate v0 vs v1 into one comparison table (the ablation headline).

Reads eval/results/verifier_b/{v0,v1}/{eval.json,prm.json} and writes compare.md.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "eval" / "results" / "verifier_b"


def _load(v, name):
    p = OUT / v / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else {}


def main():
    e0, e1 = _load("v0", "eval"), _load("v1", "eval")
    p0, p1 = _load("v0", "prm"), _load("v1", "prm")
    lines = ["# Verifier B — v0 vs v1\n",
             "| metric | v0 (public) | v1 (+our-distribution) |",
             "|---|---|---|",
             f"| transfer macro-F1 | {e0.get('transfer_macro_f1')} | {e1.get('transfer_macro_f1')} |",
             f"| ECE (after Platt) | {e0.get('ece',{}).get('ece_after')} | {e1.get('ece',{}).get('ece_after')} |",
             f"| monotonicity pass | {p0.get('monotonicity',{}).get('pass')} | {p1.get('monotonicity',{}).get('pass')} |",
             f"| monotonicity frac | {p0.get('monotonicity',{}).get('frac_monotonic')} | {p1.get('monotonicity',{}).get('frac_monotonic')} |",
             f"| insensitivity pass | {p0.get('insensitivity',{}).get('pass')} | {p1.get('insensitivity',{}).get('pass')} |"]
    for cls in ("supported", "refuted", "nei"):
        c0 = (e0.get("transfer_per_class") or {}).get(cls, {})
        c1 = (e1.get("transfer_per_class") or {}).get(cls, {})
        lines.append(f"| transfer F1 [{cls}] | {c0.get('f1')} | {c1.get('f1')} |")
    (OUT / "compare.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
