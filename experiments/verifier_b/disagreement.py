"""v0-vs-v1 disagreement / error analysis on the Layer-1 FEVER+SciFact test set.

Finds the cases where one fine-tune is right and the other wrong (per-example
probs included) to explain *why* v1 underperforms v0. Live (GPU), no Bedrock.

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.disagreement
Writes: eval/results/verifier_b/v1_gap.json  (+ console summary + sample)
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

from dra.eval.loaders.fever import load_fever
from dra.eval.loaders.scifact import load_scifact

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"


def _label3(p, margin=0.5):
    """Single-passage CrossEncoderVerifier label, collapsed to FEVER/SciFact 3-way."""
    s, r = p["supported"], p["refuted"]
    if s >= margin and r >= margin:
        return "insufficient"   # contested -> insufficient for 3-way scoring
    if s >= margin:
        return "supported"
    if r >= margin:
        return "refuted"
    return "insufficient"


def main():
    from experiments.verifier_b.evaluate import _bind_score_fn  # lazy (torch)

    v0 = _bind_score_fn(str(MODELS / "v0" / "best"))
    v1 = _bind_score_fn(str(MODELS / "v1" / "best"))
    examples = [("fever", e) for e in load_fever(seed=13)] + \
               [("scifact", e) for e in load_scifact(seed=13)]

    v0_wins, v1_wins = [], []
    for ds, ex in examples:
        psg = ex.passages[0].text if ex.passages else ""
        p0, p1 = v0(ex.claim, psg), v1(ex.claim, psg)
        l0, l1 = _label3(p0), _label3(p1)
        rec = {"dataset": ds, "id": ex.example_id, "gold": ex.gold_label,
               "claim": ex.claim, "evidence": psg[:400],
               "v0": {"label": l0, "probs": {k: round(v, 3) for k, v in p0.items()}},
               "v1": {"label": l1, "probs": {k: round(v, 3) for k, v in p1.items()}}}
        if l0 == ex.gold_label and l1 != ex.gold_label:
            v0_wins.append(rec)
        elif l1 == ex.gold_label and l0 != ex.gold_label:
            v1_wins.append(rec)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v1_gap.json").write_text(json.dumps({"v0_wins": v0_wins, "v1_wins": v1_wins}, indent=2))

    print(f"v0-right & v1-WRONG: {len(v0_wins)}   |   v1-right & v0-wrong: {len(v1_wins)}")
    print("\n=== v0-right/v1-wrong, breakdown (gold -> v1's wrong pred) ===")
    for (g, p), n in collections.Counter((r["gold"], r["v1"]["label"]) for r in v0_wins).most_common():
        print(f"  gold={g:12s} -> v1 said {p:12s} : {n}")
    print("  by dataset:", dict(collections.Counter(r["dataset"] for r in v0_wins)))
    print("\n=== SAMPLE: v1 WRONG, v0 RIGHT (first 12) ===")
    for r in v0_wins[:12]:
        print(f"\n[{r['dataset']}] gold={r['gold']}  v0={r['v0']['label']}(OK)  v1={r['v1']['label']}(X)")
        print(f"  claim: {r['claim'][:140]}")
        print(f"  v0 {r['v0']['probs']} | v1 {r['v1']['probs']}")
    print(f"\nFull dump -> {OUT / 'v1_gap.json'}")


if __name__ == "__main__":
    main()
