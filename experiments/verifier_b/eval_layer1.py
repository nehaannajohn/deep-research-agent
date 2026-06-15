"""Layer-1 eval of a Verifier B checkpoint on the SAME FEVER/SciFact seed-13
test set Verifier A used: 3-way macro-F1 + Platt ECE/Brier before-after +
AUROC + per-claim latency. Live (GPU). Mirrors the harness metrics so the rows
are directly A-comparable.

Objective (Layer-1): certify a *competent, calibratable* verifier that is
cheaper + faster than A's 3-model ensemble — not to beat A's macro-F1 (B trains
in-distribution on FEVER/SciFact, A is zero-shot).

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.verifier_b.eval_layer1 --variant v0

The torch model wrapper (`_bind_score_fn`) is imported lazily inside `run()` so
this module (and the pure `summarize`) import cleanly without torch — keeps the
unit test runnable in `.venv`.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dra.eval.calibrate import PlattCalibrator, auroc, brier, ece_before_after
from dra.eval.loaders.fever import load_fever
from dra.eval.loaders.scifact import load_scifact
from dra.eval.metrics import macro_f1
from dra.verify.cross_encoder import CrossEncoderVerifier

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"


def summarize(preds, golds, p_supported) -> dict:
    """Pure metric assembly (no torch/loaders) — A-comparable Layer-1 metrics.

    Calibration uses an interleaved even=calib / odd=test split (representative,
    avoids the FEVER||SciFact concatenation landing one dataset in one fold).
    `outcomes` is the supported-detector target (1 iff gold == supported), the
    same convention Verifier A's ECE and evaluate.py use.
    """
    f1 = macro_f1(golds, preds)
    outcomes = [1 if g == "supported" else 0 for g in golds]
    cal_idx = list(range(0, len(p_supported), 2))
    test_idx = list(range(1, len(p_supported), 2))
    cal = PlattCalibrator().fit([p_supported[i] for i in cal_idx],
                                [outcomes[i] for i in cal_idx])
    te_p = [p_supported[i] for i in test_idx]
    te_o = [outcomes[i] for i in test_idx]
    eb = ece_before_after(te_p, te_o, cal)
    return {
        "n": len(golds),
        "macro_f1": f1["macro_f1"],
        "per_class": f1["per_class"],
        "ece_before": eb["ece_before"],
        "ece_after": eb["ece_after"],
        "brier_before": eb["brier_before"],
        "brier_after": eb["brier_after"],
        "auroc": auroc(te_p, te_o),
        "calib_fit_n": len(cal_idx),
        "calib_eval_n": len(test_idx),
    }


def run(variant: str) -> dict:
    from experiments.verifier_b.evaluate import _bind_score_fn  # lazy (torch)

    score_fn = _bind_score_fn(str(MODELS / variant / "best"))
    verifier = CrossEncoderVerifier(score_fn=score_fn)
    examples = list(load_fever(seed=13)) + list(load_scifact(seed=13))

    preds, golds, psup, lat = [], [], [], []
    for ex in examples:
        texts = [p.text for p in ex.passages if (p.text or "").strip()]
        t0 = time.perf_counter()
        # aggregate() exposes the per-class maxes directly. We need max_sup
        # SPECIFICALLY (the supported-detector score summarize() calibrates on),
        # NOT VerifierResult.confidence — that is now the *predicted label's*
        # probability, which differs from max_sup for refuted/insufficient claims.
        if texts:
            label, _, _, max_sup, _, _ = verifier.aggregate(ex.claim, texts)
        else:
            label, max_sup = "insufficient", 0.0
        lat.append((time.perf_counter() - t0) * 1000.0)
        # collapse the 4-label verifier output to FEVER/SciFact 3-way
        preds.append("insufficient" if label in ("insufficient", "contested") else label)
        golds.append(ex.gold_label)
        psup.append(float(max_sup))  # raw max p_supported (supported-detector score)

    s = summarize(preds, golds, psup)
    lat_sorted = sorted(lat)
    s.update({
        "variant": variant,
        "datasets": ["fever", "scifact"],
        "latency_ms_p50": lat_sorted[len(lat_sorted) // 2],
        "latency_ms_p90": lat_sorted[int(len(lat_sorted) * 0.9)],
        "latency_ms_mean": sum(lat) / len(lat),
        "device": "gpu",
    })
    (OUT / variant).mkdir(parents=True, exist_ok=True)
    (OUT / variant / "layer1.json").write_text(json.dumps(s, indent=2))
    print(json.dumps(s, indent=2))
    return s


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["v0", "v1"], required=True)
    run(ap.parse_args(argv).variant)


if __name__ == "__main__":
    main()
