from __future__ import annotations

from dra.verify.train.prm import insensitivity_check, monotonicity_ladder


def test_monotonicity_passes_when_p_rises_along_rungs():
    rows = [[0.1, 0.2, 0.5, 0.9]] * 100
    res = monotonicity_ladder(rows)
    assert res["frac_monotonic"] == 1.0
    assert res["mean_delta"] > 0
    assert res["pass"] is True


def test_monotonicity_fails_when_flat_or_decreasing():
    rows = [[0.9, 0.8, 0.7, 0.6]] * 100
    res = monotonicity_ladder(rows)
    assert res["pass"] is False


def test_insensitivity_passes_when_padding_barely_moves_p():
    pairs = [(0.80, 0.81), (0.50, 0.49), (0.30, 0.31)]
    res = insensitivity_check(pairs, eps=0.05)
    assert res["mean_abs_delta"] < 0.05 and res["pass"] is True


def test_insensitivity_fails_when_padding_inflates_p():
    pairs = [(0.50, 0.80), (0.40, 0.75)]
    res = insensitivity_check(pairs, eps=0.05)
    assert res["pass"] is False
