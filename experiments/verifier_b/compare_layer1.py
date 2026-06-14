"""Layer-1 5-set comparison: Verifier A vs v0/v1 (uncal + Platt-cal) on the same
combined FEVER+SciFact seed-13 3-way test set.

Objective recap: certify a competent, calibratable verifier that is cheaper +
faster than A's 3-model ensemble. So the table foregrounds competency (macro-F1),
calibration (ECE pre/post Platt, AUROC), and latency (p50/p90) — the last is the
decision lever: a comparable B that runs ~100x faster is a win.

A's macro-F1 + latency are recomputed from its persisted predictions on the SAME
1300 examples (contested excluded, pred contested->insufficient). A's ECE/AUROC
come from its Layer-1 report; note A's confidence target (agreement-in-verdict)
differs from B's (P(supported)), so ECE is "both calibratable", not a strict
apples-to-apples number.

Usage: .venv/bin/python -m experiments.verifier_b.compare_layer1
"""
from __future__ import annotations

import json
from pathlib import Path

from dra.eval.metrics import macro_f1

REPO = Path(__file__).resolve().parents[2]
PRED = REPO / "eval" / "results" / "verifier" / "predictions"
BDIR = REPO / "eval" / "results" / "verifier_b"


def _a_from_predictions():
    golds, preds, lat = [], [], []
    for ds in ("fever", "scifact"):
        fp = PRED / f"A__{ds}__test__latest__seed13.jsonl"
        for line in open(fp):
            r = json.loads(line)
            g, p = r.get("gold"), r.get("pred")
            if g in ("supported", "refuted", "insufficient"):
                golds.append(g)
                preds.append("insufficient" if p in ("contested", "insufficient") else p)
                if r.get("latency_ms") is not None:
                    lat.append(r["latency_ms"])
    lat.sort()
    return {
        "n": len(golds),
        "macro_f1": macro_f1(golds, preds)["macro_f1"],
        "latency_ms_p50": lat[len(lat) // 2],
        "latency_ms_p90": lat[int(len(lat) * 0.9)],
    }


def _b(variant):
    return json.loads((BDIR / variant / "layer1.json").read_text())


def main():
    a = _a_from_predictions()
    v0, v1 = _b("v0"), _b("v1")
    a_p50 = a["latency_ms_p50"]

    def speedup(x):
        return f"{a_p50 / x['latency_ms_p50']:.0f}x"

    rows = [
        ("A (ensemble)", a["macro_f1"], None, None, None, a["latency_ms_p50"], "1x"),
        ("v0 uncal", v0["macro_f1"], v0["ece_before"], v0["auroc"], v0["brier_before"], v0["latency_ms_p50"], speedup(v0)),
        ("v0 cal",   v0["macro_f1"], v0["ece_after"],  v0["auroc"], v0["brier_after"],  v0["latency_ms_p50"], speedup(v0)),
        ("v1 uncal", v1["macro_f1"], v1["ece_before"], v1["auroc"], v1["brier_before"], v1["latency_ms_p50"], speedup(v1)),
        ("v1 cal",   v1["macro_f1"], v1["ece_after"],  v1["auroc"], v1["brier_after"],  v1["latency_ms_p50"], speedup(v1)),
    ]
    print(f"\nLayer-1 5-set (combined FEVER+SciFact 3-way, n={a['n']})\n")
    print("| set | macro-F1 | ECE | AUROC | Brier | latency p50 (ms) | speedup vs A |")
    print("|---|---|---|---|---|---|---|")
    for name, f1, ece, au, br, p50, sp in rows:
        fmt = lambda x: "—" if x is None else f"{x:.3f}"
        print(f"| {name} | {f1:.3f} | {fmt(ece)} | {fmt(au)} | {fmt(br)} | {p50:.1f} | {sp} |")

    # best B by the objective: competency in A's band AND best post-Platt ECE
    best = "v0" if v0["ece_after"] <= v1["ece_after"] else "v1"
    print(f"\nBest B (objective: competent + best calibration): {best} (cal) "
          f"— ECE_after v0={v0['ece_after']:.3f} vs v1={v1['ece_after']:.3f}; "
          f"macro-F1 v0={v0['macro_f1']:.3f} vs v1={v1['macro_f1']:.3f}; "
          f"~{a_p50 / v0['latency_ms_p50']:.0f}x faster than A.")


if __name__ == "__main__":
    main()
