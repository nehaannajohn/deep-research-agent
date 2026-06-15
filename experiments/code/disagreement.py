"""v0-vs-v1 disagreement / error analysis on the Layer-1 FEVER+SciFact test set.

Uses the REAL multi-passage `CrossEncoderVerifier.verify(claim, passages)` (the
verifier aggregates over ALL cited evidence sentences — 309/1300 examples are
multi-passage), so the verdicts match how the verifier actually operates. Finds
where one fine-tune is right and the other wrong, tags v1's error type, and dumps
the FULL evidence per case. Live (GPU), no Bedrock.

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.code.disagreement
Writes: eval/results/verifier_b/v1_gap.json  (+ console summary + sample)
"""
from __future__ import annotations

import collections
import json
from pathlib import Path

from dra.eval.loaders.fever import load_fever
from dra.eval.loaders.scifact import load_scifact
from dra.verify.cross_encoder import CrossEncoderVerifier

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"


def _label3(r):
    """Collapse a VerifierResult to FEVER/SciFact 3-way (contested -> insufficient)."""
    return "insufficient" if r.label in ("insufficient", "contested") else r.label


def _tag(gold, v1):
    if gold == "insufficient" and v1 in ("supported", "refuted"):
        return "genuine_over_commit"           # v1 asserts a verdict the evidence doesn't support
    if gold in ("supported", "refuted") and v1 == "insufficient":
        return "over_abstain"                   # defensible on multi-hop / thin single evidence
    return "wrong_direction_flip"


def main():
    from dra.verify.cross_encoder_model import bind_score_fn  # lazy (torch)

    v0 = CrossEncoderVerifier(score_fn=bind_score_fn(str(MODELS / "v0" / "best")))
    v1 = CrossEncoderVerifier(score_fn=bind_score_fn(str(MODELS / "v1" / "best")))
    examples = [("fever", e) for e in load_fever(seed=13)] + \
               [("scifact", e) for e in load_scifact(seed=13)]

    dist = collections.Counter(len(e.passages) for _, e in examples)
    print("n_passages distribution:", dict(sorted(dist.items())))

    v0_wins, v1_wins = [], []
    for ds, ex in examples:
        l0 = _label3(v0.verify(ex.claim, ex.passages))   # FULL multi-passage
        l1 = _label3(v1.verify(ex.claim, ex.passages))
        rec = {"ds": ds, "id": ex.example_id, "gold": ex.gold_label, "claim": ex.claim,
               "n_passages": len(ex.passages), "evidence": [p.text for p in ex.passages],
               "v0": l0, "v1": l1}
        if l0 == ex.gold_label and l1 != ex.gold_label:
            rec["tag"] = _tag(ex.gold_label, l1)
            v0_wins.append(rec)
        elif l1 == ex.gold_label and l0 != ex.gold_label:
            v1_wins.append(rec)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "v1_gap.json").write_text(json.dumps({"v0_wins": v0_wins, "v1_wins": v1_wins}, indent=2))

    print(f"\nv0-right & v1-WRONG: {len(v0_wins)}   |   v1-right & v0-wrong: {len(v1_wins)}")
    print("v1-error tags:", dict(collections.Counter(r["tag"] for r in v0_wins)))
    print("breakdown (gold -> v1):",
          dict(collections.Counter((r["gold"], r["v1"]) for r in v0_wins)))
    print("\n=== SAMPLE: genuine over-commit (gold=insufficient, v1 committed) ===")
    for r in [x for x in v0_wins if x["tag"] == "genuine_over_commit"][:6]:
        print(f"\n[{r['ds']}] gold={r['gold']} v0={r['v0']} v1={r['v1']} n_ev={r['n_passages']}")
        print(f"  claim: {r['claim'][:140]}")
        for i, e in enumerate(r["evidence"][:3]):
            print(f"  evid[{i}]: {e[:160]}")
    print(f"\nFull dump -> {OUT / 'v1_gap.json'}")


if __name__ == "__main__":
    main()
