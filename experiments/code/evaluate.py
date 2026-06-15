"""Evaluate a Verifier B checkpoint: macro-F1 + per-class on the silver transfer
set; Platt-fit on P(supported); ECE before/after (live, GPU).

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.code.evaluate --variant v0
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from dra.eval.calibrate import PlattCalibrator, ece_before_after        # noqa: E402
from dra.eval.metrics import macro_f1                                   # noqa: E402
from dra.verify.cross_encoder import CrossEncoderVerifier               # noqa: E402
from dra.verify.cross_encoder_model import bind_score_fn                # noqa: E402
from dra.verify.train.transfer import TransferExample                   # noqa: E402

DATA = REPO / "eval" / "verifier_b_data"
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"


def _eval_transfer(verifier):
    rows = [TransferExample(**json.loads(l)) for l in open(DATA / "transfer.jsonl")]
    y_true, y_pred, p_sup, outcomes = [], [], [], []
    for ex in rows:
        texts = [p.text for p in ex.passages if (p.text or "").strip()]
        # supported-detector calibration needs max_sup, NOT VerifierResult.confidence
        # (now the predicted-label probability). aggregate() exposes it directly.
        if texts:
            label, _, _, max_sup, _, _ = verifier.aggregate(ex.claim, texts)
        else:
            label, max_sup = "insufficient", 0.0
        # 3-way for F1: contested folds back to nei for the head comparison
        pred = "nei" if label in ("insufficient", "contested") else label
        y_true.append(ex.label)
        y_pred.append(pred)
        p_sup.append(max_sup)
        outcomes.append(1 if ex.label == "supported" else 0)
    return y_true, y_pred, p_sup, outcomes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["v0", "v1"], required=True)
    a = ap.parse_args(argv)

    score_fn = bind_score_fn(str(MODELS / a.variant / "best"))
    verifier = CrossEncoderVerifier(score_fn=score_fn)

    yt, yp, psup, outc = _eval_transfer(verifier)
    f1 = macro_f1(yt, yp)
    # OUT-OF-SAMPLE calibration: fit Platt on an interleaved half, report ECE on the
    # other half (fitting + scoring on the same points gives an optimistic in-sample
    # ECE). Even indices = calibration fold, odd = test fold (representative split).
    cal_idx = list(range(0, len(psup), 2))
    test_idx = list(range(1, len(psup), 2))
    cal = PlattCalibrator().fit([psup[i] for i in cal_idx], [outc[i] for i in cal_idx])
    ece = ece_before_after([psup[i] for i in test_idx], [outc[i] for i in test_idx], cal)

    out = OUT / a.variant
    out.mkdir(parents=True, exist_ok=True)
    result = {"variant": a.variant, "transfer_macro_f1": f1["macro_f1"],
              "transfer_per_class": f1["per_class"], "ece": ece,
              "ece_note": "out-of-sample: Platt fit on calibration fold, ECE on held-out test fold",
              "platt": {"w": cal.w, "b": cal.b},
              "n_transfer": len(yt), "n_cal": len(cal_idx), "n_ece_test": len(test_idx)}
    (out / "eval.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
