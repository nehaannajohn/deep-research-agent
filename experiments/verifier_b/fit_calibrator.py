"""Fit + persist a Platt calibrator for a Verifier B variant on the Layer-1
FEVER+SciFact data (P(supported) detector), so the Layer-2 cross-encoder arm can
surface a *calibrated* confidence. Live (GPU).

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.fit_calibrator --variant v0
Writes: eval/results/verifier_b/<variant>/platt.json  ({w, b, n})
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dra.eval.calibrate import PlattCalibrator
from dra.eval.loaders.fever import load_fever
from dra.eval.loaders.scifact import load_scifact
from dra.verify.cross_encoder import CrossEncoderVerifier

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"


def run(variant: str) -> dict:
    from experiments.verifier_b.evaluate import _bind_score_fn  # lazy (torch)

    verifier = CrossEncoderVerifier(score_fn=_bind_score_fn(str(MODELS / variant / "best")))
    examples = list(load_fever(seed=13)) + list(load_scifact(seed=13))
    psup, outc = [], []
    for ex in examples:
        r = verifier.verify(ex.claim, ex.passages)
        psup.append(float(r.confidence))                  # raw max p_supported
        outc.append(1 if ex.gold_label == "supported" else 0)
    cal = PlattCalibrator().fit(psup, outc)
    out = OUT / variant
    out.mkdir(parents=True, exist_ok=True)
    payload = {"w": cal.w, "b": cal.b, "n": len(psup), "fit_on": "fever+scifact seed13"}
    (out / "platt.json").write_text(json.dumps(payload, indent=2))
    print(f"{variant}: Platt w={cal.w:.4f} b={cal.b:.4f} n={len(psup)} -> {out}/platt.json")
    return payload


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["v0", "v1"], required=True)
    run(ap.parse_args(argv).variant)


if __name__ == "__main__":
    main()
