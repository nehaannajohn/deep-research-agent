"""Unit tests for per-label Platt calibrator fitting (pure logic)."""
from __future__ import annotations

from experiments.code.fit_calibrator import _raw_for_label, fit_label_calibrators


def test_raw_for_label_matches_verifier_definition():
    row = {"max_sup": 0.7, "max_ref": 0.4, "max_nei": 0.2}
    assert _raw_for_label(row, "supported") == 0.7
    assert _raw_for_label(row, "refuted") == 0.4
    assert _raw_for_label(row, "insufficient") == 0.2
    assert _raw_for_label(row, "contested") == 0.4  # min(0.7, 0.4)


def _rows():
    # supported & refuted both have positives and negatives; nei has none;
    # contested has none. Each calibrator is one-vs-rest on its raw score.
    return [
        {"max_sup": 0.9, "max_ref": 0.05, "max_nei": 0.05, "gold": "supported"},
        {"max_sup": 0.85, "max_ref": 0.10, "max_nei": 0.05, "gold": "supported"},
        {"max_sup": 0.10, "max_ref": 0.88, "max_nei": 0.02, "gold": "refuted"},
        {"max_sup": 0.15, "max_ref": 0.80, "max_nei": 0.05, "gold": "refuted"},
    ]


def test_fits_one_calibrator_per_label_with_both_classes():
    cals = fit_label_calibrators(_rows())
    # supported and refuted each have 2 positives / 2 negatives -> fit
    assert set(cals) == {"supported", "refuted"}
    assert cals["supported"]["pos"] == 2 and cals["supported"]["n"] == 4
    assert cals["refuted"]["pos"] == 2
    assert "w" in cals["supported"] and "b" in cals["supported"]


def test_skips_labels_without_both_classes():
    # nei never appears as gold -> 0 positives; contested likewise -> skipped
    cals = fit_label_calibrators(_rows())
    assert "insufficient" not in cals
    assert "contested" not in cals


def test_all_one_label_skips_that_label_too():
    rows = [{"max_sup": 0.9, "max_ref": 0.0, "max_nei": 0.1, "gold": "supported"}] * 3
    # supported has no negatives (pos == n) -> not fit; nothing fit at all
    assert fit_label_calibrators(rows) == {}
