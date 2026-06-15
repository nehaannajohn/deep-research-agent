"""Unit test for the pure Layer-1 metric assembly (no torch / no loaders)."""
from __future__ import annotations

from experiments.code.eval_layer1 import summarize


def test_summarize_reports_macro_f1_calibration_and_auroc():
    golds = ["supported", "refuted", "insufficient", "supported",
             "refuted", "supported", "insufficient", "supported"]
    preds = ["supported", "refuted", "insufficient", "refuted",
             "refuted", "supported", "insufficient", "supported"]
    # raw P(supported): high where gold is supported, low otherwise
    psup = [0.95, 0.05, 0.40, 0.80, 0.10, 0.90, 0.30, 0.88]

    out = summarize(preds, golds, psup)

    assert out["n"] == 8
    assert 0.0 <= out["macro_f1"] <= 1.0
    assert "per_class" in out
    for k in ("ece_before", "ece_after", "brier_before", "brier_after", "auroc"):
        assert k in out and 0.0 <= out[k] <= 1.0
    assert out["calib_fit_n"] + out["calib_eval_n"] == 8


def test_summarize_perfect_separation_high_auroc():
    # order so the interleaved even/odd split puts a supported AND a refuted in
    # each fold (else the test fold is single-class and AUROC is undefined).
    golds = ["supported", "refuted", "refuted", "supported"]
    preds = ["supported", "refuted", "refuted", "supported"]
    psup = [0.99, 0.01, 0.02, 0.98]  # perfectly separates supported vs not
    out = summarize(preds, golds, psup)
    assert out["macro_f1"] == 1.0
    assert out["auroc"] >= 0.99
