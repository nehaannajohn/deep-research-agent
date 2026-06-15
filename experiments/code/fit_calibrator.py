"""Fit + persist PER-LABEL Platt calibrators for a Verifier B variant, so the
verifier can surface a *calibrated confidence of the predicted label* (not just
P(supported)). One one-vs-rest calibrator per label:

  supported   : raw = max p_supported          , positive iff gold == supported
  refuted     : raw = max p_refuted             , positive iff gold == refuted
  insufficient: raw = max p_nei                 , positive iff gold == insufficient

These three head classes are fit on FEVER+SciFact. **Contested is NOT fit here**:
it is a conjunction (a genuine supporting AND a genuine refuting passage), so its
confidence is DERIVED at inference from the supported/refuted calibrators —
`min(supported_cal(max_sup), refuted_cal(max_ref))` in
`CrossEncoderVerifier.label_confidence` — needing no contested gold. (FEVER/SciFact
have none, and the prior contested artifact carries no passages to score.)
`fit_label_calibrators` still fits a contested calibrator IF contested rows with
passages are ever supplied; a label with no positives/negatives is skipped.

`fit_label_calibrators(rows)` is pure and unit-tested; `run()` is the live (GPU)
driver. Output `platt.json` (per-label) is back-compat-read by run_pipeline_eval.

Usage: CUDA_VISIBLE_DEVICES=0 .venv-train/bin/python -m experiments.code.fit_calibrator --variant v0
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from dra.eval.calibrate import PlattCalibrator

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "eval" / "verifier_b_models"
OUT = REPO / "eval" / "results" / "verifier_b"

LABELS = ("supported", "refuted", "insufficient", "contested")


def _raw_for_label(row: dict, label: str) -> float:
    """The pre-calibration score the predicted label's confidence is read from
    (mirrors CrossEncoderVerifier.raw_label_confidence)."""
    if label == "supported":
        return row["max_sup"]
    if label == "refuted":
        return row["max_ref"]
    if label == "insufficient":
        return row["max_nei"]
    return min(row["max_sup"], row["max_ref"])  # contested


def fit_label_calibrators(rows: list[dict]) -> dict:
    """rows: dicts with max_sup, max_ref, max_nei, gold. Returns
    {label: {w, b, n, pos}} for every label that has BOTH positives and negatives
    in `rows` (one-vs-rest). Degenerate labels are skipped, not faked."""
    out: dict[str, dict] = {}
    for label in LABELS:
        scores = [_raw_for_label(r, label) for r in rows]
        outc = [1 if r["gold"] == label else 0 for r in rows]
        pos = sum(outc)
        if not (0 < pos < len(outc)):  # need both classes to fit a calibrator
            continue
        cal = PlattCalibrator().fit(scores, outc)
        out[label] = {"w": cal.w, "b": cal.b, "n": len(rows), "pos": pos}
    return out


def _harvest(verifier, examples) -> list[dict]:  # pragma: no cover - live (torch)
    """Run the (frozen) cross-encoder over each example and record the per-class
    max probabilities + gold label, using the SAME aggregation as verify()."""
    rows = []
    for ex in examples:
        texts = [p.text for p in ex.passages if (p.text or "").strip()]
        if not texts:
            continue
        _, _, _, max_sup, max_ref, max_nei = verifier.aggregate(ex.claim, texts)
        rows.append({"max_sup": max_sup, "max_ref": max_ref, "max_nei": max_nei,
                     "gold": ex.gold_label})
    return rows


def run(variant: str, contested_examples=None) -> dict:  # pragma: no cover - live (GPU)
    from dra.eval.loaders.fever import load_fever
    from dra.eval.loaders.scifact import load_scifact
    from dra.verify.cross_encoder import CrossEncoderVerifier
    from dra.verify.cross_encoder_model import bind_score_fn  # lazy (torch)

    verifier = CrossEncoderVerifier(score_fn=bind_score_fn(str(MODELS / variant / "best")))
    examples = list(load_fever(seed=13)) + list(load_scifact(seed=13))
    if contested_examples:
        examples += list(contested_examples)
    rows = _harvest(verifier, examples)
    labels = fit_label_calibrators(rows)

    out = OUT / variant
    out.mkdir(parents=True, exist_ok=True)
    payload = {"labels": labels, "n": len(rows), "fit_on": "fever+scifact seed13"
               + ("+contested" if contested_examples else "")}
    (out / "platt.json").write_text(json.dumps(payload, indent=2))
    summary = ", ".join(f"{k}(pos={v['pos']}, w={v['w']:.3f}, b={v['b']:.3f})"
                        for k, v in labels.items())
    print(f"{variant}: per-label Platt over {len(rows)} claims -> {summary or 'NONE'} "
          f"-> {out}/platt.json")
    return payload


def main(argv=None):  # pragma: no cover - live
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["v0", "v1"], required=True)
    ap.add_argument("--contested-set", default=None,
                    help="optional path to a contested set (EvalExamples WITH passages) "
                         "to additionally fit a contested calibrator; by default contested "
                         "confidence is derived from supported/refuted at inference")
    a = ap.parse_args(argv)
    contested = None
    if a.contested_set:
        import json as _json
        from dra.eval.base import EvalExample
        contested = [EvalExample(**_json.loads(l)) for l in open(a.contested_set)]
    run(a.variant, contested_examples=contested)


if __name__ == "__main__":
    main()
