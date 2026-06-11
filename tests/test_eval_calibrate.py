from dra.eval.calibrate import ece, brier, auroc, cohen_kappa, PlattCalibrator, ece_before_after


def test_ece_zero_when_calibrated():
    # confidence matches accuracy within each bin -> ECE 0
    assert ece([0.0, 0.0, 1.0, 1.0], [0, 0, 1, 1]) == 0.0


def test_ece_overconfident():
    # both at conf 1.0 but only half correct -> ECE 0.5
    assert ece([1.0, 1.0], [1, 0]) == 0.5


def test_brier():
    assert brier([1.0, 0.0], [1, 0]) == 0.0
    assert brier([0.5, 0.5], [1, 0]) == 0.25


def test_auroc_perfect_and_tie():
    assert auroc([0.9, 0.8, 0.2, 0.1], [1, 1, 0, 0]) == 1.0
    assert auroc([0.5, 0.5], [1, 0]) == 0.5     # tie -> 0.5


def test_cohen_kappa():
    assert cohen_kappa(["a", "b", "c"], ["a", "b", "c"]) == 1.0
    assert round(cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]), 3) == 0.0  # chance


def test_platt_is_monotonic_and_separates():
    cal = PlattCalibrator().fit([0.0, 0.0, 1.0, 1.0], [0, 0, 1, 1])
    assert cal.apply(0.0) < cal.apply(1.0)
    assert cal.apply(1.0) > 0.5 > cal.apply(0.0)


def test_ece_before_after_improves_on_miscalibrated_signal():
    # a monotonic-but-miscalibrated signal: Platt should not worsen ECE
    scores = [0.1, 0.2, 0.3, 0.7, 0.8, 0.9]
    outcomes = [0, 0, 0, 1, 1, 1]
    res = ece_before_after(scores, outcomes, PlattCalibrator().fit(scores, outcomes))
    assert res["ece_after"] <= res["ece_before"] + 1e-9
