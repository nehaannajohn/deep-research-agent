"""Run the §1.6 PRM gates on a checkpoint (live, GPU).

monotonicity: for each supported claim, score p_supported under
{distractor, partial, full}; rows fed to prm.monotonicity_ladder.
insensitivity: supported claims, p_supported on (clean gold) vs (gold padded with
3 distractor passages); fed to insensitivity_check.

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.run_prm --variant v1
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dra.eval.loaders.scifact import load_scifact          # noqa: E402
from dra.verify.train.prm import insensitivity_check, monotonicity_ladder  # noqa: E402

DATA = REPO / "eval" / "verifier_b_data"
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"


def main(argv=None):
    from experiments.verifier_b.evaluate import _bind_score_fn  # reuse binder

    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["v0", "v1"], required=True)
    a = ap.parse_args(argv)
    score = _bind_score_fn(str(MODELS / a.variant / "best"))

    distractors = [json.loads(l)["passage"] for l in open(DATA / "synthetic.jsonl")][:500]
    rng = random.Random(13)

    ladder_rows, insens_pairs = [], []
    n = 0
    for ex in load_scifact(split="train", n=4000):
        if ex.gold_label != "supported" or not ex.passages:
            continue
        gold = [p.text for p in ex.passages if p.text.strip()]
        if not gold:
            continue
        full = " ".join(gold)
        partial = " ".join(gold[: max(1, len(gold) // 2)])
        distractor = rng.choice(distractors)
        ladder_rows.append([
            score(ex.claim, distractor)["supported"],
            score(ex.claim, partial)["supported"],
            score(ex.claim, full)["supported"],
        ])
        padded = full + " " + " ".join(rng.sample(distractors, 3))
        insens_pairs.append((score(ex.claim, full)["supported"],
                             score(ex.claim, padded)["supported"]))
        n += 1
        if n >= 200:
            break

    res = {"variant": a.variant,
           "monotonicity": monotonicity_ladder(ladder_rows),
           "insensitivity": insensitivity_check(insens_pairs)}
    out = OUT / a.variant
    out.mkdir(parents=True, exist_ok=True)
    (out / "prm.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
